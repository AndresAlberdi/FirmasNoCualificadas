"""Claves de KMS propias de cada inquilino (ADR-0006).

Dos claves por inquilino, con funciones distintas:

* **Sello de acta** (`ECC_NIST_P256`): firma el hash canónico del acta de
  evidencia. Su clave pública se publica, de modo que el inquilino y cualquier
  tercero pueden verificar el sello sin acceso a nuestros registros. Es lo que
  hace verificable al nivel 1, donde el documento no se modifica.
* **Cifrado de evidencias** (simétrica): cifrado envolvente de los datos en
  reposo.

Dos invariantes que este módulo hace cumplir, y por qué:

1. **La clave se nombra siempre por alias versionado, nunca por identificador**
   (regla inviolable 9). Un identificador fijo convierte cada rotación en un
   despliegue, y durante el solapamiento hacen falta las dos claves a la vez —la
   anterior verificando, la nueva firmando—, algo que un identificador no permite
   expresar. El alias viaja además como `kid` del sobre JWS, así que un
   verificador sabe con qué clave pública comprobar el sello.

2. **Toda operación de cifrado lleva el contexto del inquilino y la transacción**
   (regla inviolable 10). La política de la clave lo exige, de modo que un texto
   cifrado del inquilino A no puede descifrarse en el contexto del inquilino B
   aunque el llamador tenga permisos sobre ambas claves. Es el aislamiento del
   ADR-0005 llevado a la capa criptográfica, donde un error de enrutamiento en el
   código no puede eludirlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Literal

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from pscnc.errors import PscncError, SigningError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)

#: Algoritmo del sello. `ES256` en la nomenclatura JOSE. El tipo es un `Literal`
#: porque el cliente de KMS solo admite el catálogo cerrado de algoritmos que
#: soporta: así, un valor equivocado se detecta al verificar tipos y no en la
#: primera llamada real al servicio.
ALGORITMO_SELLO: Final[Literal["ECDSA_SHA_256"]] = "ECDSA_SHA_256"

#: Formato del identificador de inquilino, alineado con `b2b_client_id`.
PATRON_TENANT = re.compile(r"^[a-zA-Z0-9_.-]{2,40}$")


class TenantKeyError(PscncError):
    """Error en la resolución o el uso de una clave de inquilino."""

    http_status = 500
    code = "tenant_key_error"


class CrossTenantKeyAccessError(TenantKeyError):
    """Se intentó usar la clave de un inquilino en el contexto de otro.

    No es un error de programación cualquiera: es el aislamiento del ADR-0005
    deteniendo una operación que habría cruzado datos entre clientes.
    """

    http_status = 403
    code = "cross_tenant_key_access"


@dataclass(frozen=True, slots=True)
class KeyAliases:
    """Los alias versionados de un inquilino en un entorno."""

    tenant_id: str
    environment: str
    acta_seal_version: int = 1
    evidence_version: int = 1

    def __post_init__(self) -> None:
        if not PATRON_TENANT.match(self.tenant_id):
            raise TenantKeyError(f"Identificador de inquilino inválido: {self.tenant_id!r}")

    @property
    def acta_seal(self) -> str:
        return f"alias/fnc/{self.environment}/{self.tenant_id}/acta-seal/v{self.acta_seal_version}"

    @property
    def evidence(self) -> str:
        return f"alias/fnc/{self.environment}/{self.tenant_id}/evidence/v{self.evidence_version}"


@dataclass(frozen=True, slots=True)
class SealResult:
    """Firma producida por KMS sobre el hash canónico de un acta."""

    signature: bytes
    #: Alias versionado usado. Viaja como `kid` del sobre JWS.
    key_alias: str
    algorithm: str = ALGORITMO_SELLO


class TenantKeyRing:
    """Acceso a las claves de un inquilino, siempre por alias.

    Una instancia atiende a **un solo inquilino**: el identificador se fija al
    construirla y todas las operaciones lo llevan. Así, pedirle una operación
    sobre otro inquilino es un error explícito y no un dato que se cuela por un
    parámetro.
    """

    def __init__(
        self,
        tenant_id: str,
        *,
        environment: str,
        region: str,
        acta_seal_version: int = 1,
        evidence_version: int = 1,
        client: Any | None = None,
    ) -> None:
        self._aliases = KeyAliases(
            tenant_id=tenant_id,
            environment=environment,
            acta_seal_version=acta_seal_version,
            evidence_version=evidence_version,
        )
        self._client = client or boto3.client(
            "kms",
            region_name=region,
            config=BotoConfig(retries={"max_attempts": 5, "mode": "standard"}),
        )

    @property
    def tenant_id(self) -> str:
        return self._aliases.tenant_id

    @property
    def acta_seal_alias(self) -> str:
        return self._aliases.acta_seal

    @property
    def evidence_alias(self) -> str:
        return self._aliases.evidence

    # ------------------------------------------------------ Sello del acta ---
    def seal(self, digest: bytes) -> SealResult:
        """Firma un digest SHA-256 con la clave de sello del inquilino.

        Se envía el digest y no el acta completa: además de ser el modo correcto
        para datos de tamaño arbitrario, evita transmitir el contenido.
        """
        if len(digest) != 32:
            raise TenantKeyError("Se esperaba un digest SHA-256 de 32 bytes")

        try:
            respuesta = self._client.sign(
                KeyId=self._aliases.acta_seal,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm=ALGORITMO_SELLO,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error(
                "acta_seal_failed", tenant_id=self.tenant_id, alias=self._aliases.acta_seal
            )
            raise SigningError("No se pudo sellar el acta de evidencia") from exc

        logger.info("acta_sealed", tenant_id=self.tenant_id, key_alias=self._aliases.acta_seal)
        return SealResult(
            signature=bytes(respuesta["Signature"]), key_alias=self._aliases.acta_seal
        )

    def public_key_der(self) -> bytes:
        """Clave pública del sello, en `SubjectPublicKeyInfo` DER.

        Es lo que se publica en `/.well-known/fnc-keys.json` para que un tercero
        verifique el acta sin depender de nosotros.
        """
        try:
            respuesta = self._client.get_public_key(KeyId=self._aliases.acta_seal)
        except (ClientError, BotoCoreError) as exc:
            raise TenantKeyError("No se pudo obtener la clave pública de sello") from exc
        return bytes(respuesta["PublicKey"])

    # ------------------------------------------------ Cifrado de evidencia ---
    def encryption_context(self, transaction_id: str) -> dict[str, str]:
        """Contexto de cifrado exigido por la política de la clave.

        Va autenticado con el texto cifrado: cambiarlo invalida el descifrado.
        Por eso liga cada objeto cifrado a su inquilino y a su transacción sin
        depender de que el código recuerde comprobarlo.
        """
        if not transaction_id:
            raise TenantKeyError(
                "El contexto de cifrado exige el identificador de la transacción: "
                "sin él, una operación no puede rastrearse hasta el acto que la originó."
            )
        return {"tenant_id": self.tenant_id, "transaction_id": transaction_id}

    def encrypt(self, plaintext: bytes, *, transaction_id: str) -> bytes:
        """Cifra un dato sensible con la clave del inquilino."""
        try:
            respuesta = self._client.encrypt(
                KeyId=self._aliases.evidence,
                Plaintext=plaintext,
                EncryptionContext=self.encryption_context(transaction_id),
            )
        except (ClientError, BotoCoreError) as exc:
            raise TenantKeyError("No se pudo cifrar el dato de evidencia") from exc
        return bytes(respuesta["CiphertextBlob"])

    def decrypt(self, ciphertext: bytes, *, transaction_id: str) -> bytes:
        """Descifra un dato de este inquilino y esta transacción.

        Si el texto cifrado pertenece a otro inquilino, KMS rechaza la operación
        porque el contexto autenticado no coincide. El error se traduce a
        `CrossTenantKeyAccessError` para que quede registrado como lo que es —un
        intento de acceso cruzado— y no como un fallo genérico de descifrado.
        """
        contexto = self.encryption_context(transaction_id)
        try:
            respuesta = self._client.decrypt(
                KeyId=self._aliases.evidence,
                CiphertextBlob=ciphertext,
                EncryptionContext=contexto,
            )
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code", "")
            if codigo in ("InvalidCiphertextException", "IncorrectKeyException", "AccessDenied"):
                logger.warning(
                    "cross_tenant_decrypt_blocked",
                    tenant_id=self.tenant_id,
                    transaction_id=transaction_id,
                    error_code=codigo,
                )
                raise CrossTenantKeyAccessError(
                    "El dato cifrado no pertenece a este inquilino o a esta transacción"
                ) from exc
            raise TenantKeyError("No se pudo descifrar el dato de evidencia") from exc
        except BotoCoreError as exc:
            raise TenantKeyError("No se pudo descifrar el dato de evidencia") from exc

        return bytes(respuesta["Plaintext"])
