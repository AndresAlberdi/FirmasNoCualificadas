"""Bloque visible de constancia dentro del PDF firmado.

Lo que estas pruebas fijan no es la maquetación sino **qué afirma el bloque y qué
no debe aparecer nunca en él**. Un bloque que muestre el código del OTP o el
teléfono completo convierte el artefacto que el firmante recibe —y que puede
terminar en manos de un tercero— en una filtración.

Todos los datos son sintéticos.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pytest
from asn1crypto import x509 as asn1_x509

from jurisdictions import get_profile
from pscnc.crypto.constancia import (
    ALTO_MINIMO,
    ANCHO_MINIMO,
    CARACTERES_POR_LINEA,
    LADO_QR,
    TAMANO_FUENTE,
    ConstanciaFirma,
    alto_necesario,
    componer_bloque,
)
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData
from pscnc.crypto.pades import PadesSigner, VisualSignatureSpec
from pscnc.crypto.tsa import RecordingTimeStamper

HUELLA = "7f3a" + "0" * 56 + "91bc"
URL = "https://verificar.example.py/v1/verify/SOL-00018425"
MARCA_DEV = "[NO VALIDO - ENTORNO DEV]"


def _flujo_de_la_apariencia(pdf: bytes) -> tuple[bytes, float]:
    """Flujo de la apariencia del campo de firma y ancho natural de su QR."""
    from pypdf import PdfReader

    for pagina in PdfReader(io.BytesIO(pdf)).pages:
        for anotacion in pagina.get("/Annots") or []:
            apariencia = (anotacion.get_object().get("/AP") or {}).get("/N")
            if apariencia is None:
                continue
            flujo = apariencia.get_object()
            qr = flujo["/Resources"]["/XObject"]["/QR"].get_object()
            x0, _, x1, _ = (float(v) for v in qr["/BBox"])
            return flujo.get_data(), abs(x1 - x0)
    raise AssertionError("El PDF no tiene apariencia de firma")


_TOKEN = re.compile(
    rb"\((?:[^()\\]|\\.)*\)"  # cadena literal
    rb"|<[0-9A-Fa-f\s]*>"  # cadena hexadecimal
    rb"|/[^\s/\[\]()<>]+"  # nombre
    rb"|[-+]?(?:\d+\.?\d*|\.\d+)"  # número
    rb"|[A-Za-z*'\"]+"  # operador
)


@dataclass(frozen=True)
class Medidas:
    """Lo que un lector ve de la apariencia, una vez aplicadas las escalas."""

    #: Cuerpo efectivo de cada selección de fuente, en puntos de página.
    cuerpos: list[float]
    #: Lado efectivo del QR, en puntos de página.
    lado_qr: float


def _medir(flujo: bytes, ancho_natural_qr: float) -> Medidas:
    """Recorre el flujo acumulando las matrices ``cm``, como lo haría un visor.

    pyHanko no avisa cuando escala: si el texto no entra, antepone un ``cm`` con
    un factor menor que uno y dibuja igual. Por eso lo que se mide es el cuerpo
    efectivo —el de ``Tf`` por la escala vigente—, no el declarado.
    """
    escala, pila = 1.0, []
    operandos: list[bytes] = []
    cuerpos: list[float] = []
    lado_qr = 0.0
    for token in _TOKEN.findall(flujo):
        if not token[:1].isalpha() and token[:1] not in (b"*", b"'", b'"'):
            operandos.append(token)
            continue
        if token == b"q":
            pila.append(escala)
        elif token == b"Q":
            escala = pila.pop()
        elif token == b"cm":
            a, b, c, d = (float(v) for v in operandos[:4])
            assert b == 0 and c == 0, "La apariencia no debería rotar"
            assert abs(a) == abs(d), "La apariencia no debería deformar"
            escala *= abs(a)
        elif token == b"Tf":
            cuerpos.append(float(operandos[-1]) * escala)
        elif token == b"Do" and operandos[-1] == b"/QR":
            lado_qr = ancho_natural_qr * escala
        operandos = []
    return Medidas(cuerpos=cuerpos, lado_qr=lado_qr)


def _lineas_como_las_ve_el_visor(flujo: bytes) -> list[str]:
    """Cadenas dibujadas, decodificadas como las decodifica el visor.

    La fuente declara ``WinAnsiEncoding`` y el visor lee cada byte con esa tabla.
    Una cadena hexadecimal —pyHanko cae en UTF-16 cuando no puede codificar— se
    conserva cruda: no hay forma de que coincida con el texto original, y la
    comparación la delata.
    """
    escapes = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}

    def _desescapar(m: re.Match[bytes]) -> bytes:
        s = m.group(1)
        if s[:1].isdigit():
            return bytes([int(s, 8)])
        return escapes.get(s, s)

    lineas: list[str] = []
    for token in _TOKEN.findall(flujo):
        if token.startswith(b"("):
            crudo = re.sub(rb"\\([0-7]{1,3}|.)", _desescapar, token[1:-1])
            lineas.append(crudo.decode("cp1252", errors="replace"))
        elif token.startswith(b"<"):
            lineas.append(token.decode("ascii"))
    return lineas


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
def fabrica_de_firmantes(ca_certificate_der, ca_signer, tsa_material):  # type: ignore[no-untyped-def]
    """Firmantes por entorno: la marca del bloque depende de él."""
    from pyhanko.sign.timestamps import DummyTimeStamper

    tsa_cert, tsa_key = tsa_material

    def _firmante(entorno: str = "prod") -> PadesSigner:
        autoridad = EphemeralCertificateAuthority(
            ca_certificate_der=ca_certificate_der,
            ca_signer=ca_signer,
            crl_url="https://crl.pruebas.example.py/pscnc/intermediate.crl",
            policy_oid="1.3.6.1.4.1.99999.1.1.1",
            environment=entorno,
        )

        def _fabrica() -> RecordingTimeStamper:
            return RecordingTimeStamper(
                "",
                provider_name="TSA de Pruebas",
                qualified=False,
                delegate=DummyTimeStamper(tsa_cert=tsa_cert, tsa_key=tsa_key),
            )

        return PadesSigner(
            certificate_authority=autoridad,
            timestamper_factory=_fabrica,
            jurisdiction=get_profile("PY"),
        )

    return _firmante


@pytest.fixture()
def firmante(fabrica_de_firmantes):  # type: ignore[no-untyped-def]
    return fabrica_de_firmantes()


def _firmar(firmante: PadesSigner, pdf: bytes, constancia: ConstanciaFirma) -> bytes:
    return firmante.sign(
        pdf,
        SubjectData.for_jurisdiction(
            get_profile("PY"),
            given_name="María José",
            surname="Ruiz Díaz",
            national_id="4829153",
        ),
        visual=VisualSignatureSpec(enabled=True, constancia=constancia),
    ).signed_pdf


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

        assert "7F3A0000...000091BC" in texto
        assert HUELLA not in texto  # sesenta y cuatro caracteres no entran en el bloque
        # «…» no existe en la fuente del bloque: el visor lo mostraba como «ƒ».
        assert "…" not in texto

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


class TestSeLeeSinLupa:
    """Que el texto esté en el flujo no alcanza: tiene que poder leerse.

    pyHanko no corta líneas. Si el texto no entra en la caja, lo escala entero,
    y el bloque queda impreso con letra de un punto y un QR de milímetros. Nada
    falla: el texto sigue estando, y las pruebas que solo buscan el texto pasan.
    """

    def test_ninguna_linea_supera_el_ancho_fijo(self, constancia) -> None:  # type: ignore[no-untyped-def]
        for pais in ("PY", "BO"):
            texto = componer_bloque(constancia, get_profile(pais), marca_entorno=MARCA_DEV)

            largas = [linea for linea in texto.split("\n") if len(linea) > CARACTERES_POR_LINEA]
            assert not largas, f"{pais}: {largas}"

    def test_la_continuacion_de_una_linea_va_sangrada(self, constancia) -> None:  # type: ignore[no-untyped-def]
        """Sin sangría, el resto de un dato se confunde con el rótulo siguiente."""
        texto = componer_bloque(constancia, get_profile("PY"))

        assert "\n  verificado terminado en **** 4821" in texto

    def test_el_detector_ve_un_bloque_escalado(self) -> None:
        """El error que motivó estas pruebas, tal como pyHanko lo dibujaba."""
        flujo = b"q 0.188442 0 0 0.188442 0 77 cm q 0.557576 0 0 0.557576 3 3 cm /QR Do Q"
        flujo += b" q BT /F1 7 Tf 7 TL (FIRMA) Tj ET Q Q"

        medidas = _medir(flujo, ancho_natural_qr=410)

        assert medidas.cuerpos == [pytest.approx(7 * 0.188442)]
        assert medidas.lado_qr == pytest.approx(410 * 0.188442 * 0.557576)

    def test_la_letra_y_el_qr_conservan_su_tamano(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        flujo, ancho_qr = _flujo_de_la_apariencia(_firmar(firmante, pdf_de_prueba, constancia))

        medidas = _medir(flujo, ancho_qr)

        assert medidas.cuerpos, "La apariencia no selecciona ninguna fuente"
        assert min(medidas.cuerpos) >= TAMANO_FUENTE * 0.99
        assert medidas.lado_qr >= LADO_QR * 0.99

    def test_los_datos_largos_agrandan_la_caja_en_vez_de_achicar_la_letra(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        """Los datos del firmante son de largo variable; la letra no puede serlo."""
        larga = replace(
            constancia,
            documento_firmado="Solicitud de Seguro de Vida Colectivo " * 6,
            caracter="Proponente, Asegurado Titular y Representante Legal del Tomador",
        )

        flujo, ancho_qr = _flujo_de_la_apariencia(_firmar(firmante, pdf_de_prueba, larga))
        medidas = _medir(flujo, ancho_qr)

        assert min(medidas.cuerpos) >= TAMANO_FUENTE * 0.99
        assert medidas.lado_qr >= LADO_QR * 0.99

    def test_la_caja_crece_con_los_renglones(self, constancia) -> None:  # type: ignore[no-untyped-def]
        bloque = componer_bloque(constancia, get_profile("PY")) + "\nrenglon" * 40

        caja = VisualSignatureSpec(constancia=constancia).con_espacio_para_la_constancia(bloque)

        assert caja.height == alto_necesario(bloque) > ALTO_MINIMO


class TestLaFuenteCodificaLoQueSeImprime:
    """La fuente estándar declara WinAnsi, pero pyHanko escribe en PDFDocEncoding.

    Las dos tablas coinciden en ASCII y en las letras acentuadas, y difieren en
    unos pocos signos tipográficos: «…» sale como «ƒ». En una huella, un signo
    equivocado no se ve como error sino como dato.
    """

    def test_lo_que_ve_el_visor_es_lo_que_se_compuso(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        flujo, _ = _flujo_de_la_apariencia(_firmar(firmante, pdf_de_prueba, constancia))

        visto = "".join(_lineas_como_las_ve_el_visor(flujo))

        assert visto == componer_bloque(constancia, get_profile("PY")).replace("\n", "")

    def test_el_detector_ve_un_caracter_mal_codificado(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        """El mismo control, con el carácter que motivó la corrección."""
        con_elipsis = replace(constancia, documento_firmado="Solicitud…")

        flujo, _ = _flujo_de_la_apariencia(_firmar(firmante, pdf_de_prueba, con_elipsis))
        visto = "".join(_lineas_como_las_ve_el_visor(flujo))

        assert "Solicitudƒ" in visto
        assert visto != componer_bloque(con_elipsis, get_profile("PY")).replace("\n", "")


class TestMarcaDeEntorno:
    """Fuera de producción, todo artefacto va marcado; el bloque también."""

    def test_fuera_de_produccion_el_bloque_lo_dice_primero(  # type: ignore[no-untyped-def]
        self, fabrica_de_firmantes, pdf_de_prueba, constancia
    ) -> None:
        flujo, _ = _flujo_de_la_apariencia(
            _firmar(fabrica_de_firmantes("dev"), pdf_de_prueba, constancia)
        )

        lineas = _lineas_como_las_ve_el_visor(flujo)
        assert lineas[0] == MARCA_DEV

    def test_la_marca_es_la_misma_del_certificado(  # type: ignore[no-untyped-def]
        self, fabrica_de_firmantes, pdf_de_prueba, constancia
    ) -> None:
        """Dos marcas escritas por separado terminan diciendo cosas distintas."""
        resultado = fabrica_de_firmantes("dev").sign(
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
        assert sujeto["organizational_unit_name"].startswith(MARCA_DEV)
        assert MARCA_DEV in _texto_de_la_apariencia(resultado.signed_pdf)

    def test_en_produccion_no_hay_marca(  # type: ignore[no-untyped-def]
        self, firmante, pdf_de_prueba, constancia
    ) -> None:
        texto = _texto_de_la_apariencia(_firmar(firmante, pdf_de_prueba, constancia))

        assert "NO VALIDO" not in texto
