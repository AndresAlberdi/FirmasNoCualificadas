"""Rutas del contrato público v1 (ADR-0007, ADR-0009).

Cuatro endpoints:

* ``POST /v1/transactions``                 abre la transacción
* ``POST /v1/transactions/{id}/confirm``    confirma y sella el acta
* ``GET  /v1/transactions/{id}/artifacts``  recupera lo producido
* ``GET  /v1/verify/{code}``                constancia pública, sin autenticación

Las dos escrituras exigen ``Idempotency-Key``. No es una comodidad: una
confirmación repetida debe devolver **el acta original**, porque dos actas para
un mismo acto de firma son dos evidencias divergentes sobre el mismo hecho, y eso
es material para impugnar ambas.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from pscnc.logging_setup import get_logger
from pscnc.models.motivos import RETRYABLE_REASONS, RejectionReason
from pscnc.models.v1 import (
    Artifacts,
    ConfirmTransactionRequest,
    CreateTransactionRequest,
    ErrorResponse,
    PublicVerification,
    TransactionConfirmed,
    TransactionCreated,
)
from pscnc.orchestrator.idempotencia import IdempotencyConflictError
from pscnc.orchestrator.transacciones import TransactionRejectedError
from pscnc.repositories.dynamo_audit import SecurityContext

logger = get_logger(__name__)

router = APIRouter(tags=["transacciones"])


async def contexto(request: Request) -> SecurityContext:
    """Autentica la petición y devuelve el inquilino.

    Se declara acá y no como middleware para que la ruta pública de verificación
    quede fuera por construcción: lo que no depende de esto, no exige credencial.
    """
    from pscnc.orchestrator.app import contexto_autenticado

    return await contexto_autenticado(request)


ContextoDep = Annotated[SecurityContext, Depends(contexto)]

#: Códigos HTTP por motivo. Se declara acá y no en cada rechazo para que el
#: contrato sea uniforme: el mismo motivo devuelve siempre el mismo código.
HTTP_STATUS_BY_REASON: dict[RejectionReason, int] = {
    RejectionReason.UNAUTHENTICATED: 401,
    RejectionReason.INVALID_SIGNATURE: 401,
    RejectionReason.REQUEST_EXPIRED: 401,
    RejectionReason.TENANT_NOT_ENABLED: 403,
    RejectionReason.TRANSACTION_OF_ANOTHER_TENANT: 403,
    RejectionReason.EXCLUDED_LEGAL_ACT: 403,
    RejectionReason.IDENTITY_NOT_APPROVED: 403,
    RejectionReason.TRANSACTION_NOT_FOUND: 404,
    RejectionReason.TRANSACTION_ALREADY_CONFIRMED: 409,
    RejectionReason.INVALID_STATE: 409,
    RejectionReason.IDEMPOTENCY_CONFLICT: 409,
    RejectionReason.TRANSACTION_EXPIRED: 410,
    RejectionReason.DOCUMENT_TAMPERED: 422,
    RejectionReason.INVALID_DOCUMENT: 422,
    RejectionReason.INVALID_IDENTITY_DOCUMENT: 422,
    RejectionReason.INCOMPLETE_IDENTITY_DECISION: 422,
    RejectionReason.IDEMPOTENCY_KEY_REQUIRED: 400,
    RejectionReason.UNSUPPORTED_JURISDICTION: 400,
    RejectionReason.SERVICE_LEVEL_NOT_CONTRACTED: 403,
    RejectionReason.SERVICE_LEVEL_UNAVAILABLE: 501,
    RejectionReason.OTP_NOT_VERIFIED: 422,
    RejectionReason.TIMESTAMP_UNAVAILABLE: 503,
}


def error_response(
    motivo: RejectionReason,
    mensaje: str,
    *,
    transaction_id: str | None = None,
    detalle: dict[str, Any] | None = None,
) -> JSONResponse:
    """Construye el cuerpo de rechazo del contrato."""
    cuerpo = ErrorResponse(
        motivo=motivo,
        mensaje=mensaje,
        transaction_id=transaction_id,
        detalle=detalle or {},
        reintentable=motivo in RETRYABLE_REASONS,
    )
    return JSONResponse(
        status_code=HTTP_STATUS_BY_REASON.get(motivo, 500),
        content=json.loads(cuerpo.model_dump_json()),
    )


async def _idempotente(
    request: Request,
    response_class: type[Any],
    clave: str | None,
    tenant_id: str,
    ejecutar: Any,
) -> Any:
    """Envuelve una escritura con el control de idempotencia.

    Devuelve la respuesta guardada si la operación ya se ejecutó con esa clave, y
    rechaza si la clave se reutilizó con otro cuerpo: devolver la primera
    respuesta sería peor que fallar, porque el tenant creería que su segunda
    petición se aplicó.
    """
    from pscnc.orchestrator.dependencies import get_control_idempotencia

    if not clave:
        return error_response(
            RejectionReason.IDEMPOTENCY_KEY_REQUIRED,
            "Las escrituras exigen la cabecera `Idempotency-Key`: sin ella, un reintento "
            "produciría un acta nueva para el mismo acto de firma.",
        )

    control = get_control_idempotencia()
    ruta = request.url.path
    cuerpo = await request.body()

    try:
        guardada = control.recuperar(tenant_id=tenant_id, clave=clave, ruta=ruta, cuerpo=cuerpo)
    except IdempotencyConflictError as exc:
        return error_response(RejectionReason.IDEMPOTENCY_CONFLICT, str(exc))

    if guardada is not None:
        return JSONResponse(
            status_code=guardada.status_code,
            content=guardada.body,
            # Le dice al tenant que esto es una repetición y no una operación
            # nueva: sin esta señal, un reintento parece un segundo acto.
            headers={"Idempotency-Replayed": "true"},
        )

    resultado = ejecutar()
    contenido = json.loads(resultado.model_dump_json())
    status_code = 201 if response_class is TransactionCreated else 200

    control.registrar(
        tenant_id=tenant_id,
        clave=clave,
        ruta=ruta,
        cuerpo=cuerpo,
        status_code=status_code,
        body=contenido,
    )
    return JSONResponse(status_code=status_code, content=contenido)


@router.post(
    "/v1/transactions",
    response_model=TransactionCreated,
    status_code=201,
    responses={409: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def crear_transaccion(
    peticion: CreateTransactionRequest,
    request: Request,
    context: ContextoDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    """Abre una transacción de firma.

    La decisión de identidad llega tomada por el tenant y se asienta como
    evidencia; FNC no la revisa (ADR-0009).
    """
    from pscnc.orchestrator.dependencies import build_transaction_service

    servicio = build_transaction_service()

    try:
        return await _idempotente(
            request,
            TransactionCreated,
            idempotency_key,
            context.b2b_client_id,
            lambda: servicio.crear(tenant_id=context.b2b_client_id, peticion=peticion),
        )
    except TransactionRejectedError as exc:
        return error_response(
            exc.motivo, exc.mensaje, transaction_id=exc.transaction_id, detalle=exc.detalle
        )


@router.post(
    "/v1/transactions/{transaction_id}/confirm",
    response_model=TransactionConfirmed,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def confirmar_transaccion(
    transaction_id: str,
    peticion: ConfirmTransactionRequest,
    request: Request,
    context: ContextoDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    """Confirma el acto y devuelve el acta sellada.

    Una confirmación repetida con la misma clave devuelve **el acta original**.
    """
    from pscnc.orchestrator.dependencies import build_transaction_service

    servicio = build_transaction_service()

    try:
        return await _idempotente(
            request,
            TransactionConfirmed,
            idempotency_key,
            context.b2b_client_id,
            lambda: servicio.confirmar(
                tenant_id=context.b2b_client_id,
                transaction_id=transaction_id,
                peticion=peticion,
            ),
        )
    except TransactionRejectedError as exc:
        return error_response(
            exc.motivo, exc.mensaje, transaction_id=exc.transaction_id, detalle=exc.detalle
        )


@router.get(
    "/v1/transactions/{transaction_id}/artifacts",
    response_model=Artifacts,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def obtener_artefactos(transaction_id: str, context: ContextoDep) -> Any:
    """Recupera el acta sellada y el código de verificación."""
    from pscnc.orchestrator.dependencies import build_transaction_service

    try:
        return build_transaction_service().artefactos(
            tenant_id=context.b2b_client_id, transaction_id=transaction_id
        )
    except TransactionRejectedError as exc:
        return error_response(
            exc.motivo, exc.mensaje, transaction_id=exc.transaction_id, detalle=exc.detalle
        )


@router.get("/v1/verify/{code}", response_model=PublicVerification, tags=["verificación"])
async def verificar_publicamente(code: str, response: Response) -> PublicVerification:
    """Constancia pública de un acto de firma. **Sin autenticación.**

    La consulta quien recibió el documento, que no tiene credenciales. No devuelve
    ningún dato personal: confirma que el acto existe, sobre qué documento y bajo
    qué norma. Un código inexistente y uno no confirmado responden igual, para que
    quien prueba códigos al azar no pueda averiguar cuáles existen.
    """
    from pscnc.orchestrator.dependencies import build_transaction_service

    # Sin caché: una constancia es un estado que puede cambiar, y servir una
    # copia vieja de una verificación sería peor que no servirla.
    response.headers["Cache-Control"] = "no-store"
    return build_transaction_service().verificar(code)
