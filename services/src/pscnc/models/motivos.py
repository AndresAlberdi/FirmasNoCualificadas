"""Motivos de rechazo del contrato público (ADR-0009).

Todo rechazo de la API devuelve un motivo de este enumerado. **Nunca un mensaje
libre.** La razón es del lado del consumidor: el tenant tiene que poder mapear
cada rechazo a su propia máquina de estados, y un texto que cambia de redacción
entre versiones rompe integraciones sin que cambie una sola firma de función.

El modelo es el de `MotivoRechazoFirmaCliente` del primer tenant, que ya
distingue lo que hay que distinguir: un código incorrecto —donde reintentar tiene
sentido— de un código ya consumido, donde no.

## Regla de evolución

**Agregar un motivo es compatible; cambiar o quitar uno, no.** Un tenant que
recibe un motivo desconocido debe tratarlo como fallo genérico y registrarlo, y
por eso agregar valores no rompe a nadie. Renombrar uno sí: el `match` del tenant
deja de cubrir un caso que antes manejaba, en silencio. Los valores de este
enumerado son parte del contrato tanto como las rutas.
"""

from __future__ import annotations

from enum import StrEnum


class RejectionReason(StrEnum):
    """Motivos estables de rechazo de una operación."""

    # ------------------------------------------------------- Autenticación --
    UNAUTHENTICATED = "UNAUTHENTICATED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    REQUEST_EXPIRED = "REQUEST_EXPIRED"
    TENANT_NOT_ENABLED = "TENANT_NOT_ENABLED"

    # -------------------------------------------------------- Transacción --
    TRANSACTION_NOT_FOUND = "TRANSACTION_NOT_FOUND"
    TRANSACTION_OF_ANOTHER_TENANT = "TRANSACTION_OF_ANOTHER_TENANT"
    TRANSACTION_ALREADY_CONFIRMED = "TRANSACTION_ALREADY_CONFIRMED"
    TRANSACTION_EXPIRED = "TRANSACTION_EXPIRED"
    INVALID_STATE = "INVALID_STATE"

    # ---------------------------------------------------------- Identidad --
    #: El tenant declaró que su verificación de identidad no fue aprobada. FNC no
    #: vuelve a decidir la identidad: asienta la decisión ajena (ADR-0009).
    IDENTITY_NOT_APPROVED = "IDENTITY_NOT_APPROVED"
    INCOMPLETE_IDENTITY_DECISION = "INCOMPLETE_IDENTITY_DECISION"
    #: El nivel 2 necesita el nombre y el apellido por separado, porque el perfil
    #: de certificado los exige como atributos distintos. Partir una sola cadena
    #: sería adivinar, y el error quedaría dentro de un documento probatorio
    #: sin avisar a nadie (ADR-0010).
    INCOMPLETE_SIGNER_NAME = "INCOMPLETE_SIGNER_NAME"

    # --------------------------------------------------------------- OTP ---
    OTP_NOT_VERIFIED = "OTP_NOT_VERIFIED"
    OTP_NOT_FOR_TRANSACTION = "OTP_NOT_FOR_TRANSACTION"
    OTP_INCORRECT_CODE = "OTP_INCORRECT_CODE"
    OTP_ATTEMPTS_EXHAUSTED = "OTP_ATTEMPTS_EXHAUSTED"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_ALREADY_USED = "OTP_ALREADY_USED"

    # ---------------------------------------------------------- Documento --
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    #: La huella recibida no coincide con la registrada al abrir la transacción.
    DOCUMENT_TAMPERED = "DOCUMENT_TAMPERED"
    DOCUMENT_REQUIRED = "DOCUMENT_REQUIRED"
    DOCUMENT_TOO_LARGE = "DOCUMENT_TOO_LARGE"
    #: Acto jurídico excluido de la firma no cualificada en la jurisdicción.
    EXCLUDED_LEGAL_ACT = "EXCLUDED_LEGAL_ACT"

    # ------------------------------------------------------- Jurisdicción --
    UNSUPPORTED_JURISDICTION = "UNSUPPORTED_JURISDICTION"
    INVALID_IDENTITY_DOCUMENT = "INVALID_IDENTITY_DOCUMENT"

    # ------------------------------------------------- Nivel de servicio ---
    #: El nivel pedido excede el que el contrato del tenant habilita.
    SERVICE_LEVEL_NOT_CONTRACTED = "SERVICE_LEVEL_NOT_CONTRACTED"
    #: El nivel 2 necesita el documento y la infraestructura de firma completa.
    SERVICE_LEVEL_UNAVAILABLE = "SERVICE_LEVEL_UNAVAILABLE"

    # ------------------------------------------------------ Idempotencia ---
    #: Misma clave de idempotencia con un cuerpo distinto: no se puede decidir
    #: cuál de las dos peticiones es la buena, así que se rechazan las dos.
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"

    # ------------------------------------------------------------ Sistema --
    SEALING_FAILED = "SEALING_FAILED"
    EVIDENCE_NOT_PERSISTED = "EVIDENCE_NOT_PERSISTED"
    TIMESTAMP_UNAVAILABLE = "TIMESTAMP_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


#: Motivos ante los cuales reintentar la misma operación puede tener sentido.
#: Se declara explícitamente para que el SDK no tenga que inferirlo de la forma
#: del nombre, que es frágil.
RETRYABLE_REASONS: frozenset[RejectionReason] = frozenset(
    {
        RejectionReason.OTP_INCORRECT_CODE,
        RejectionReason.TIMESTAMP_UNAVAILABLE,
        RejectionReason.INTERNAL_ERROR,
    }
)

#: Motivos que indican que el acto ya se consumió y **no** debe reintentarse: el
#: OTP es de un solo uso, y volver a pedirlo con el mismo código no lo revive.
TERMINAL_REASONS: frozenset[RejectionReason] = frozenset(
    {
        RejectionReason.OTP_ALREADY_USED,
        RejectionReason.OTP_ATTEMPTS_EXHAUSTED,
        RejectionReason.OTP_EXPIRED,
        RejectionReason.TRANSACTION_EXPIRED,
        RejectionReason.EXCLUDED_LEGAL_ACT,
        RejectionReason.IDENTITY_NOT_APPROVED,
    }
)
