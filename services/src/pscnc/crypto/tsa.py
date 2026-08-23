"""Cliente de la Autoridad de Sellado de Tiempo cualificada (RFC 3161).

La fecha cierta es el elemento que sostiene la validez de una firma producida con
un certificado efímero: acredita que el acto ocurrió dentro de la ventana de
vigencia del certificado. Por eso el fallo del sellado es un fallo de la
transacción completa y nunca una degradación silenciosa a PAdES-B-B.

El token obtenido se conserva íntegro en la pista de auditoría (Base64) para que
un perito pueda verificarlo de forma independiente años después.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from asn1crypto import cms, tsp

from pscnc.errors import TimestampError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TimestampResult:
    """Resultado del sellado, listo para volcarse a la evidencia criptográfica."""

    provider_name: str
    token_base64: str
    gen_time: datetime
    serial_number: str
    certificate_chain_pem: list[str]


def _pem(der: bytes) -> str:
    cuerpo = base64.b64encode(der).decode("ascii")
    lineas = [cuerpo[i : i + 64] for i in range(0, len(cuerpo), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lineas) + "\n-----END CERTIFICATE-----\n"


def parse_timestamp_token(token: cms.ContentInfo, *, provider_name: str) -> TimestampResult:
    """Extrae los datos periciales relevantes de un token RFC 3161."""
    try:
        signed_data = token["content"]
        # El contenido encapsulado es un TSTInfo: asn1crypto lo analiza según el
        # content_type declarado, de modo que se accede por `.parsed`.
        tst_info: tsp.TSTInfo = signed_data["encap_content_info"]["content"].parsed
        gen_time = tst_info["gen_time"].native
        serial = str(tst_info["serial_number"].native)
        cadena = [_pem(cert.chosen.dump()) for cert in signed_data["certificates"]]
    except Exception as exc:
        raise TimestampError("Token de sellado de tiempo ilegible o malformado") from exc

    if gen_time.tzinfo is None:
        gen_time = gen_time.replace(tzinfo=UTC)

    return TimestampResult(
        provider_name=provider_name,
        token_base64=base64.b64encode(token.dump()).decode("ascii"),
        gen_time=gen_time,
        serial_number=serial,
        certificate_chain_pem=cadena,
    )


class RecordingTimeStamper:
    """Envoltorio del sellador de pyHanko que retiene el último token obtenido.

    pyHanko incrusta el token en el PDF pero no lo devuelve; se intercepta aquí
    para poder persistirlo en la pista de auditoría sin volver a analizar el
    binario firmado.
    """

    def __init__(
        self,
        url: str,
        *,
        provider_name: str,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 10,
        max_retries: int = 3,
        delegate: object | None = None,
    ) -> None:
        # `delegate` permite inyectar un sellador de pruebas; en producción siempre
        # es nulo y se construye el cliente HTTP contra la TSA cualificada.
        if delegate is None:
            if not url:
                raise TimestampError(
                    "No hay URL de TSA configurada: no se puede otorgar fecha cierta"
                )

            from pyhanko.sign.timestamps import HTTPTimeStamper

            auth = (username, password) if username else None
            delegate = HTTPTimeStamper(
                url=url, https=url.startswith("https"), auth=auth, timeout=timeout
            )

        self._delegate = delegate
        self._provider_name = provider_name
        self._max_retries = max_retries
        self._last_token: cms.ContentInfo | None = None

    # pyHanko invoca este método durante el firmado.
    async def async_timestamp(self, message_digest: bytes, md_algorithm: str) -> cms.ContentInfo:
        ultimo_error: Exception | None = None
        for intento in range(1, self._max_retries + 1):
            try:
                token = await self._delegate.async_timestamp(message_digest, md_algorithm)
            except Exception as exc:
                ultimo_error = exc
                espera = min(2 ** (intento - 1), 8)
                logger.warning(
                    "tsa_request_failed",
                    provider=self._provider_name,
                    attempt=intento,
                    retry_in_seconds=espera,
                    error=str(exc),
                )
                if intento < self._max_retries:
                    time.sleep(espera)
                continue
            self._last_token = token
            logger.info("tsa_token_obtained", provider=self._provider_name, attempt=intento)
            return token

        raise TimestampError(
            "La Autoridad de Sellado de Tiempo cualificada no respondió; "
            "la transacción se cancela para no emitir una firma sin fecha cierta."
        ) from ultimo_error

    def __getattr__(self, item: str) -> object:
        # Delegación transparente del resto de la interfaz de pyHanko.
        return getattr(self._delegate, item)

    @property
    def last_result(self) -> TimestampResult:
        if self._last_token is None:
            raise TimestampError("No se obtuvo ningún token de sellado de tiempo")
        return parse_timestamp_token(self._last_token, provider_name=self._provider_name)
