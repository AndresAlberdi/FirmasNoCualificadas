"""Logging estructurado con redacción obligatoria de datos personales.

Regla del proyecto: ningún número de cédula, teléfono, correo, código OTP ni
imagen biométrica puede aparecer completo en un log. La redacción se aplica en
el procesador, no en cada punto de llamada, para que no dependa de la disciplina
del desarrollador.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_CAMPOS_SENSIBLES = frozenset(
    {
        "national_id",
        "cedula",
        "ocr_mrz_raw",
        "destination",
        "phone",
        "email",
        "otp_code",
        "consent_otp_code",
        "selfie",
        "selfie_image",
        "document_image",
        "password",
        "api_key",
        "secret",
        "authorization",
        "tsa_password",
    }
)

_PATRON_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PATRON_TELEFONO = re.compile(r"\+?\d{8,15}")


def enmascarar_identificador(valor: str, visibles: int = 3) -> str:
    """Enmascara un identificador dejando visibles los primeros dígitos.

    >>> enmascarar_identificador("4829153")
    '482****'
    """
    if not valor:
        return ""
    if len(valor) <= visibles:
        return "*" * len(valor)
    return valor[:visibles] + "*" * (len(valor) - visibles)


def _redactar(
    _logger: object, _metodo: str, evento: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Procesador de structlog que enmascara PII antes de emitir el registro."""
    for clave, valor in list(evento.items()):
        clave_normalizada = clave.lower()
        if clave_normalizada in _CAMPOS_SENSIBLES:
            evento[clave] = enmascarar_identificador(str(valor)) if valor else None
        elif isinstance(valor, str):
            valor = _PATRON_EMAIL.sub("<email>", valor)
            evento[clave] = _PATRON_TELEFONO.sub(
                lambda m: enmascarar_identificador(m.group(0), visibles=4), valor
            )
    return evento


def configurar_logging(nivel: str = "INFO", *, json_output: bool = True) -> None:
    """Inicializa structlog. Debe invocarse una sola vez al arrancar el proceso."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, nivel.upper(), logging.INFO),
    )

    procesadores: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redactar,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    procesadores.append(
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=procesadores,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, nivel.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(nombre: str) -> Any:
    """Devuelve un logger estructurado."""
    return structlog.get_logger(nombre)
