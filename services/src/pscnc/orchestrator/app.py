"""API B2B de firma electrónica no cualificada.

Superficie pública mínima y explícita:

* ``POST /v1/signing-sessions``                inicia la sesión y resguarda el original
* ``POST /v1/signing-sessions/{id}/confirm``   verifica el consentimiento y firma
* ``GET  /v1/signing-sessions/{id}/evidence``  entrega el expediente y el documento
* ``GET  /health``                             sonda de vida para el balanceador

Toda petición de negocio se autentica con HMAC-SHA256 y su inquilino se deriva de
la credencial, nunca del cuerpo (ADR-0005).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pscnc import __version__
from pscnc.config import get_settings
from pscnc.errors import PscncError
from pscnc.logging_setup import configurar_logging, get_logger
from pscnc.models.api import (
    ConfirmSignatureRequest,
    EvidenceBundle,
    HealthResponse,
    SigningSessionCompleted,
    SigningSessionCreated,
)
from pscnc.orchestrator.dependencies import build_signing_service, get_secret_resolver
from pscnc.orchestrator.security import authenticate
from pscnc.orchestrator.state_machine import RequestEnvironment
from pscnc.repositories.dynamo_audit import SecurityContext

configurar_logging()
logger = get_logger(__name__)

TAMANIO_MAXIMO_PDF = 25 * 1024 * 1024  # 25 MiB

# Marcador para el caso en que no se pueda determinar la dirección del cliente.
# Deliberadamente NO es una dirección válida: escribir "0.0.0.0" en una evidencia
# pericial afirma algo falso —un perito no puede distinguir la dirección real de
# la ausencia de dato— y este campo se conserva como prueba del origen del acto.
# En producción el servicio corre detrás de un balanceador que siempre envía
# `X-Forwarded-For`, así que este valor señala una anomalía de despliegue.
IP_NO_CAPTURADA = "no-capturada"


class CuerpoCacheado:
    """Middleware ASGI que materializa el cuerpo y repone el canal de recepción.

    La firma HMAC cubre el cuerpo completo, de modo que la autenticación tiene
    que leerlo. En una petición ``multipart/form-data`` el analizador de FastAPI
    consume el flujo para resolver los parámetros ``Form`` y ``File`` **sin**
    dejarlo en la caché de la petición, y la lectura posterior fallaba con
    ``RuntimeError: Stream consumed``: el endpoint de creación de sesión no
    podía autenticar ninguna petición.

    Reponer el canal de recepción no alcanza: el analizador de formularios y la
    dependencia de autenticación comparten la **misma** instancia de
    ``Request``, y aquel la deja marcada como consumida. Por eso el cuerpo se
    publica además en el estado de la petición, de donde la autenticación lo
    toma sin volver a leer el flujo.

    El tamaño ya está acotado antes de llegar acá por el límite del balanceador;
    el control de 25 MiB del endpoint sigue aplicando sobre el archivo.
    """

    #: Clave bajo la que viaja el cuerpo crudo en ``request.state``.
    CLAVE_ESTADO = "cuerpo_firmado"

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in ("POST", "PUT", "PATCH"):
            await self._app(scope, receive, send)
            return

        partes: list[bytes] = []
        while True:
            mensaje = await receive()
            if mensaje["type"] != "http.request":
                # Desconexión del cliente: se delega el mensaje sin alterarlo.
                await self._app(scope, receive, send)
                return
            partes.append(mensaje.get("body", b""))
            if not mensaje.get("more_body", False):
                break

        cuerpo = b"".join(partes)
        scope.setdefault("state", {})[self.CLAVE_ESTADO] = cuerpo

        async def recibir() -> Message:
            return {"type": "http.request", "body": cuerpo, "more_body": False}

        await self._app(scope, recibir, send)


app = FastAPI(
    title="PSCNC · API de Firma Electrónica No Cualificada",
    version=__version__,
    description=(
        "API B2B para la generación de firmas electrónicas no cualificadas. El marco "
        "normativo aplicable lo determina la jurisdicción de cada transacción "
        "(ADR-0008)."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(CuerpoCacheado)

# Contrato público v1 (ADR-0007, ADR-0009). Se monta como router aparte para que
# la superficie heredada de `/v1/signing-sessions` pueda retirarse sin tocarlo.
from pscnc.orchestrator.rutas_v1 import router as router_v1  # noqa: E402

app.include_router(router_v1)


# --------------------------------------------------------------- Excepciones --
@app.exception_handler(PscncError)
async def _manejar_error_dominio(_request: Request, exc: PscncError) -> JSONResponse:
    """Traduce los errores del dominio a respuestas HTTP estables."""
    if exc.http_status >= 500:
        logger.error("domain_error", code=exc.code, message=exc.message)
    else:
        logger.info("domain_rejection", code=exc.code)
    return JSONResponse(status_code=exc.http_status, content=exc.to_payload())


# ------------------------------------------------------------ Autenticación --
async def contexto_autenticado(request: Request) -> SecurityContext:
    """Verifica la firma HMAC de la petición y devuelve el contexto del inquilino."""
    settings = get_settings()
    # El cuerpo lo dejó el middleware; leerlo de la petición fallaría cuando el
    # analizador de formularios ya consumió el flujo.
    cuerpo = getattr(request.state, CuerpoCacheado.CLAVE_ESTADO, None)
    if cuerpo is None:
        cuerpo = await request.body()
    return authenticate(
        headers=dict(request.headers),
        method=request.method,
        path=request.url.path,
        body=cuerpo,
        resolver=get_secret_resolver(),
        max_skew_seconds=settings.hmac_max_skew_seconds,
    )


def entorno_de_peticion(request: Request) -> RequestEnvironment:
    """Captura los datos de red con valor pericial.

    La IP se toma de ``X-Forwarded-For`` porque el servicio corre detrás de un
    balanceador; se usa el primer elemento de la cadena, que es el cliente real.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else IP_NO_CAPTURADA)
    )
    puerto = request.client.port if request.client else 0
    return RequestEnvironment(
        client_ip=ip,
        source_port=puerto or 1024,
        user_agent=request.headers.get("user-agent", "desconocido"),
        tls_version=request.headers.get("x-forwarded-tls-version", "TLSv1.3"),
        tls_cipher=request.headers.get("x-forwarded-tls-cipher", "TLS_AES_256_GCM_SHA384"),
    )


