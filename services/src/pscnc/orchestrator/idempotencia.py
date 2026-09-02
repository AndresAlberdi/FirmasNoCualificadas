"""Idempotencia de las escrituras del contrato público (ADR-0009).

## Por qué es obligatoria y no opcional

Una confirmación repetida —por un reintento de red, por un tiempo de espera
agotado del lado del tenant— **debe devolver el acta original, nunca una nueva**.
Emitir dos actas para un mismo acto de firma produce dos piezas de evidencia
divergentes sobre el mismo hecho: sellos distintos, instantes distintos, y ninguna
forma de decidir cuál es la buena. Es exactamente el material que una pericia
usaría para impugnar las dos.

## Qué se guarda y por qué el hash del cuerpo

Se guarda la respuesta y **la huella de la petición que la produjo**. Si llega la
misma clave con un cuerpo distinto, no hay forma de saber cuál de las dos
peticiones es la que el tenant quiso: se rechazan ambas con
`IDEMPOTENCY_CONFLICT` en lugar de devolver una respuesta que corresponde a
otra petición. Devolver la primera sería peor que fallar, porque el tenant creería
que su segunda petición se aplicó.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from pscnc.logging_setup import get_logger
from pscnc.models.motivos import RejectionReason

logger = get_logger(__name__)

#: Cuánto se recuerda una clave. Cubre de sobra cualquier reintento razonable sin
#: retener respuestas indefinidamente.
DEFAULT_WINDOW = timedelta(hours=24)


class IdempotencyConflictError(Exception):
    """Misma clave, cuerpo distinto."""

    motivo = RejectionReason.IDEMPOTENCY_CONFLICT


@dataclass(frozen=True, slots=True)
class StoredResponse:
    """Lo que se recuerda de una operación ya ejecutada."""

    status_code: int
    body: dict[str, Any]
    request_sha256: str
    stored_at: datetime

    def vigente(self, ahora: datetime, ventana: timedelta) -> bool:
        return ahora - self.stored_at < ventana


class IdempotencyStore(Protocol):
    """Contrato del almacén. En producción, DynamoDB con TTL nativo."""

    def obtener(self, clave: str) -> StoredResponse | None: ...

    def guardar(self, clave: str, respuesta: StoredResponse) -> None: ...


class InMemoryIdempotencyStore:
    """Implementación para desarrollo y pruebas.

    No sirve en producción con más de una instancia: dos réplicas no comparten
    memoria, así que un reintento que caiga en otra instancia no encontraría la
    clave y emitiría un acta nueva. El almacén real es DynamoDB.
    """

    def __init__(self) -> None:
        self._datos: dict[str, StoredResponse] = {}

    def obtener(self, clave: str) -> StoredResponse | None:
        return self._datos.get(clave)

    def guardar(self, clave: str, respuesta: StoredResponse) -> None:
        self._datos[clave] = respuesta


def request_fingerprint(tenant_id: str, ruta: str, cuerpo: bytes) -> str:
    """Huella de la petición, para detectar el mismo `Idempotency-Key` con otro cuerpo.

    Incluye el inquilino y la ruta: dos tenants pueden elegir la misma clave sin
    saberlo, y sin el inquilino en la huella uno recibiría la respuesta del otro.
    """
    material = f"{tenant_id}\n{ruta}\n".encode() + cuerpo
    return hashlib.sha256(material).hexdigest()


class IdempotencyControl:
    """Resuelve si una operación ya se ejecutó, y con qué resultado."""

    def __init__(self, almacen: IdempotencyStore, *, ventana: timedelta = DEFAULT_WINDOW) -> None:
        self._almacen = almacen
        self._ventana = ventana

    @staticmethod
    def clave_completa(tenant_id: str, clave: str) -> str:
        """Clave con espacio de nombres por inquilino.

        Sin esto, dos tenants que eligieran la misma clave compartirían respuesta:
        una fuga de datos entre clientes por una colisión de nombres.
        """
        return f"{tenant_id}:{clave}"

    def recuperar(
        self, *, tenant_id: str, clave: str, ruta: str, cuerpo: bytes
    ) -> StoredResponse | None:
        """Devuelve la respuesta previa, si la operación ya se ejecutó.

        Lanza `IdempotencyConflictError` si la clave se reutilizó con otro cuerpo.
        """
        guardada = self._almacen.obtener(self.clave_completa(tenant_id, clave))
        if guardada is None:
            return None

        if not guardada.vigente(datetime.now(UTC), self._ventana):
            # Fuera de ventana la clave se considera libre: retener respuestas
            # indefinidamente convertiría el almacén en un registro paralelo de
            # toda la actividad del servicio.
            return None

        huella = request_fingerprint(tenant_id, ruta, cuerpo)
        if huella != guardada.request_sha256:
            logger.warning(
                "idempotency_conflict",
                tenant_id=tenant_id,
                ruta=ruta,
                clave_sha256=hashlib.sha256(clave.encode()).hexdigest()[:16],
            )
            raise IdempotencyConflictError(
                "La clave de idempotencia ya se usó con un cuerpo distinto."
            )

        logger.info("idempotency_replay", tenant_id=tenant_id, ruta=ruta)
        return guardada

    def registrar(
        self,
        *,
        tenant_id: str,
        clave: str,
        ruta: str,
        cuerpo: bytes,
        status_code: int,
        body: dict[str, Any],
    ) -> None:
        """Recuerda el resultado de una operación ejecutada con éxito."""
        self._almacen.guardar(
            self.clave_completa(tenant_id, clave),
            StoredResponse(
                status_code=status_code,
                body=body,
                request_sha256=request_fingerprint(tenant_id, ruta, cuerpo),
                stored_at=datetime.now(UTC),
            ),
        )
