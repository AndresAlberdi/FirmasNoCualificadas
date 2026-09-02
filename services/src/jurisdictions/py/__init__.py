"""Perfil de la República del Paraguay.

Fuentes de cada valor, para que un revisor pueda contrastarlas:

* **Ley N.º 6822/2021** — servicios de confianza, documento electrónico y documentos
  transmisibles electrónicos. Art. 39: principio de no discriminación, que da validez
  a la firma no cualificada. Art. 15: deber de comunicar el inicio de actividades.
* **Decreto Reglamentario N.º 7576/2022** — art. 6: notificación de incidentes en 24 h.
* **Resolución MIC N.º 262/2024** (`DOC-ICPP-20 v2.0`) — perfil del certificado del
  prestador no cualificado, de donde salen el `serialNumber` y el país del sujeto.
* **Resolución SS.SG. N.º 210/2025** — arts. 4 y 9: la norma que habilita la firma
  simple del proponente en seguros y fija la conservación de la evidencia.

**Advertencia registrada en `docs/PENDIENTES.md` §2:** estas citas provienen de los
documentos de análisis de `docs/diseno/`, no del texto oficial de cada norma, que
todavía no está en el repositorio.
"""

from __future__ import annotations

from types import MappingProxyType

from jurisdictions.profile import (
    DocumentType,
    EvidenceRetention,
    JurisdictionProfile,
    LegalActRestrictions,
    Regulator,
    TimestampAuthority,
)
from jurisdictions.py.textos import TEXTOS

# Términos que indican actos con forma solemne o excluidos de la firma simple.
# Normalizados: minúsculas, sin acentos. Revisión legal obligatoria antes de cada
# modificación (L-01 de docs/PENDIENTES.md).
ACTOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        "testamento",
        "acto de ultima voluntad",
        "sucesion",
        "hipoteca",
        "prenda con registro",
        "donacion",
        "escritura publica",
        "compraventa de inmueble",
        "transferencia de inmueble",
        "usufructo",
        "matrimonio",
        "capitulaciones matrimoniales",
        "divorcio",
        "adopcion",
        "reconocimiento de filiacion",
        "poder general",
        "poder especial para juicios",
        "constitucion de sociedad anonima",
        "cesion de derechos hereditarios",
        "fideicomiso",
    }
)

# Términos que exigen revisión humana pero no bloquean automáticamente.
ACTOS_CON_ADVERTENCIA: frozenset[str] = frozenset(
    {
        "aval",
        "fianza solidaria",
        "pagare",
        "contrato de trabajo",
        "renuncia de derechos",
        "confesion de deuda",
    }
)

PERFIL = JurisdictionProfile(
    code="PY",
    name="República del Paraguay",
    signature_law_citation="Res. SS.SG. N.º 210/2025, arts. 4 y 9",
    signature_law_name="Ley N.º 6822/2021",
    document_types=(
        DocumentType(
            code="CI_PY",
            label="cédula de identidad paraguaya",
            # Solo formato. El dígito verificador no se comprueba (T-03).
            pattern=r"[0-9]{4,15}",
        ),
        DocumentType(
            code="PASAPORTE",
            label="pasaporte",
            pattern=r"[A-Z0-9]{6,15}",
        ),
    ),
    certificate_serial_prefix="PY",
    certificate_country="PY",
    retention=EvidenceRetention(
        # Dos años desde el vencimiento del contrato (Res. 210/2025 art. 9). En la
        # práctica, la retención de S3 Object Lock se fija sobre el objeto y no sobre
        # el contrato, así que el mínimo operativo es mayor: se toman tres años para
        # cubrir la vigencia del contrato más los dos años posteriores.
        minimum_days=1095,
        counted_from="el vencimiento del contrato firmado",
        legal_basis="Res. SS.SG. N.º 210/2025, art. 9",
    ),
    restrictions=LegalActRestrictions(
        excluded=ACTOS_EXCLUIDOS,
        warning=ACTOS_CON_ADVERTENCIA,
    ),
    regulator=Regulator(
        name="Dirección General de Firma Digital y Comercio Electrónico",
        short_name="DGFDCE",
        contact="info-dgce@mic.gov.py",
        incident_notification_hours=24,
        incident_response_team="CERT-Py (MITIC)",
    ),
    timestamp_authorities=(
        # Prestadores cualificados habilitados por el MIC. Ninguno está contratado
        # todavía (B-01 de docs/PENDIENTES.md).
        TimestampAuthority(name="Confirma S.A.", qualified=True),
        TimestampAuthority(name="VIT S.A. (eFirma)", qualified=True),
        TimestampAuthority(name="CODE 100 S.A.", qualified=True),
        TimestampAuthority(name="Documenta S.A.", qualified=True),
        TimestampAuthority(name="ITTI S.A.E.C.A.", qualified=True),
        TimestampAuthority(name="SOS Tecnología y Gestión Ltda.", qualified=True),
    ),
    texts=MappingProxyType(TEXTOS),
    # El marco paraguayo es el que sostiene todo el diseño del producto y está
    # documentado en `docs/diseno/`. Queda pendiente incorporar los textos oficiales
    # de cada norma (N-01 a N-03 de docs/PENDIENTES.md).
    legally_validated=True,
)
