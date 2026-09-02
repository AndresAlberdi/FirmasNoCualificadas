"""Pruebas del agente de cumplimiento legal."""

from __future__ import annotations

import pytest

from pscnc.compliance.legal_guard import (
    ComplianceVerdict,
    LegalGuard,
    enforce_biometric_threshold,
    normalizar,
)
from pscnc.errors import BiometricThresholdError, LegallyExcludedDocumentError


def test_normaliza_acentos_y_mayusculas() -> None:
    assert normalizar("CONSTITUCIÓN  de   Sociedad") == "constitucion de sociedad"


def test_bloquea_acto_excluido() -> None:
    guard = LegalGuard.for_jurisdiction("PY")
    veredicto = guard.evaluate_text(
        "Por el presente instrumento se constituye HIPOTECA sobre el inmueble."
    )
    assert veredicto.allowed is False
    assert "hipoteca" in veredicto.blocking_terms


def test_bloquea_pese_a_los_acentos() -> None:
    """La detección no puede depender de la acentuación del documento."""
    guard = LegalGuard.for_jurisdiction("PY")
    veredicto = guard.evaluate_text("Escritura Pública de donación entre vivos")
    assert veredicto.allowed is False
    assert {"escritura publica", "donacion"} <= set(veredicto.blocking_terms)


def test_permite_contrato_ordinario() -> None:
    guard = LegalGuard.for_jurisdiction("PY")
    veredicto = guard.evaluate_text(
        "Contrato de prestacion de servicios de consultoria por doce meses."
    )
    assert veredicto.allowed is True
    assert veredicto.blocking_terms == ()


def test_marca_para_revision_sin_bloquear() -> None:
    guard = LegalGuard.for_jurisdiction("PY")
    veredicto = guard.evaluate_text("El deudor suscribe un pagare a la orden.")
    assert veredicto.allowed is True
    assert veredicto.requires_human_review is True
    assert "pagare" in veredicto.warning_terms


def test_enforce_lanza_excepcion_con_detalle() -> None:
    guard = LegalGuard.for_jurisdiction("PY")
    veredicto = guard.evaluate_text("Testamento ológrafo del causante.")
    with pytest.raises(LegallyExcludedDocumentError) as excepcion:
        guard.enforce(veredicto, transaction_id="tx-1")
    assert "testamento" in excepcion.value.detail["blocking_terms"]


def test_documento_sin_texto_extraible_no_bloquea_pero_se_marca() -> None:
    """Un PDF escaneado no puede analizarse léxicamente: se marca para revisión."""
    guard = LegalGuard.for_jurisdiction("PY")
    veredicto = guard.evaluate_pdf(b"esto no es un pdf")
    assert isinstance(veredicto, ComplianceVerdict)
    assert veredicto.allowed is True
    assert veredicto.text_extraction_succeeded is False
    assert veredicto.requires_human_review is True


def test_politica_estricta_bloquea_si_no_hay_texto() -> None:
    guard = LegalGuard.for_jurisdiction("PY", block_on_extraction_failure=True)
    with pytest.raises(LegallyExcludedDocumentError):
        guard.evaluate_pdf(b"esto no es un pdf")


def test_umbral_biometrico_rechaza_por_debajo_del_minimo() -> None:
    with pytest.raises(BiometricThresholdError):
        enforce_biometric_threshold(0.93, minimum=0.95, liveness_detected=True)


def test_umbral_biometrico_rechaza_sin_prueba_de_vida() -> None:
    with pytest.raises(BiometricThresholdError, match="prueba de vida"):
        enforce_biometric_threshold(0.99, minimum=0.95, liveness_detected=False)


def test_umbral_biometrico_acepta_caso_valido() -> None:
    enforce_biometric_threshold(0.985, minimum=0.95, liveness_detected=True)
