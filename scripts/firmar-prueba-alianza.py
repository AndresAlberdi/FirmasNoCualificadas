#!/usr/bin/env python3
"""Firma no cualificada de prueba sobre un PDF, lista para una firma cualificada posterior.

Se escribió para la prueba con el firmador de Alianza Garantía (2026-09-11): toma un PDF
cualquiera, le aplica la firma no cualificada de un **cliente ficticio** con el bloque
visible de constancia y su QR, y verifica que una segunda firma incremental —la
cualificada, simulada— no invalide la primera.

Usa el motor real (`PadesSigner`, `EphemeralCertificateAuthority`, `ConstanciaFirma`) en
entorno **dev**: CA de desarrollo generada en el momento y TSA de pruebas local. Todo lo
que produce va marcado como no válido, y **nada de esto es un artefacto oponible**.

## Lo que el script compensa del motor (T-25 de `docs/PENDIENTES.md`)

`FirmanteMarcado` y `CajaExacta` existen porque el bloque del motor, tal como está en
`main`, sale ilegible (la declaración va en una sola línea y pyHanko escala todo el
bloque), imprime «ƒ» en vez de «…» y no lleva la marca de entorno. Lo corrige el PR #47
(`fix/bloque-constancia-legible`); cuando se fusione, estas dos clases se retiran.

## La hoja de firma (T-24)

`--hoja-de-firma` agrega una página final para las firmas, como actualización
incremental. **No existe en el motor**: cambia qué documento se cierra y se hashea, y
para entrar al producto necesita su ADR.

## Verificaciones que hace al terminar (quedan en `expediente-prueba.json`)

1. La firma es íntegra y cubre el archivo entero (pyHanko).
2. El original —y el documento cerrado— sobreviven byte a byte como prefijo del firmado.
3. El QR dibujado es idéntico, byte a byte, al generado desde la URL con los parámetros
   de pyHanko (no hace falta un decodificador de QR).
4. Una segunda firma incremental no invalida la nuestra.

Para una verificación independiente de pyHanko: `pdfsig <archivo>` (poppler).

Uso:
  services/.venv/bin/python scripts/firmar-prueba-alianza.py [entrada.pdf] --salida DIR \\
      [--hoja-de-firma --ancho-linea 96] [--codigo PROP-00000000] [--url-base URL]

Sin `entrada.pdf` genera un PDF sintético.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import secrets
import sys
import textwrap
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "services" / "src"))

from asn1crypto import keys as asn1_keys  # noqa: E402
from asn1crypto import x509 as asn1_x509  # noqa: E402
from cryptography import x509 as cx509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import utils as asym_utils  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # noqa: E402
from jurisdictions import get_profile  # noqa: E402
from pscnc.crypto.constancia import ConstanciaFirma  # noqa: E402
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData  # noqa: E402
from pscnc.crypto.pades import PadesSigner, VisualSignatureSpec  # noqa: E402
from pscnc.crypto.tsa import RecordingTimeStamper  # noqa: E402

ENTORNO = "dev"
MARCA = "DOCUMENTO DE PRUEBA - NO VALIDO - ENTORNO DEV"
#: Caracteres por línea del bloque; con Courier de 7 pt son ~270 pt de ancho.
ANCHO_DE_LINEA = 64
#: Lado del QR en puntos PDF (~3,2 cm): se escanea sin dificultad impreso.
LADO_QR = 90
#: Caja del bloque. Con este tamaño el contenido entra sin que pyHanko lo escale.
ANCHO_BLOQUE, ALTO_BLOQUE = 420.0, 205.0
#: Caja del bloque dentro de la hoja de firma (x, y, ancho, alto), en puntos PDF.
CAJA_EN_HOJA = (36.0, 330.0, 540.0, 215.0)
#: Espacio reservado para la firma cualificada posterior (x, y, ancho, alto).
RESERVA_CUALIFICADA = (36.0, 70.0, 540.0, 200.0)

# Cliente ficticio. La cédula es la sintética de la batería de pruebas de FNC.
CLIENTE = {
    "given_name": "Lucía Belén",
    "surname": "Galeano Rivas",
    "national_id": "4829153",
}


# ------------------------------------------------------------ Material dev --
def _certificado(
    sujeto: str,
    clave: rsa.RSAPrivateKey,
    *,
    ca: bool,
    dias: int,
    eku: list[cx509.ObjectIdentifier] | None = None,
) -> cx509.Certificate:
    nombre = cx509.Name(
        [
            cx509.NameAttribute(NameOID.COUNTRY_NAME, "PY"),
            cx509.NameAttribute(NameOID.ORGANIZATION_NAME, "FNC - Entorno de desarrollo"),
            cx509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "[NO VALIDO - ENTORNO DEV]"),
            cx509.NameAttribute(NameOID.COMMON_NAME, sujeto),
        ]
    )
    ahora = datetime.now(UTC)
    b = (
        cx509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(cx509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=dias))
        .add_extension(
            cx509.SubjectKeyIdentifier.from_public_key(clave.public_key()), critical=False
        )
    )
    if ca:
        b = b.add_extension(cx509.BasicConstraints(ca=True, path_length=0), critical=True)
        b = b.add_extension(
            cx509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    if eku:
        b = b.add_extension(cx509.ExtendedKeyUsage(eku), critical=True)
    return b.sign(clave, hashes.SHA256())


def _asn1(cert: cx509.Certificate) -> asn1_x509.Certificate:
    return asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))


def _pkcs8(clave: rsa.RSAPrivateKey) -> asn1_keys.PrivateKeyInfo:
    return asn1_keys.PrivateKeyInfo.load(
        clave.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


class CaDeDesarrollo:
    """Misma interfaz que `KmsCaSigner`, con la clave en memoria."""

    def __init__(self, clave: rsa.RSAPrivateKey) -> None:
        self._clave = clave

    @property
    def signing_algorithm(self) -> str:
        return "RSASSA_PKCS1_V1_5_SHA_256"

    def sign_digest(self, digest: bytes) -> bytes:
        return self._clave.sign(digest, padding.PKCS1v15(), asym_utils.Prehashed(hashes.SHA256()))

    def public_key_der(self) -> bytes:
        return self._clave.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )


class FirmanteMarcado(PadesSigner):
    """Compensa tres defectos del bloque del motor en `main` (T-25).

    1. La declaración sale en una sola línea de ~370 caracteres y pyHanko achica el
       bloque entero para que entre a lo ancho: se cortan las líneas y se fija el QR.
    2. `_abreviar` elide la huella con «…» (U+2026), que la Courier estándar no
       codifica y se imprime «ƒ»: se usan tres puntos.
    3. El bloque no lleva la marca de entorno: se antepone.

    Además agrega la línea del certificado con `%(signer)s`, que pyHanko completa al
    firmar con el titular del certificado efímero —se emite dentro de `sign()` y no
    existe antes—.
    """

    #: Se ajustan desde la línea de comandos según el espacio disponible.
    ancho_linea: int = ANCHO_DE_LINEA
    #: Sin renglones en blanco y con la marca en la línea del título: para huecos bajos.
    compacto: bool = False

    def _estilo_de_sello(self, visual: VisualSignatureSpec) -> Any:
        estilo = super()._estilo_de_sello(visual)
        if estilo is None:
            return None
        titulo, _, resto = estilo.stamp_text.partition("\n")
        certificado = "Certificado: %(signer)s - emitido por CA de Desarrollo FNC [NO VALIDO]"
        if self.compacto:
            crudas = [f"{titulo} - {MARCA}", *(x for x in resto.split("\n") if x.strip())]
        else:
            crudas = [MARCA, titulo, *resto.split("\n")]
        crudas.append(certificado)

        lineas: list[str] = []
        for linea in crudas:
            cortadas = textwrap.wrap(
                linea.replace("…", "..."), self.ancho_linea, subsequent_indent="  "
            )
            lineas.extend(cortadas or ([] if self.compacto else [""]))
        return replace(estilo, stamp_text="\n".join(lineas), qr_inner_size=LADO_QR)


@dataclass(frozen=True, slots=True)
class CajaExacta(VisualSignatureSpec):
    """Respeta la caja pedida en vez de agrandarla al mínimo del motor (300x190 pt).

    El mínimo existe para que el bloque no se recorte; pyHanko no recorta sino que
    escala, y con las líneas ya cortadas el escalado es mínimo. Agrandar la caja, en
    cambio, la haría pisar el contenido del documento.
    """

    def con_espacio_para_la_constancia(self) -> VisualSignatureSpec:
        return self


# ------------------------------------------------------------ Hoja de firma --
def _cadena_pdf(texto: str) -> bytes:
    crudo = texto.encode("cp1252")
    return b"(" + crudo.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def agregar_hoja_de_firma(original: bytes, *, nombre: str, paginas: int) -> bytes:
    """Agrega una página final para las firmas, como actualización incremental.

    Incremental y no reescribiendo el archivo: así el PDF recibido queda byte a byte
    al principio del documento cerrado —y del firmado—, y su huella sigue siendo
    comprobable contra el archivo que entregó quien lo pidió.
    """
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.generic import pdf_name
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pypdf import PdfReader

    caja = PdfReader(io.BytesIO(original)).pages[-1].mediabox
    ancho, alto = float(caja.width), float(caja.height)
    huella_original = hashlib.sha256(original).hexdigest()

    ops: list[bytes] = []

    def texto(x: float, y: float, fuente: str, tam: float, contenido: str) -> None:
        ops.append(
            b"BT /%s %g Tf %g %g Td %s Tj ET" % (fuente.encode(), tam, x, y, _cadena_pdf(contenido))
        )

    def parrafo(x: float, y: float, contenido: str, *, tam: float = 9, cols: int = 110) -> float:
        for linea in textwrap.wrap(contenido, cols):
            texto(x, y, "F1", tam, linea)
            y -= tam * 1.35
        return y

    y = alto - 60
    texto(36, y, "F2", 16, "Hoja de firma electrónica")
    y -= 18
    texto(36, y, "F2", 9, "DOCUMENTO DE PRUEBA - NO VÁLIDO - ENTORNO DE DESARROLLO")
    y -= 22
    y = parrafo(
        36,
        y,
        "Esta hoja se agrega al documento para contener la firma electrónica no cualificada del "
        "firmante y la firma electrónica cualificada que se aplique después. Forma parte del "
        "documento cerrado que se firma.",
    )
    y -= 8
    texto(36, y, "F2", 9, "Documento al que corresponde")
    y -= 13
    texto(36, y, "F1", 9, f"{nombre}.pdf  ·  {paginas} páginas")
    y -= 13
    texto(36, y, "F1", 9, "Huella SHA-256 del archivo original:")
    y -= 12
    texto(36, y, "F3", 8, huella_original)
    y -= 16
    parrafo(
        36,
        y,
        "El archivo original se conserva sin modificaciones como primera revisión de este PDF: "
        "cualquier validador PAdES puede extraerla y recalcular esa huella.",
    )

    x0, y0, _, h0 = CAJA_EN_HOJA
    texto(x0, y0 + h0 + 8, "F2", 10, "1. Firma electrónica no cualificada del firmante")
    x1, y1, w1, h1 = RESERVA_CUALIFICADA
    texto(x1, y1 + h1 + 8, "F2", 10, "2. Espacio reservado para la firma electrónica cualificada")
    ops.append(b"0.6 G 0.5 w [3 3] 0 d %g %g %g %g re S [] 0 d 0 G" % (x1, y1, w1, h1))
    parrafo(
        36,
        44,
        "El certificado del firmante y el sello de tiempo van incrustados en cada firma y se "
        "consultan en el panel de firmas del lector PDF.",
        tam=7.5,
        cols=140,
    )

    escritor = IncrementalPdfFileWriter(io.BytesIO(original))

    def fuente(base: str) -> Any:
        return escritor.add_object(
            generic.DictionaryObject(
                {
                    pdf_name("/Type"): pdf_name("/Font"),
                    pdf_name("/Subtype"): pdf_name("/Type1"),
                    pdf_name("/BaseFont"): pdf_name(base),
                    pdf_name("/Encoding"): pdf_name("/WinAnsiEncoding"),
                }
            )
        )

    flujo = escritor.add_object(generic.StreamObject(stream_data=b"\n".join(ops)))
    pagina = generic.DictionaryObject(
        {
            pdf_name("/Type"): pdf_name("/Page"),
            pdf_name("/MediaBox"): generic.ArrayObject(
                [generic.FloatObject(v) for v in (0, 0, ancho, alto)]
            ),
            pdf_name("/Resources"): generic.DictionaryObject(
                {
                    pdf_name("/Font"): generic.DictionaryObject(
                        {
                            pdf_name("/F1"): fuente("/Helvetica"),
                            pdf_name("/F2"): fuente("/Helvetica-Bold"),
                            pdf_name("/F3"): fuente("/Courier"),
                        }
                    )
                }
            ),
            pdf_name("/Contents"): flujo,
        }
    )
    escritor.insert_page(pagina)
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


# ------------------------------------------------------------ PDF sintético --
def pdf_sintetico() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 770, "Solicitud de Seguro - DOCUMENTO DE PRUEBA")
    c.setFont("Helvetica", 10)
    y = 740
    for linea in (
        "Documento sintetico generado para la prueba de firma cualificada.",
        "No contiene datos de personas reales y no tiene validez juridica.",
        "",
        "Proponente: Lucia Belen Galeano Rivas (cliente ficticio)",
        "Producto: Seguro de prueba",
        "Correlativo: ver bloque de firma",
    ):
        c.drawString(72, y, linea)
        y -= 16
    c.showPage()
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------ Verificación --
def _validar(pdf: bytes, raices: list[asn1_x509.Certificate]) -> list[dict[str, Any]]:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    vc = ValidationContext(trust_roots=raices, allow_fetching=False, revocation_mode="soft-fail")
    salida = []
    for emb in PdfFileReader(io.BytesIO(pdf)).embedded_signatures:
        st = validate_pdf_signature(emb, signer_validation_context=vc, ts_validation_context=vc)
        ts = st.timestamp_validity
        salida.append(
            {
                "campo": emb.field_name,
                "intacta": st.intact,
                "valida": st.valid,
                "confiable_con_raiz_dev": st.trusted,
                "cobertura": st.coverage.name,
                "modificaciones_posteriores": (
                    st.modification_level.name if st.modification_level else None
                ),
                "sello_de_tiempo_valido": bool(ts and ts.intact and ts.valid),
            }
        )
    return salida


def _qr_codifica(pdf: bytes, url: str) -> dict[str, Any]:
    """Compara el QR dibujado con uno regenerado desde la URL, con los parámetros de pyHanko.

    Si el flujo de dibujo coincide byte a byte, el QR es exactamente el de esa URL: es más
    fuerte que decodificarlo, y no exige instalar un decodificador.
    """
    import qrcode
    from pyhanko.pdf_utils.qr import PdfStreamQRImage
    from pypdf import PdfReader

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make()
    esperado = qr.make_image(image_factory=PdfStreamQRImage).render_command_stream()
    if isinstance(esperado, str):
        esperado = esperado.encode("latin-1")

    def _qrs(obj: Any) -> list[bytes]:
        recursos = obj.get("/Resources")
        xobjetos = recursos.get_object().get("/XObject") if recursos is not None else None
        if xobjetos is None:
            return []
        hallados: list[bytes] = []
        for nombre, ref in xobjetos.get_object().items():
            hijo = ref.get_object()
            if nombre == "/QR":
                hallados.append(hijo.get_data())
            hallados.extend(_qrs(hijo))
        return hallados

    dibujados: list[bytes] = []
    for pagina in PdfReader(io.BytesIO(pdf)).pages:
        for anotacion in pagina.get("/Annots") or []:
            ap = (anotacion.get_object().get("/AP") or {}).get("/N")
            if ap is not None:
                dibujados.extend(_qrs(ap.get_object()))
    return {
        "qr_encontrados": len(dibujados),
        "coincide_con_la_url": any(d.strip() == esperado.strip() for d in dibujados),
        "version_qr": qr.version,
    }


def _firma_simulada_posterior(pdf: bytes) -> bytes:
    """Segunda firma incremental con un certificado de simulación, como la cualificada."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = _certificado("SIMULACION firma cualificada", clave, ca=False, dias=2)
    firmante = signers.SimpleSigner(
        signing_cert=_asn1(cert), signing_key=_pkcs8(clave), cert_registry=None
    )
    x, y, _, _ = RESERVA_CUALIFICADA
    salida = io.BytesIO()
    signers.PdfSigner(
        signers.PdfSignatureMetadata(field_name="FirmaSimuladaCualificada", md_algorithm="sha256"),
        signer=firmante,
        new_field_spec=fields.SigFieldSpec(
            "FirmaSimuladaCualificada",
            box=(round(x + 10), round(y + 10), round(x + 260), round(y + 80)),
            on_page=-1,
        ),
    ).sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf)), output=salida)
    return salida.getvalue()


