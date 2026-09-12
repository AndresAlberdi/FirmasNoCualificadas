"""Bloque visible de constancia de firma dentro del PDF.

## Por qué el bloque es la apariencia de la firma y no un estampado aparte

El bloque muestra la **huella del documento firmado**, y ahí hay una trampa: si se
estampara como contenido adicional, el archivo resultante tendría una huella
distinta de la que el propio bloque declara. Un lector que hashee el PDF que
tiene en la mano obtendría otro valor, y el bloque se contradiría a sí mismo.

Se resuelve haciendo que el bloque **sea la representación visual del campo de
firma**. La firma PAdES se aplica como actualización incremental: el documento
original sobrevive íntegro dentro del archivo firmado, byte a byte, como su
primera revisión. Por lo tanto la huella que el bloque declara **sí es
recomputable** por cualquiera que extraiga esa revisión con un validador PAdES.
No es una afirmación que haya que creer: es una que se puede comprobar.

## Qué no entra acá

El código del OTP no aparece nunca —solo el destino enmascarado y el hecho de la
validación—, ni el teléfono completo, ni la dirección IP, ni datos biométricos.
Es la regla de datos sensibles del proyecto aplicada al artefacto que el firmante
recibe y que puede terminar en manos de un tercero.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import datetime

from jurisdictions import JurisdictionProfile

# ------------------------------------------------------------ Maquetación --
# pyHanko no corta líneas: mide el ancho natural del texto y, si no entra en la
# caja, **escala todo el contenido** hasta que entre. Una declaración en una sola
# línea dejaba la letra de 7 pt en poco más de 1 pt y el QR en unos milímetros:
# el bloque estaba impreso, pero no se podía leer. Por eso el corte lo hace este
# módulo, a un ancho fijo, y la caja se dimensiona para ese ancho.

#: Cuerpo de la letra, en puntos. Es también el interlineado.
TAMANO_FUENTE = 7
#: Caracteres por línea. La fuente es Courier, monoespaciada de 0,6 em:
#: 64 caracteres miden 64 * 0,6 * 7 = 268,8 pt.
CARACTERES_POR_LINEA = 64
#: Lado del QR, en puntos (unos 32 mm). Fijo: sin él, pyHanko lo deriva de la
#: caja y del texto, y lo achica junto con todo lo demás.
LADO_QR = 90
#: Separación alrededor del QR, en puntos.
SEPARACION_QR = 3
#: Holgura vertical para que el texto no toque el borde de la caja.
_MARGEN_VERTICAL = 10

#: Ancho mínimo de la caja, en puntos PDF. Tiene que alojar el QR con su
#: separación (96 pt) más una línea completa (≈ 269 pt) sin escalar.
ANCHO_MINIMO = 420
#: Alto mínimo. Si el bloque tiene más líneas de las que caben, la caja crece
#: con él: ver `alto_necesario`.
ALTO_MINIMO = 205

#: Elidido de la huella. ASCII a propósito: la fuente estándar no codifica «…»
#: y el visor lo mostraba como «ƒ», que en una huella parece un dato.
ELIDIDO = "..."


@dataclass(frozen=True, slots=True)
class ConstanciaFirma:
    """Datos que el bloque visible declara.

    Todos provienen de la evidencia ya registrada: el bloque no calcula nada ni
    afirma nada que el expediente no sostenga.
    """

    #: Nombre y apellido del firmante, según su documento.
    firmante: str
    #: Documento de identidad, ya enmascarado si la política lo exige.
    documento_identidad: str
    #: En qué carácter firma (proponente, asegurado, representante…).
    caracter: str
    #: Nombre del documento firmado, tal como se le mostró al firmante.
    documento_firmado: str
    #: Correlativo del expediente en el sistema del inquilino.
    codigo_solicitud: str
    #: Momento de la firma, con zona horaria.
    firmado_en: datetime
    #: Cómo se autenticó la voluntad. **Nunca el código, solo el destino enmascarado.**
    metodo_autenticacion: str
    #: Identificador de la operación, que liga el bloque con el expediente.
    identificador_operacion: str
    #: Versión del documento. Viaja junto a la huella: una huella suelta no dice
    #: contra qué comparar.
    version_documento: str
    #: SHA-256 del documento **tal como se cerró y se le mostró al firmante**.
    huella_documento: str
    #: URL de la constancia pública. Es lo que codifica el QR.
    url_verificacion: str

    def __post_init__(self) -> None:
        if self.firmado_en.tzinfo is None:
            raise ValueError(
                "La fecha de firma debe llevar zona horaria: una hora sin zona no "
                "acredita cuándo ocurrió el acto."
            )
        if len(self.huella_documento) != 64:
            raise ValueError("La huella del documento debe ser un SHA-256 en hexadecimal.")


def _abreviar(huella: str, visibles: int = 8) -> str:
    """Huella con el centro elidido, para que entre en el bloque.

    El valor completo vive en el acta y en la constancia pública; acá basta con
    lo suficiente para cotejar a simple vista, y el QR lleva al valor entero.
    """
    return f"{huella[:visibles].upper()}{ELIDIDO}{huella[-visibles:].upper()}"


def _cortar(lineas: list[str]) -> list[str]:
    """Corta cada línea a `CARACTERES_POR_LINEA`, con sangría en la continuación.

    La sangría es lo que permite ver dónde termina un dato y empieza el rótulo
    siguiente. Las líneas vacías se conservan: separan el encabezado, los datos
    y la declaración.
    """
    cortadas: list[str] = []
    for linea in lineas:
        cortadas.extend(textwrap.wrap(linea, CARACTERES_POR_LINEA, subsequent_indent="  ") or [""])
    return cortadas


def componer_bloque(
    constancia: ConstanciaFirma,
    perfil: JurisdictionProfile,
    *,
    marca_entorno: str | None = None,
) -> str:
    """Arma el texto del bloque con los rótulos de la jurisdicción.

    Los rótulos y la declaración salen del perfil (ADR-0008): son texto de
    producto de un país, y el motor no los conoce.

    ``marca_entorno`` va en la primera línea, antes que el título. Fuera de
    producción el bloque tiene que decir que no vale como prueba igual que lo
    dice el certificado: un bloque sin marca sobre un documento de pruebas es
    exactamente el artefacto que alguien termina presentando como válido.
    """
    r = perfil.text
    lineas = [
        *([marca_entorno] if marca_entorno else []),
        r("bloque_firma.titulo"),
        "",
        f"{r('bloque_firma.firmante')}: {constancia.firmante}",
        f"{r('bloque_firma.documento')}: {constancia.documento_identidad}",
        f"{r('bloque_firma.caracter')}: {constancia.caracter}",
        f"{r('bloque_firma.documento_firmado')}: {constancia.documento_firmado}",
        f"{r('bloque_firma.codigo')}: {constancia.codigo_solicitud}",
        f"{r('bloque_firma.fecha')}: {constancia.firmado_en.strftime('%d/%m/%Y %H:%M:%S %Z')}",
        f"{r('bloque_firma.autenticacion')}: {constancia.metodo_autenticacion}",
        f"{r('bloque_firma.operacion')}: {constancia.identificador_operacion}",
        f"{r('bloque_firma.version')}: {constancia.version_documento}",
        f"{r('bloque_firma.huella')}: {_abreviar(constancia.huella_documento)}",
        f"{r('bloque_firma.estado')}: {r('bloque_firma.estado_validada')}",
        "",
        r("bloque_firma.declaracion"),
    ]
    return "\n".join(_cortar(lineas))


def alto_necesario(bloque: str) -> int:
    """Alto de caja, en puntos, para que el bloque entre sin escalarse.

    El texto ocupa una línea de `TAMANO_FUENTE` por renglón, y el QR su lado más
    la separación; la caja tiene que alojar el mayor de los dos. Los datos del
    firmante son de largo variable, así que un mínimo fijo no alcanza: un nombre
    de documento largo agrega renglones.
    """
    renglones = bloque.count("\n") + 1
    contenido = max(renglones * TAMANO_FUENTE, LADO_QR + 2 * SEPARACION_QR)
    return max(ALTO_MINIMO, contenido + _MARGEN_VERTICAL)
