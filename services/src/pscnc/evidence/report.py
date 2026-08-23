"""Generación del Expediente de Evidencias (Audit Trail en PDF).

Este documento es la pieza que se presenta ante un juzgado cuando el firmante
desconoce su firma. Está organizado según las cuatro preguntas que responde una
pericia informática —quién, con qué voluntad, desde dónde y sobre qué documento—
y cada afirmación se acompaña del dato técnico que la respalda.

Pendiente declarado: el sellado del expediente con un **Sello Electrónico
Cualificado de persona jurídica** requiere un certificado de sello contratado con
un PCSC cualificado paraguayo. Mientras no exista, el expediente se entrega
firmado con la CA intermedia del propio prestador, lo que aporta integridad pero
no la autonomía probatoria del Art. 63 de la Ley N.º 6822/2021.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from pscnc.logging_setup import get_logger
from pscnc.models.audit_trail import AuditTrailItem

logger = get_logger(__name__)

_AZUL = colors.HexColor("#1E3A5F")
_GRIS = colors.HexColor("#F1F5F9")
_BORDE = colors.HexColor("#CBD5E1")


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "TituloPSCNC",
            parent=base["Title"],
            fontSize=16,
            textColor=_AZUL,
            spaceAfter=4,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloPSCNC",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#475569"),
            spaceAfter=12,
        ),
        "seccion": ParagraphStyle(
            "SeccionPSCNC",
            parent=base["Heading2"],
            fontSize=11.5,
            textColor=_AZUL,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "cuerpo": ParagraphStyle(
            "CuerpoPSCNC",
            parent=base["Normal"],
            fontSize=8.5,
            leading=12,
            alignment=TA_JUSTIFY,
        ),
        "mono": ParagraphStyle(
            "MonoPSCNC",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=7,
            leading=9,
        ),
    }


def _tabla(filas: list[tuple[str, str]], estilos: dict[str, ParagraphStyle]) -> Table:
    datos = [
        [Paragraph(f"<b>{clave}</b>", estilos["cuerpo"]), Paragraph(valor, estilos["mono"])]
        for clave, valor in filas
    ]
    tabla = Table(datos, colWidths=[55 * mm, 110 * mm])
    tabla.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDE),
                ("BACKGROUND", (0, 0), (0, -1), _GRIS),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabla


def _fecha(valor: datetime | None) -> str:
    if valor is None:
        return "—"
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _pie(canvas: object, documento: object) -> None:
    canvas.saveState()  # type: ignore[attr-defined]
    canvas.setFont("Helvetica", 7)  # type: ignore[attr-defined]
    canvas.setFillColor(colors.HexColor("#64748B"))  # type: ignore[attr-defined]
    canvas.drawString(  # type: ignore[attr-defined]
        20 * mm,
        12 * mm,
        "Expediente de evidencias — Prestador de Servicios de Confianza No Cualificado "
        "(Ley N.º 6822/2021, Paraguay)",
    )
    canvas.drawRightString(190 * mm, 12 * mm, f"Página {documento.page}")  # type: ignore[attr-defined]
    canvas.restoreState()  # type: ignore[attr-defined]


def build_evidence_report(item: AuditTrailItem) -> bytes:
    """Construye el expediente de evidencias en PDF a partir del ítem de auditoría."""
    estilos = _estilos()
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Expediente de evidencias {item.transaction_id}",
        author="PSCNC Paraguay",
        subject="Pista de auditoría de firma electrónica no cualificada",
    )

    identidad = item.identity_evidence
    red = item.network_evidence
    cripto = item.cryptographic_evidence
    consentimiento = item.consent_evidence

    flujo: list[object] = [
        Paragraph("Expediente de Evidencias Técnicas", estilos["titulo"]),
        Paragraph(
            "Documento generado automáticamente por la plataforma del Prestador de Servicios "
            "de Confianza No Cualificado. Contiene la pista de auditoría de una firma "
            "electrónica no cualificada conforme a la Ley N.º 6822/2021 y su Decreto "
            "Reglamentario N.º 7576/2022.",
            estilos["subtitulo"],
        ),
        _tabla(
            [
                ("Identificador de transacción", item.transaction_id),
                ("Cliente B2B", item.b2b_client_id),
                ("Estado", item.status.value),
                ("Documento original", item.document_filename or "—"),
                ("Inicio de la sesión", _fecha(item.created_at)),
                ("Finalización", _fecha(item.completed_at)),
                ("Generado el", _fecha(datetime.now(UTC))),
            ],
            estilos,
        ),
    ]

    # ------------------------------------------------------------- Identidad
    flujo += [
        Paragraph("1. Identidad del firmante — ¿quién firmó?", estilos["seccion"]),
        Paragraph(
            "Datos obtenidos del proceso de verificación de identidad con lectura óptica del "
            "documento, comparación biométrica facial uno a uno contra la fotografía del "
            "documento y prueba de vida activa.",
            estilos["cuerpo"],
        ),
        Spacer(1, 4),
        _tabla(
            [
                ("Nombre completo", identidad.full_name),
                ("Tipo de documento", identidad.document_type),
                ("Número de documento", identidad.national_id),
                ("Fecha de nacimiento", identidad.birth_date.isoformat()),
                ("Coincidencia biométrica", f"{identidad.facial_match_score * 100:.2f} %"),
                ("Prueba de vida", "Aprobada" if identidad.liveness_detected else "NO ACREDITADA"),
                ("Confianza del OCR", f"{identidad.ocr_confidence * 100:.2f} %"),
                ("MRZ leída", identidad.ocr_mrz_raw),
                ("Proveedor de verificación", identidad.verification_partner_id),
                (
                    "Contraste AML/PEP",
                    identidad.aml_pep_result or ("Realizado" if identidad.aml_pep_checked else "—"),
                ),
            ],
            estilos,
        ),
    ]

    # -------------------------------------------------------- Consentimiento
    flujo += [Paragraph("2. Voluntad y control exclusivo — ¿quiso firmar?", estilos["seccion"])]
    if consentimiento is not None:
        flujo += [
            Paragraph(
                "El firmante aceptó de forma expresa la declaración transcrita y verificó un "
                "código de un solo uso enviado a un canal de su posesión. El código no se "
                "almacena en claro: solo se conserva su huella criptográfica.",
                estilos["cuerpo"],
            ),
            Spacer(1, 4),
            _tabla(
                [("Declaración aceptada", consentimiento.consent_statement)]
                + [
                    fila
                    for canal in consentimiento.otp_channels
                    for fila in (
                        (f"Canal {canal.channel_type}", canal.destination),
                        ("  Enviado", _fecha(canal.otp_sent_timestamp)),
                        ("  Verificado", _fecha(canal.otp_verified_timestamp)),
                        ("  ID del proveedor", canal.provider_message_id),
                        ("  Hash SHA-256 del código", canal.otp_code_hash),
                    )
                ],
                estilos,
            ),
        ]
    else:
        flujo.append(Paragraph("Sin evidencia de consentimiento registrada.", estilos["cuerpo"]))

    # -------------------------------------------------------------------- Red
    flujo += [
        Paragraph("3. Entorno de conexión — ¿desde dónde se firmó?", estilos["seccion"]),
        _tabla(
            [
                ("Dirección IP pública", red.client_ip),
                ("Puerto de origen", str(red.source_port)),
                ("Agente de usuario", red.user_agent),
                ("Versión TLS", red.tls_version),
                ("Suite criptográfica", red.tls_cipher),
                (
                    "Geolocalización estimada",
                    (
                        f"{red.geolocation.city or '—'}, {red.geolocation.country_code} "
                        f"(ISP: {red.geolocation.isp or '—'})"
                        if red.geolocation
                        else "—"
                    ),
                ),
            ],
            estilos,
        ),
        Paragraph(
            "La geolocalización por dirección IP es orientativa y no constituye por sí sola "
            "prueba de la ubicación física del firmante.",
            estilos["cuerpo"],
        ),
    ]

    # ----------------------------------------------------------- Criptografía
    flujo.append(PageBreak())
    flujo.append(
        Paragraph("4. Integridad del documento — ¿qué se firmó y cuándo?", estilos["seccion"])
    )
    if cripto is not None:
        flujo += [
            KeepTogether(
                [
                    _tabla(
                        [
                            ("Hash SHA-256 del PDF original", cripto.original_pdf_sha256),
                            ("Hash SHA-256 del PDF firmado", cripto.signed_pdf_sha256),
                            ("Formato de firma", cripto.signature_format),
                            ("Algoritmo de firma", cripto.signature_algorithm),
                            ("Algoritmo de resumen", cripto.digest_algorithm),
                            ("Serie del certificado del firmante", cripto.user_certificate_serial),
                            ("Serie de la CA intermedia", cripto.ca_intermediate_serial),
                        ],
                        estilos,
                    )
                ]
            ),
            Paragraph("Sello de tiempo cualificado (RFC 3161)", estilos["seccion"]),
            Paragraph(
                "La fecha cierta proviene de una Autoridad de Sellado de Tiempo operada por un "
                "Prestador Cualificado de Servicios de Confianza, con independencia del reloj de "
                "los servidores de esta plataforma.",
                estilos["cuerpo"],
            ),
            Spacer(1, 4),
            _tabla(
                [
                    ("Autoridad de sellado", cripto.tsa_evidence.tsa_provider_name),
                    ("Hora oficial del sello", _fecha(cripto.tsa_evidence.timestamp_utc)),
                    ("Número de serie del token", cripto.tsa_evidence.tsa_serial_number or "—"),
                    (
                        "Token RFC 3161 (Base64, truncado)",
                        cripto.tsa_evidence.rfc3161_response_base64[:512] + "…",
                    ),
                ],
                estilos,
            ),
        ]
    else:
        flujo.append(Paragraph("Sin evidencia criptográfica registrada.", estilos["cuerpo"]))

    # ------------------------------------------------------------ Advertencia
    flujo += [
        Paragraph("5. Alcance y limitaciones de este expediente", estilos["seccion"]),
        Paragraph(
            "Este expediente acredita el proceso técnico ejecutado por el prestador. La firma "
            "documentada es una <b>firma electrónica no cualificada</b>: goza de validez "
            "jurídica por el principio de no discriminación (Art. 39 de la Ley N.º 6822/2021), "
            "pero no de la presunción legal de autoría propia de la firma cualificada. Su "
            "eficacia probatoria se apoya en los elementos aquí documentados, sujetos a la "
            "valoración del juzgador y, en su caso, a pericia informática. "
            "El prestador conserva estos registros por el plazo mínimo exigido por la "
            "normativa vigente, en almacenamiento inmutable de tipo WORM.",
            estilos["cuerpo"],
        ),
    ]

    documento.build(flujo, onFirstPage=_pie, onLaterPages=_pie)
    contenido = buffer.getvalue()

    logger.info(
        "evidence_report_built",
        transaction_id=item.transaction_id,
        bytes=len(contenido),
    )
    return contenido
