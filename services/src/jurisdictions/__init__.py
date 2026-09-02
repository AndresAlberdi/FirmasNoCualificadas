"""Registro de perfiles de jurisdicción (ADR-0008).

Punto de entrada único: el resto del código pide un perfil por su código ISO y
nunca importa un perfil concreto. Así, agregar un país es agregar un paquete y una
entrada en este registro — no tocar el motor de firma.

La salvaguarda que hace que esto no sea solo una convención: ``require_profile``
se niega a devolver un perfil sin validación legal fuera de desarrollo. Un perfil
estructural sirve para probar que la arquitectura generaliza; usarlo para firmar
produciría una constancia que cita una norma que nadie verificó.
"""

from __future__ import annotations

from jurisdictions.bo import PERFIL as PERFIL_BO
from jurisdictions.profile import (
    DocumentType,
    EvidenceRetention,
    JurisdictionProfile,
    LegalActRestrictions,
    Regulator,
    TimestampAuthority,
)
from jurisdictions.py import PERFIL as PERFIL_PY

__all__ = [
    "DocumentType",
    "EvidenceRetention",
    "JurisdictionProfile",
    "LegalActRestrictions",
    "Regulator",
    "TimestampAuthority",
    "UnknownJurisdictionError",
    "UnvalidatedJurisdictionError",
    "available",
    "get_profile",
    "require_profile",
]

_PERFILES: dict[str, JurisdictionProfile] = {
    PERFIL_PY.code: PERFIL_PY,
    PERFIL_BO.code: PERFIL_BO,
}

#: Jurisdicción por defecto cuando el tenant no declara ninguna.
DEFAULT_JURISDICTION = "PY"


class UnknownJurisdictionError(ValueError):
    """Se pidió una jurisdicción que no tiene perfil."""


class UnvalidatedJurisdictionError(RuntimeError):
    """Se intentó operar con un perfil que no pasó revisión legal."""


def available() -> tuple[str, ...]:
    """Códigos de las jurisdicciones con perfil, en orden alfabético."""
    return tuple(sorted(_PERFILES))


def get_profile(code: str) -> JurisdictionProfile:
    """Devuelve el perfil de una jurisdicción, validada o no.

    Se usa en pruebas y en herramientas de diagnóstico. Para operar, use
    ``require_profile``.
    """
    try:
        return _PERFILES[code.upper()]
    except KeyError as exc:
        raise UnknownJurisdictionError(
            f"No hay perfil para la jurisdicción {code!r}. Disponibles: {', '.join(available())}"
        ) from exc


def require_profile(code: str, *, environment: str = "prod") -> JurisdictionProfile:
    """Devuelve el perfil exigiendo que sea apto para operar en el entorno dado.

    En ``staging`` y ``prod`` un perfil sin validación legal es un error de
    configuración, no una advertencia: firmar bajo un marco normativo que nadie
    verificó produce una constancia que afirma algo que el prestador no puede
    sostener.
    """
    perfil = get_profile(code)
    if not perfil.legally_validated and environment in ("staging", "prod"):
        raise UnvalidatedJurisdictionError(
            f"El perfil de {perfil.name} ({perfil.code}) no cuenta con validación legal "
            f"y no puede usarse en el entorno {environment!r}. "
            "Vea T-02 en docs/PENDIENTES.md."
        )
    return perfil