# ------------------------------------------------------------------ Main ----
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("entrada", nargs="?", type=Path)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--url-base", default="https://segurolotengo.com/verificar")
    ap.add_argument("--codigo", default=f"PROP-{secrets.randbelow(10**8):08d}")
    ap.add_argument("--pagina", type=int, default=0, help="1-indexada; 0 = última")
    ap.add_argument("--x", type=float, default=40.0)
    ap.add_argument("--y", type=float, default=40.0)
    ap.add_argument("--ancho", type=float, default=ANCHO_BLOQUE)
    ap.add_argument("--alto", type=float, default=ALTO_BLOQUE)
    ap.add_argument("--ancho-linea", type=int, default=ANCHO_DE_LINEA)
    ap.add_argument("--compacto", action="store_true")
    ap.add_argument(
        "--hoja-de-firma", action="store_true", help="agrega una página final para las firmas"
    )
    args = ap.parse_args()
    FirmanteMarcado.ancho_linea = args.ancho_linea
    FirmanteMarcado.compacto = args.compacto

    original = args.entrada.read_bytes() if args.entrada else pdf_sintetico()
    nombre = args.entrada.stem if args.entrada else "solicitud-prueba"
    args.salida.mkdir(parents=True, exist_ok=True)
    if not args.entrada:
        (args.salida / f"{nombre}.pdf").write_bytes(original)

    from pypdf import PdfReader

    paginas = len(PdfReader(io.BytesIO(original)).pages)
    if args.hoja_de_firma:
        # El documento que se cierra —y cuya huella declara el bloque— es el original
        # más la hoja de firma: es lo que el firmante ve y lo que se firma.
        documento = agregar_hoja_de_firma(original, nombre=nombre, paginas=paginas)
        pagina = paginas + 1
        x, y, ancho, alto = CAJA_EN_HOJA
    else:
        documento = original
        pagina = args.pagina or paginas
        x, y, ancho, alto = args.x, args.y, args.ancho, args.alto

    perfil = get_profile("PY")

    clave_ca = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    cert_ca = _certificado("CA de Desarrollo FNC", clave_ca, ca=True, dias=30)
    clave_tsa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert_tsa = _certificado(
        "TSA de Pruebas FNC", clave_tsa, ca=False, dias=30, eku=[ExtendedKeyUsageOID.TIME_STAMPING]
    )

    from pyhanko.sign.timestamps import DummyTimeStamper

    autoridad = EphemeralCertificateAuthority(
        ca_certificate_der=cert_ca.public_bytes(serialization.Encoding.DER),
        ca_signer=CaDeDesarrollo(clave_ca),
        # Dominio reservado (RFC 2606): deja constancia de que no hay CRL publicada.
        crl_url="http://crl.fnc-dev.invalid/intermedia.crl",
        user_notice=perfil.text("certificado.aviso_de_uso"),
        environment=ENTORNO,
    )
    firmante = FirmanteMarcado(
        certificate_authority=autoridad,
        timestamper_factory=lambda: RecordingTimeStamper(
            "",
            provider_name="TSA de Pruebas FNC",
            qualified=False,
            delegate=DummyTimeStamper(tsa_cert=_asn1(cert_tsa), tsa_key=_pkcs8(clave_tsa)),
        ),
        jurisdiction=perfil,
    )

    huella = hashlib.sha256(documento).hexdigest()
    transaccion = str(uuid.uuid4())
    url = f"{args.url_base.rstrip('/')}/{args.codigo}"
    cedula = CLIENTE["national_id"]
    constancia = ConstanciaFirma(
        firmante=f"{CLIENTE['given_name']} {CLIENTE['surname']}",
        documento_identidad=f"{cedula[0]}.{cedula[1:4]}****",
        caracter="Proponente / Asegurado",
        documento_firmado=nombre,
        codigo_solicitud=args.codigo,
        firmado_en=datetime.now(ZoneInfo("America/Asuncion")),
        metodo_autenticacion="Codigo de un solo uso al celular terminado en **** 4821",
        identificador_operacion=f"FENQ-{secrets.token_hex(4).upper()}",
        version_documento="1.0",
        huella_documento=huella,
        url_verificacion=url,
    )

    resultado = firmante.sign(
        documento,
        SubjectData.for_jurisdiction(perfil, transaction_id=transaccion, **CLIENTE),
        visual=CajaExacta(
            enabled=True, page=pagina, x=x, y=y, width=ancho, height=alto, constancia=constancia
        ),
        field_name="FirmaNoCualificadaCliente",
    )

    firmado = args.salida / f"{nombre}-firmado-FNC.pdf"
    firmado.write_bytes(resultado.signed_pdf)
    (args.salida / "ca-desarrollo-fnc.pem").write_bytes(
        cert_ca.public_bytes(serialization.Encoding.PEM)
    )
    (args.salida / "tsa-pruebas-fnc.pem").write_bytes(
        cert_tsa.public_bytes(serialization.Encoding.PEM)
    )

    raices = [_asn1(cert_ca), _asn1(cert_tsa)]
    propia = _validar(resultado.signed_pdf, raices)
    doble = _firma_simulada_posterior(resultado.signed_pdf)
    # El certificado simulado es autofirmado y pyHanko lo registra con traceback;
    # el resultado ya lo refleja `confiable_con_raiz_dev: false`.
    logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
    tras_segunda = _validar(doble, raices)
    verificacion = args.salida / "verificacion"
    verificacion.mkdir(exist_ok=True)
    (verificacion / f"{nombre}-con-segunda-firma-simulada.pdf").write_bytes(doble)

    sujeto = asn1_x509.Certificate.load(resultado.certificate.certificate_der).subject.native
    expediente = {
        "entorno": ENTORNO,
        "no_valido_para_produccion": True,
        "codigo": args.codigo,
        "url_verificacion": url,
        "transaction_id": transaccion,
        "identificador_operacion": constancia.identificador_operacion,
        "pagina_del_bloque": pagina,
        "documento_original": {
            "archivo": nombre,
            "sha256": hashlib.sha256(original).hexdigest(),
            "bytes": len(original),
        },
        "documento_cerrado": {
            "con_hoja_de_firma": args.hoja_de_firma,
            "sha256": huella,
            "bytes": len(documento),
            "paginas": pagina if args.hoja_de_firma else paginas,
        },
        "documento_firmado": {"archivo": firmado.name, "sha256": resultado.signed_sha256},
        "original_es_prefijo_exacto": resultado.signed_pdf.startswith(original),
        "cerrado_es_prefijo_exacto": resultado.signed_pdf.startswith(documento),
        "qr": _qr_codifica(resultado.signed_pdf, url),
        "certificado_firmante": {"serial": resultado.certificate.serial_number, "sujeto": sujeto},
        "sello_de_tiempo": {
            "autoridad": resultado.timestamp.provider_name,
            "cualificado": resultado.timestamp.qualified,
            "gen_time": resultado.timestamp.gen_time.isoformat(),
        },
        "formato": resultado.signature_format,
        "validacion_firma_propia": propia,
        "validacion_tras_segunda_firma_simulada": tras_segunda,
    }
    (args.salida / "expediente-prueba.json").write_text(
        json.dumps(expediente, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(expediente, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
