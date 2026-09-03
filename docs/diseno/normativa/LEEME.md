# Textos normativos oficiales

Fuentes de **primera mano**. Todo lo que está en este directorio se leyó del documento
oficial, no de un análisis que lo resume.

La distinción importa porque gobierna qué se puede afirmar. Un análisis de terceros dice qué
*entiende* su autor que exige una norma; el texto oficial dice qué exige. Cuando los dos
discrepan, manda el texto — y cuando el texto no está, la afirmación va a la tabla §2 de
`docs/PENDIENTES.md` como verificación pendiente, no al código.

| Archivo | Norma | Qué es | ¿Obliga a FNC? |
| :---- | :---- | :---- | :---- |
| `ley-6822-2021.pdf` | Ley N.º 6822, 30/12/2021 | **La ley marco.** Define el servicio de confianza (art. 4.º num. 48), el efecto jurídico de la firma (art. 39) y su impugnación (art. 40), la comunicación de actividad de los prestadores no cualificados (art. 15), el soporte del documento electrónico (art. 63) y la Autoridad de Aplicación (art. 96) | **Sí** |
| `decreto-7576-2022.pdf` | Decreto N.º 7576/2022 | Reglamento. Art. 5.º: procedimiento de comunicación de inicio y listado público de prestadores no cualificados. Art. 6.º: incidentes de seguridad **dentro de las 24 horas** | **Sí** |
| `res-mic-1384-2022.pdf` | Res. MIC N.º 1384, 6/10/2022 | Reglamenta la comunicación de inicio de actividad de servicios **no cualificados**. Aprueba el formulario `FOR-ICPP-02` (Anexo I) y el perfil de certificado del PSCNC (Anexo II) | **Sí** |
| `res-mic-262-2024.pdf` | Res. MIC N.º 262, 4/4/2024 | Modifica el art. 3.º de la 1384/2022 y aprueba `DOC-ICPP-20 v2.0` | **Sí** |
| `doc-icpp-20-v2.0.pdf` | Anexo I de la Res. 262/2024 | **El perfil de certificado.** Campos, obligatoriedad y algoritmos, para la AC Raíz, para el PSCNC y para las entidades finales | **Sí — es la norma que rige el motor de firma** |
| `doc-icpp-01-v2.0.pdf` | Anexo I de la Res. N.º 0495/2026 | Política y DPC de la **Autoridad Certificadora Raíz** de la ICPP | Indirectamente |
| `doc-icpp-03-v1.0.pdf` | Anexo de la Res. N.º 811/2022 | Directivas obligatorias para redactar la DPC de los prestadores **cualificados** | **No** — pero es la plantilla |
| `doc-icpp-07-v1.0.pdf` | Anexo de la Res. N.º 812/2022 | Directivas para la DPC del prestador **cualificado** que genera o gestiona datos de creación de firma (firma remota con clave en HSM bajo su custodia) | **No** — pero describe nuestra arquitectura en su versión cualificada |

## La definición que ordena el encuadre — verificada

> Servicio de confianza: el servicio electrónico **prestado habitualmente a cambio de una
> remuneración**, consistente en: a) la creación, verificación y validación de firmas
> electrónicas, sellos electrónicos, sellos de tiempo electrónicos, servicios de entrega
> electrónica certificada y certificados relativos a estos servicios […]
>
> — Ley N.º 6822/2021, **artículo 4.º, numeral 48**

Es la cita que sostiene todo el encuadre del proyecto, y ahora sale del texto y no de un
resumen. Quien firma sus propias contrataciones no presta un servicio de confianza; el
**artículo 15**, que impone comunicar la actividad dentro de los tres meses, está dirigido a
los *prestadores*.

## Lo que la ley dice sobre el valor probatorio

* **Art. 39.1** — no se niegan efectos jurídicos ni admisibilidad a una firma electrónica por
  el mero hecho de serlo o de no cumplir los requisitos de la cualificada.
* **Art. 39.2** — la equivalencia con la firma manuscrita se reconoce **solo a la
  cualificada**. No se extiende a las demás.
* **Art. 40** — impugnada la autenticidad, se estará a lo establecido en el **artículo 404 del
  Código Civil Paraguayo**.
* **Art. 63.1.b** — los instrumentos privados suscritos con firma **cualificada** acreditan la
  autenticidad de la firma y la identidad del titular; aun así **no hacen fe respecto de su
  fecha** salvo sello de tiempo de un prestador cualificado.