ContextoDep = Annotated[SecurityContext, Depends(contexto_autenticado)]
EntornoDep = Annotated[RequestEnvironment, Depends(entorno_de_peticion)]


# ------------------------------------------------------------------- Rutas ---
@app.get("/.well-known/fnc-keys.json", tags=["verificación"])
async def claves_publicas_de_sello() -> JSONResponse:
    """Claves públicas con las que se verifica el sello de las actas (RFC 7517).

    Es un endpoint **público y sin autenticación**, y tiene que serlo: el acta
    sellada solo sirve como prueba si un tercero —el inquilino, su asesoría legal,
    un perito— puede verificarla sin pedirnos acceso. Un sello que solo nosotros
    sabemos comprobar no traslada confianza, la concentra.

    Publica únicamente material público. La clave privada no puede salir del HSM
    ni aunque quisiéramos (ADR-0006).
    """
    from pscnc.evidence.claves_publicas import construir_jwks
    from pscnc.orchestrator.dependencies import build_tenant_key_rings

    jwks = construir_jwks(build_tenant_key_rings())

    return JSONResponse(
        content=jwks,
        headers={
            # Las claves cambian solo al rotar, un procedimiento planificado. Una
            # caché corta evita golpear a KMS en cada verificación sin que una
            # rotación tarde en propagarse.
            "Cache-Control": "public, max-age=300",
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["operación"])
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        version=__version__,
        crypto_backend=settings.crypto_backend,
    )


@app.post(
    "/v1/signing-sessions",
    response_model=SigningSessionCreated,
    status_code=201,
    tags=["firma"],
)
async def crear_sesion(
    context: ContextoDep,
    environment: EntornoDep,
    onboarding_token: Annotated[str, Form()],
    pdf_document: Annotated[UploadFile, File()],
    metadata: Annotated[str | None, Form()] = None,
) -> SigningSessionCreated:
    """Inicia una sesión de firma vinculada a un onboarding aprobado."""
    contenido = await pdf_document.read()
    if len(contenido) > TAMANIO_MAXIMO_PDF:
        raise PscncError("El documento supera el tamaño máximo admitido (25 MiB)")

    metadatos: dict[str, str] = {}
    if metadata:
        import json

        try:
            metadatos = {str(k): str(v) for k, v in json.loads(metadata).items()}
        except (ValueError, AttributeError) as exc:
            raise PscncError("El campo metadata no es un objeto JSON válido") from exc

    servicio = build_signing_service()
    return servicio.create_session(
        context=context,
        onboarding_token=onboarding_token,
        pdf_document=contenido,
        filename=pdf_document.filename,
        environment=environment,
        client_metadata=metadatos,
    )


@app.post(
    "/v1/signing-sessions/{session_id}/confirm",
    response_model=SigningSessionCompleted,
    tags=["firma"],
)
async def confirmar_firma(
    session_id: str,
    payload: ConfirmSignatureRequest,
    context: ContextoDep,
) -> SigningSessionCompleted:
    """Verifica el consentimiento y aplica la firma PAdES-B-T con sello de tiempo."""
    servicio = build_signing_service()
    return servicio.confirm(context=context, transaction_id=session_id, payload=payload)


@app.get(
    "/v1/signing-sessions/{session_id}/evidence",
    response_model=EvidenceBundle,
    tags=["evidencia"],
)
async def obtener_evidencia(session_id: str, context: ContextoDep) -> EvidenceBundle:
    """Entrega el expediente de evidencias y el documento firmado (URLs temporales)."""
    servicio = build_signing_service()
    return servicio.evidence(context=context, transaction_id=session_id)


@app.on_event("startup")
async def _verificar_configuracion() -> None:
    """Falla al arrancar si la configuración no permite firmar con garantías."""
    settings = get_settings()
    logger.info(
        "service_starting",
        environment=settings.environment,
        crypto_backend=settings.crypto_backend,
        version=__version__,
    )
    if settings.environment in ("staging", "prod"):
        settings.require_signing_configuration()


def create_app() -> Any:
    """Fábrica para servidores ASGI y pruebas."""
    return app
