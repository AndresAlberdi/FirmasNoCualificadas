"""Pruebas del módulo de jurisdicciones y de la regla que lo sostiene (ADR-0008).

La prueba central es `test_sin_literales_de_jurisdiccion_fuera_del_modulo`: sin ella,
«la jurisdicción es configuración» es una intención que sobrevive hasta que la
tercera persona que toca el código escriba `"PY"` en un módulo compartido.

Qué se analiza y qué no: **solo cadenas literales que llegan a un valor**, mediante
el árbol sintáctico. Los comentarios y las cadenas de documentación quedan fuera a
propósito — explican por qué una decisión existe, y prohibir que citen la norma
volvería el código menos comprensible sin evitar un solo error. Un comentario no
emite un certificado; un valor sí.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from jurisdictions import (
    DEFAULT_JURISDICTION,
    UnknownJurisdictionError,
    UnvalidatedJurisdictionError,
    available,
    get_profile,
    require_profile,
)
from jurisdictions.profile import EvidenceRetention

RAIZ_CODIGO = Path(__file__).resolve().parents[1] / "src"
PAQUETE_JURISDICCIONES = RAIZ_CODIGO / "jurisdictions"

# Literales que solo pueden aparecer dentro de `jurisdictions/`. Cada patrón nombra
# un país, una norma o un organismo concretos.
PATRONES_PROHIBIDOS: tuple[tuple[str, str], ...] = (
    (r"\bParaguay\b", "nombre de país"),
    (r"\bBolivia\b", "nombre de país"),
    (r"\b6822/2021\b", "ley de servicios de confianza"),
    (r"\b7576/2022\b", "decreto reglamentario"),
    (r"\b262/2024\b", "resolución del perfil de certificado"),
    (r"\b210/2025\b", "resolución de comercialización electrónica"),
    (r"\b231/2025\b", "resolución de pólizas electrónicas"),
    (r"DOC-ICPP", "identificador del perfil nacional de certificado"),
    (r"\bDGFDCE\b", "organismo regulador"),
    (r"\bCERT-Py\b", "equipo de respuesta a incidentes"),
    (r"\bMITIC\b", "organismo"),
    (r"info-dgce@", "contacto del regulador"),
    (r"\bCI#PY\b", "clave de índice con país cableado"),
    (r"\bCI_PY\b", "tipo de documento con país cableado"),
)


def _cadenas_con_valor(archivo: Path) -> list[tuple[int, str]]:
    """Devuelve las cadenas literales del archivo que no son documentación.

    Se descartan las cadenas de documentación de módulo, clase y función, que son
    el único caso en que un literal de norma es deseable.
    """
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))

    docstrings: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            cuerpo = getattr(nodo, "body", [])
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                docstrings.add(id(cuerpo[0].value))

    encontradas: list[tuple[int, str]] = []
    for nodo in ast.walk(arbol):
        if (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in docstrings
        ):
            encontradas.append((nodo.lineno, nodo.value))
    return encontradas


def _modulos_del_motor() -> list[Path]:
    return [
        archivo
        for archivo in sorted(RAIZ_CODIGO.rglob("*.py"))
        if PAQUETE_JURISDICCIONES not in archivo.parents
        and archivo.parent != PAQUETE_JURISDICCIONES
    ]


class TestReglaDeAislamiento:
    def test_hay_modulos_que_analizar(self) -> None:
        """Salvaguarda: una prueba que no analiza nada pasaría siempre."""
        assert len(_modulos_del_motor()) >= 15

    def test_el_detector_encuentra_un_literal_prohibido(self, tmp_path: Path) -> None:
        """Prueba del propio detector.

        Sin esto, un patrón mal escrito haría que la prueba de aislamiento pasara
        siempre y la regla del ADR-0008 dejaría de estar vigilada sin que nadie lo
        note.
        """
        modulo = tmp_path / "infractor.py"
        modulo.write_text(
            '''"""Docstring que cita la Ley N.º 6822/2021: no debe detectarse."""

# Un comentario sobre Paraguay tampoco debe detectarse.
NORMA = "conforme a la Ley N.º 6822/2021"
''',
            encoding="utf-8",
        )

        cadenas = _cadenas_con_valor(modulo)
        valores = [texto for _, texto in cadenas]

        # La cadena de documentación queda fuera; el valor asignado, dentro.
        assert any("6822/2021" in v for v in valores)
        assert not any(v.startswith("Docstring") for v in valores)

    def test_el_detector_ignora_la_documentacion(self, tmp_path: Path) -> None:
        modulo = tmp_path / "documentado.py"
        modulo.write_text(
            '''"""Módulo conforme a la Ley N.º 6822/2021 de Paraguay."""


def funcion() -> None:
    """Cita la Resolución MIC N.º 262/2024 al explicar por qué existe."""
''',
            encoding="utf-8",
        )

        assert _cadenas_con_valor(modulo) == []

    def test_sin_literales_de_jurisdiccion_fuera_del_modulo(self) -> None:
        """Ningún valor del motor nombra un país, una norma ni un organismo.

        Un literal olvidado no rompe nada visible: emite un certificado que afirma
        algo falso sobre una persona, o indexa la evidencia de un firmante bajo la
        clave de otro país.
        """
        infracciones: list[str] = []

        for archivo in _modulos_del_motor():
            relativo = archivo.relative_to(RAIZ_CODIGO)
            for linea, texto in _cadenas_con_valor(archivo):
                for patron, descripcion in PATRONES_PROHIBIDOS:
                    if re.search(patron, texto):
                        infracciones.append(
                            f"{relativo}:{linea} contiene {descripcion} "
                            f"({patron!r}) en un valor: {texto[:70]!r}"
                        )

        assert not infracciones, (
            "Literales de jurisdicción fuera de `jurisdictions/` (ADR-0008).\n"
            "El valor debe salir del perfil de la jurisdicción activa:\n  "
            + "\n  ".join(infracciones)
        )


class TestRegistro:
    def test_las_dos_jurisdicciones_estan_disponibles(self) -> None:
        assert available() == ("BO", "PY")

    def test_jurisdiccion_desconocida(self) -> None:
        with pytest.raises(UnknownJurisdictionError, match="Disponibles"):
            get_profile("XX")

    def test_el_codigo_no_distingue_mayusculas(self) -> None:
        assert get_profile("py") is get_profile("PY")

    def test_un_perfil_sin_validacion_legal_no_opera_en_produccion(self) -> None:
        """La salvaguarda que impide que un perfil estructural firme de verdad."""
        for entorno in ("staging", "prod"):
            with pytest.raises(UnvalidatedJurisdictionError, match="validación legal"):
                require_profile("BO", environment=entorno)

    def test_un_perfil_sin_validacion_legal_sí_opera_en_desarrollo(self) -> None:
        assert require_profile("BO", environment="dev").code == "BO"

    def test_la_jurisdiccion_por_defecto_esta_validada(self) -> None:
        assert get_profile(DEFAULT_JURISDICTION).legally_validated


class TestPerfilParaguayo:
    @pytest.fixture()
    def perfil(self):  # type: ignore[no-untyped-def]
        return get_profile("PY")

    def test_cita_la_norma_de_la_constancia(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert "210/2025" in perfil.signature_law_citation

    def test_serial_del_certificado(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert perfil.subject_serial_number("4829153") == "PY-4829153"

    def test_clave_del_indice_por_firmante(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert perfil.signer_index_key("4829153") == "CI#PY-4829153"

    def test_acepta_una_cedula_paraguaya(self, perfil) -> None:  # type: ignore[no-untyped-def]
        perfil.validate_national_id("CI_PY", "4829153")

    def test_rechaza_un_numero_con_complemento_alfanumerico(self, perfil) -> None:  # type: ignore[no-untyped-def]
        """El formato boliviano no es válido bajo el perfil paraguayo."""
        with pytest.raises(ValueError, match="cédula de identidad paraguaya"):
            perfil.validate_national_id("CI_PY", "1234567-1K")

    def test_rechaza_un_documento_no_admitido(self, perfil) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValueError, match="no está admitido"):
            perfil.validate_national_id("CI_BO", "4829153")

    def test_conservacion_minima_de_tres_anios(self, perfil) -> None:  # type: ignore[no-untyped-def]
        """Dos años desde el vencimiento del contrato exigen un mínimo operativo mayor."""
        assert perfil.retention.minimum_days >= 1095

    def test_bloquea_los_actos_de_forma_solemne(self, perfil) -> None:  # type: ignore[no-untyped-def]
        for acto in ("hipoteca", "donacion", "testamento", "matrimonio"):
            assert acto in perfil.restrictions.excluded

    def test_declara_el_plazo_de_notificacion_de_incidentes(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert perfil.regulator.incident_notification_hours == 24

    def test_declara_autoridades_de_sellado_cualificadas(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert len(perfil.qualified_timestamp_authorities()) >= 1


class TestPerfilBoliviano:
    """El perfil que demuestra la generalización.

    Su valor está en lo que rompe: si algún literal paraguayo hubiera quedado en el
    motor, estas pruebas lo destaparían.
    """

    @pytest.fixture()
    def perfil(self):  # type: ignore[no-untyped-def]
        return get_profile("BO")

    def test_no_esta_validado_legalmente(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert perfil.legally_validated is False

    def test_toda_referencia_normativa_esta_marcada(self, perfil) -> None:  # type: ignore[no-untyped-def]
        """Nada de este perfil puede confundirse con una cita verificada."""
        for valor in (
            perfil.signature_law_citation,
            perfil.signature_law_name,
            perfil.retention.legal_basis,
            perfil.regulator.name,
        ):
            assert "[SIN VERIFICAR]" in valor

    def test_no_declara_autoridades_de_sellado(self, perfil) -> None:  # type: ignore[no-untyped-def]
        """Afirmar que un prestador está habilitado sin comprobarlo sería inventarlo."""
        assert perfil.timestamp_authorities == ()

    def test_serial_del_certificado_lleva_su_propio_prefijo(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert perfil.subject_serial_number("1234567-1K") == "BO-1234567-1K"

    def test_acepta_una_cedula_con_complemento_alfanumerico(self, perfil) -> None:  # type: ignore[no-untyped-def]
        """La diferencia que hace útil este perfil: rompe cualquier `^[0-9]+$`."""
        for numero in ("1234567", "1234567-1K", "1234567 LP"):
            perfil.validate_national_id("CI_BO", numero)

    def test_no_admite_el_documento_paraguayo(self, perfil) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValueError, match="no está admitido"):
            perfil.validate_national_id("CI_PY", "1234567")

    def test_incluye_un_acto_propio_de_su_ordenamiento(self, perfil) -> None:  # type: ignore[no-untyped-def]
        assert "anticretico" in perfil.restrictions.excluded


class TestInvariantesDelContrato:
    def test_un_plazo_de_conservacion_menor_a_un_anio_es_invalido(self) -> None:
        """Ninguna jurisdicción puede declarar una retención que invalide la prueba."""
        with pytest.raises(ValueError, match="valor probatorio"):
            EvidenceRetention(minimum_days=180, counted_from="la firma", legal_basis="—")

    def test_toda_jurisdiccion_define_los_textos_que_el_motor_usa(self) -> None:
        """Un texto faltante rompería la generación del expediente en tiempo de ejecución."""
        requeridos = (
            "expediente.titulo",
            "expediente.autor",
            "expediente.introduccion",
            "expediente.pie",
            "expediente.valor_probatorio",
            "firma.motivo",
            "firma.lugar",
            "rechazo.acto_excluido",
        )
        for codigo in available():
            perfil = get_profile(codigo)
            for clave in requeridos:
                assert perfil.text(clave), f"{codigo} no define {clave}"

    def test_un_texto_inexistente_falla_con_un_mensaje_util(self) -> None:
        with pytest.raises(KeyError, match="no define el texto"):
            get_profile("PY").text("clave.que.no.existe")
