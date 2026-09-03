"""Perfil del Estado Plurinacional de Bolivia — **sin validación legal**.

## Para qué existe

Para demostrar que la generalización del ADR-0008 funciona: que ningún literal
paraguayo quedó fuera de este módulo. Un perfil que solo difiere en el nombre no
probaría nada, así que este difiere en lo que importa — el formato del documento de
identidad admite un complemento alfanumérico (`1234567-1K`), de modo que cualquier
validación que siguiera asumiendo `^[0-9]+$` falla contra él.

## Lo que este perfil NO es

**No es un perfil jurídicamente correcto.** No hay ningún documento normativo
boliviano en este repositorio y el equipo no inventa citas de normas que no leyó.
Cada campo con contenido normativo lleva el prefijo `[SIN VERIFICAR]` y
`legally_validated` es `False`, lo que impide que el servicio opere con él fuera de
desarrollo.

Habilitarlo comercialmente exige, en este orden: incorporar los textos oficiales
bolivianos al repositorio, una revisión de asesoría legal local, y recién entonces
cambiar `legally_validated`. Registrado como T-02 en `docs/PENDIENTES.md`.
"""

from __future__ import annotations

from types import MappingProxyType

from jurisdictions.bo.textos import TEXTOS
from jurisdictions.profile import (
    DocumentType,
    EvidenceRetention,
    JurisdictionProfile,
    LegalActRestrictions,
    Regulator,
)

_SIN_VERIFICAR = "[SIN VERIFICAR] "

# Los actos con forma solemne son parecidos entre ordenamientos de tradición
# continental, pero **parecidos no es igual**: la lista se copia como punto de
# partida estructural y no como afirmación sobre el derecho boliviano.
ACTOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        "testamento",
        "sucesion",
        "hipoteca",
        "donacion",
        "escritura publica",
        "transferencia de inmueble",
        "matrimonio",
        "divorcio",
        "adopcion",
        "reconocimiento de filiacion",
        "poder general",
        "anticretico",  # figura propia del derecho boliviano
    }
)

ACTOS_CON_ADVERTENCIA: frozenset[str] = frozenset(
    {
        "aval",
        "fianza solidaria",
        "pagare",
        "contrato de trabajo",
    }
)

PERFIL = JurisdictionProfile(
    code="BO",
    name="Estado Plurinacional de Bolivia",
    signature_law_citation=_SIN_VERIFICAR + "norma de firma electrónica pendiente de verificación",
    signature_law_name=_SIN_VERIFICAR + "marco normativo pendiente de verificación",
    document_types=(
        DocumentType(
            code="CI_BO",
            label="cédula de identidad boliviana",
            # Admite complemento alfanumérico: `1234567`, `1234567-1K`, `1234567 LP`.
            # Es la diferencia que hace útil este perfil como prueba: una validación
            # que siguiera asumiendo el formato paraguayo lo rechazaría.
            pattern=r"[0-9]{5,10}(?:[- ][A-Z0-9]{1,3})?",
            certificate_prefix="CI",
        ),
        DocumentType(
            code="PASAPORTE",
            label="pasaporte",
            pattern=r"[A-Z0-9]{6,15}",
            certificate_prefix="PAS",
        ),
    ),
    signer_index_prefix="BO",
    certificate_country="BO",
    # Sin verificar, como el resto de los campos normativos de este perfil: no hay
    # constancia de que Bolivia fije estos literales, ni de cuáles serían. Se
    # declaran para que la estructura funcione, y por eso el perfil no opera fuera
    # de desarrollo.
    certificate_subject_organization=_SIN_VERIFICAR + "organizacion del sujeto",
    certificate_subject_organizational_unit=_SIN_VERIFICAR + "unidad organizativa",
    retention=EvidenceRetention(
        # Se toma el mismo mínimo operativo que en Paraguay por prudencia: conservar
        # de más no invalida evidencia, conservar de menos sí. El plazo real depende
        # de la norma boliviana, que está sin verificar.
        minimum_days=1095,
        counted_from=_SIN_VERIFICAR + "plazo pendiente de verificación",
        legal_basis=_SIN_VERIFICAR + "norma pendiente de verificación",
    ),
    restrictions=LegalActRestrictions(
        excluded=ACTOS_EXCLUIDOS,
        warning=ACTOS_CON_ADVERTENCIA,
    ),
    regulator=Regulator(
        name=_SIN_VERIFICAR + "autoridad reguladora pendiente de verificación",
        short_name="—",
        contact="",
        # 24 h es el plazo paraguayo. El boliviano no se verificó; se conserva el más
        # exigente conocido, porque notificar antes de lo debido no incumple nada.
        incident_notification_hours=24,
        incident_response_team=_SIN_VERIFICAR + "equipo de respuesta pendiente",
    ),
    # No se declara ninguna TSA: afirmar que un prestador está habilitado en Bolivia
    # sin haberlo comprobado sería exactamente el tipo de invención que este perfil
    # evita. Sin TSA declarada, el nivel 2 no puede operar en esta jurisdicción.
    timestamp_authorities=(),
    texts=MappingProxyType(TEXTOS),
    legally_validated=False,
)
