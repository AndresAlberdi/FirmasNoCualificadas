"""Bloque visible de constancia dentro del PDF firmado.

Lo que estas pruebas fijan no es la maquetación sino **qué afirma el bloque y qué
no debe aparecer nunca en él**. Un bloque que muestre el código del OTP o el
teléfono completo convierte el artefacto que el firmante recibe —y que puede
terminar en manos de un tercero— en una filtración.

Todos los datos son sintéticos.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from asn1crypto import x509 as asn1_x509

from jurisdictions import get_profile
from pscnc.crypto.constancia import ALTO_MINIMO, ANCHO_MINIMO, ConstanciaFirma, componer_bloque
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData
from pscnc.crypto.pades import PadesSigner, VisualSignatureSpec
from pscnc.crypto.tsa import RecordingTimeStamper

HUELLA = "7f3a" + "0" * 56 + "91bc"
URL = "https://verificar.example.py/v1/verify/SOL-00018425"


def _texto_de_la_apariencia(pdf: bytes) -> str:
    """Texto dibujado en la apariencia del campo de firma, ya normalizado.

    Dos detalles del formato obligan a normalizar antes de comparar: PDF escapa
    caracteres en octal —los dos puntos son ``\\072``— y parte las líneas largas
    en varias operaciones de dibujo, de modo que un valor puede llegar cortado.
    """
    import io
    import re

    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(pdf))
    trozos: list[str] = []
    for pagina in lector.pages:
        for anotacion in pagina.get("/Annots") or []:
            objeto = anotacion.get_object()
            apariencia = (objeto.get("/AP") or {}).get("/N")
            if apariencia is None:
                continue
            datos = apariencia.get_object().get_data()
            trozos.extend(m.decode("latin-1") for m in re.findall(rb"\((?:[^()\\]|\\.)*\)", datos))

    crudo = "".join(t[1:-1] for t in trozos)
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1), 8)), crudo)


@pytest.fixture()
def firmante(ca_certificate_der, ca_signer, tsa_material):  # type: ignore[no-untyped-def]
    from pyhanko.sign.timestamps import DummyTimeStamper

    tsa_cert, tsa_key = tsa_material
    autoridad = EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url="https://crl.pruebas.example.py/pscnc/intermediate.crl",
        policy_oid="1.3.6.1.4.1.99999.1.1.1",
    )

    def _fabrica() -> RecordingTimeStamper:
        return RecordingTimeStamper(
            "",
            provider_name="TSA de Pruebas",
            delegate=DummyTimeStamper(tsa_cert=tsa_cert, tsa_key=tsa_key),
        )

    return PadesSigner(
        certificate_authority=autoridad,
        timestamper_factory=_fabrica,
        jurisdiction=get_profile("PY"),
    )


@pytest.fixture()
def constancia() -> ConstanciaFirma:
    return ConstanciaFirma(
        firmante="María José Ruiz Díaz",
        # Enmascarada: el bloque viaja con el documento y lo lee cualquiera.
        documento_identidad="4.829****",
        caracter="Proponente / Asegurado",
        documento_firmado="Solicitud de Seguro y Formulario de Identificacion",
        codigo_solicitud="SOL-00018425",
        firmado_en=datetime(2026, 9, 3, 14, 35, 22, tzinfo=UTC),
        metodo_autenticacion="Codigo de un solo uso al celular verificado terminado en **** 4821",
        identificador_operacion="FENQ-8F7A92C1",
        version_documento="1.0",
        huella_documento=HUELLA,
        url_verificacion=URL,
    )


class TestContenidoDelBloque:
    def test_lleva_los_datos_que_la_constancia_debe_mostrar(self, constancia) -> None:  # type: ignore[no-untyped-def]
        texto = componer_bloque(constancia, get_profile("PY"))

        for esperado in (
            "María José Ruiz Díaz",
            "SOL-00018425",
            "FENQ-8F7A92C1",
            "1.0",
            "03/09/2026",
            "Proponente / Asegurado",
        ):
            assert esperado in texto

    def test_incluye_la_declaracion_de_consentimiento(self, constancia) -> None:  # type: ignore[no-untyped-def]
        """Es lo único del bloque que afirma un acto en vez de describir un dato."""
        texto = componer_bloque(constancia, get_profile("PY"))

        assert "consentimiento libre, expreso e inequivoco" in texto

    def test_la_huella_va_abreviada_pero_reconocible(self, constancia) -> None:  # type: ignore[no-untyped-def]
        """El valor entero vive en el acta; acá basta para cotejar a simple vista."""
        texto = componer_bloque(constancia, get_profile("PY"))

        assert "7F3A" in texto and "91BC" in texto
        assert HUELLA not in texto  # sesenta y cuatro caracteres no entran en el bloque

    def test_los_rotulos_salen_del_perfil_y_no_del_motor(self, constancia) -> None:  # type: ignore[no-untyped-def]
        """Un rótulo cableado en el motor sería un literal de país fuera de su lugar."""
        py = componer_bloque(constancia, get_profile("PY"))
        bo = componer_bloque(constancia, get_profile("BO"))

        assert py != bo
        assert "[SIN VERIFICAR]" in bo


class TestLoQueNuncaAparece:
    """Regla de datos sensibles aplicada al artefacto que recibe el firmante."""

    def test_no_hay_lugar_para_el_codigo_del_otp(self, constancia) -> None:  # type: ignore[no-untyped-def]
        """`ConstanciaFirma` no tiene campo donde ponerlo, que es más fuerte que no ponerlo."""
        campos = set(ConstanciaFirma.__dataclass_fields__)

        assert not {c for c in campos if "otp" in c or "codigo_verificacion" in c}
        # Lo que sí viaja es el método, con el destino ya enmascarado.
        assert "4821" in constancia.metodo_autenticacion
        assert "otp" not in componer_bloque(constancia, get_profile("PY")).lower()

    def test_rechaza_una_fecha_sin_zona_horaria(self) -> None:
        """Una hora sin zona no acredita cuándo ocurrió el acto."""
        with pytest.raises(ValueError, match="zona horaria"):
            ConstanciaFirma(
                firmante="X",
                documento_identidad="1***",
                caracter="Proponente",
                documento_firmado="Doc",
                codigo_solicitud="SOL-1",
                firmado_en=datetime(2026, 9, 3, 14, 35, 22),
                metodo_autenticacion="OTP",
                identificador_operacion="OP-1",
                version_documento="1.0",
                huella_documento=HUELLA,
                url_verificacion=URL,
            )

    def test_rechaza_una_huella_que_no_sea_sha256(self, constancia) -> None:  # type: ignore[no-untyped-def]
        from dataclasses import replace

        with pytest.raises(ValueError, match="SHA-256"):
            replace(constancia, huella_documento="abc")


class TestEspacioDelBloque:
    def test_la_caja_se_agranda_para_que_no_se_recorte(self, constancia) -> None:  # type: ignore[no-untyped-def]
        """Un bloque recortado deja media huella y media declaración a la vista.

        Las dos cosas dejan de significar lo que dicen, así que es peor que no
        tener bloque.
        """
        chica = VisualSignatureSpec(width=180, height=60, constancia=constancia)

        agrandada = chica.con_espacio_para_la_constancia()

        assert agrandada.width >= ANCHO_MINIMO
        assert agrandada.height >= ALTO_MINIMO

    def test_sin_constancia_la_caja_no_se_toca(self) -> None:
        chica = VisualSignatureSpec(width=180, height=60)

        assert chica.con_espacio_para_la_constancia() == chica


class TestDentroDelPdfFirmado:
    def test_el_bloque_queda_impreso_en_el_documento(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        """Y el documento original sobrevive dentro, que es lo que hace recomputable
        la huella que el propio bloque declara."""
        resultado = firmante.sign(
            pdf_de_prueba,
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                given_name="María José",
                surname="Ruiz Díaz",
                national_id="4829153",
            ),
            visual=VisualSignatureSpec(enabled=True, constancia=constancia),
        )

        # El bloque se dibuja en la apariencia de la anotación de firma, no en el
        # contenido de la página: `extract_text` no lo ve, y hay que leer el flujo.
        texto = _texto_de_la_apariencia(resultado.signed_pdf)
        assert "SOL-00018425" in texto
        assert "FENQ-8F7A92C1" in texto
        assert "Ruiz" in texto

        # El original íntegro sigue adentro: la firma es una actualización
        # incremental, y por eso la huella que el bloque declara es recomputable.
        assert pdf_de_prueba in resultado.signed_pdf

    def test_el_certificado_sigue_siendo_el_emitido(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        """El bloque es apariencia: no cambia quién firmó ni con qué."""
        resultado = firmante.sign(
            pdf_de_prueba,
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                given_name="María José",
                surname="Ruiz Díaz",
                national_id="4829153",
            ),
            visual=VisualSignatureSpec(enabled=True, constancia=constancia),
        )

        sujeto = asn1_x509.Certificate.load(resultado.certificate.certificate_der).subject.native
        assert sujeto["serial_number"] == "CI4829153"