* **Art. 63.2** — el soporte con datos firmados electrónicamente es admisible como prueba
  documental en procedimientos judiciales y administrativos.

**Una corrección que apareció al contrastar.** Los documentos de análisis atribuían la
impugnación de una firma electrónica al art. 308 del Código Procesal Civil. El art. 40 remite
al **art. 404 del Código Civil**. No es el mismo cuerpo legal ni el mismo artículo, y ese
artículo todavía no está en el repositorio (N-07).

## La distinción que ordena esta carpeta: cualificado ≠ no cualificado

`DOC-ICPP-03` y `DOC-ICPP-07` están dirigidos a los **PCSC**, los prestadores *cualificados*.
FNC es **no cualificado**, así que no la obligan. Conviene tenerlo presente en las dos
direcciones:

* **No hay que autoimponerse sus requisitos** como si fueran ley. Exigencias de HSM
  certificado, auditoría de conformidad y habilitación previa pertenecen al régimen
  cualificado; trasladarlas al no cualificado encarece el servicio sin obligación.
* **Tampoco conviene ignorarlas.** Son el mapa más fiel de qué espera el MIC de una
  declaración de prácticas, y `DOC-ICPP-07` describe exactamente nuestra arquitectura —firma
  con clave generada y custodiada por el prestador— en su variante cualificada. La estructura
  de capítulos de `DOC-ICPP-03` (el esquema RFC 3647) es la que nuestra DPSC debería seguir.

`DOC-ICPP-07` dice además que *toda* DPC elaborada «en el ámbito de la ICPP» debe adoptar su
misma estructura. Si esa frase alcanza a los no cualificados es una de las preguntas de la
consulta escrita al MIC (L-05).

## Res. 1384/2022 — lo que aporta

* **Art. 2.º aprueba el formulario `FOR-ICPP-02`**, que es el instrumento concreto de la
  comunicación de inicio de actividad. B-03 deja de ser «comunicar al MIC» y pasa a ser
  «presentar `FOR-ICPP-02`».
* **Art. 3.º aprueba el perfil de certificado** del PSCNC en su Anexo II — reemplazado por
  `DOC-ICPP-20 v2.0` vía la Res. 262/2024.
* Firmada por Francisco Ruiz Díaz, ministro sustituto, el 6 de octubre de 2022.

## Res. 262/2024 — lo que aporta

* Título exacto: *«Por la cual se aprueba el perfil del certificado del prestador no
  cualificado de servicios de confianza DOC-ICPP-20 versión 2.0»*. Asunción, 4 de abril de
  2024, firma el ministro Francisco Javier Giménez.
* Su art. 2.º aprueba el Anexo y deja sin efecto la versión 1.0. Vigencia desde la
  promulgación.
* De los considerandos: la Ley N.º 6822/2021 instituye al MIC como Autoridad de Aplicación en
  su **artículo 96**, a través de la Dirección General de Comercio Electrónico, y los
  servicios no cualificados **no necesitan autorización administrativa** para iniciar
  actividad, pero deben comunicarla **dentro de los tres meses**.

## DOC-ICPP-20 v2.0 — lo que zanja

**Sí alcanza al certificado del firmante.** Su §4 es «Perfiles de certificado de entidades
finales», con §4.1 dedicado al *certificado no cualificado de firma electrónica*. La duda que
abría el título de la resolución —si el perfil regía solo el certificado *del prestador*— está
resuelta: rige los dos.

**El algoritmo es obligatorio y es RSA.** Los tres perfiles fijan
`Signature Algorithm = Sha256withRsaEncryption` y `Subject Public Key Info = RSA Encryption`,
en ambos casos con obligatoriedad «Sí». Elegir ECDSA habría incumplido la norma.

Nótese que `Sha256withRsaEncryption` es **PKCS#1 v1.5**, no PSS. Son dos OID distintos, y la
norma nombra uno solo.

**La vigencia del certificado de entidad final es «hasta 4 años».** Es un techo, no un valor
fijo: los 15 minutos del ADR-0004 caben dentro.

El detalle campo por campo, y en qué se aparta hoy la implementación, está en
`docs/CONFORMIDAD-PERFIL-CERTIFICADO.md`.

## Una rareza documental, para que no confunda

El índice del `DOC-ICPP-20` numera «2. Perfil de certificado del Prestador No Cualificado»,
pero el cuerpo titula «2. PERFIL DE CERTIFICADO DE LA AC RAÍZ» y deja el del prestador en el
§3. Al citar el documento hay que referirse a los títulos del cuerpo, no a los del índice.
