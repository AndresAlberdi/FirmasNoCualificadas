# Textos normativos oficiales

Fuentes de **primera mano**. Todo lo que está en este directorio se leyó del documento
oficial, no de un análisis que lo resume.

La distinción importa porque gobierna qué se puede afirmar. Un análisis de terceros dice qué
*entiende* su autor que exige una norma; el texto oficial dice qué exige. Cuando los dos
discrepan, manda el texto — y cuando el texto no está, la afirmación va a la tabla §2 de
`docs/PENDIENTES.md` como verificación pendiente, no al código.

| Archivo | Norma | Qué es | ¿Obliga a FNC? |
| :---- | :---- | :---- | :---- |
| `res-mic-1384-2022.pdf` | Res. MIC N.º 1384, 6/10/2022 | Reglamenta la comunicación de inicio de actividad de servicios **no cualificados**. Aprueba el formulario `FOR-ICPP-02` (Anexo I) y el perfil de certificado del PSCNC (Anexo II) | **Sí** |
| `res-mic-262-2024.pdf` | Res. MIC N.º 262, 4/4/2024 | Modifica el art. 3.º de la 1384/2022 y aprueba `DOC-ICPP-20 v2.0` | **Sí** |
| `doc-icpp-20-v2.0.pdf` | Anexo I de la Res. 262/2024 | **El perfil de certificado.** Campos, obligatoriedad y algoritmos, para la AC Raíz, para el PSCNC y para las entidades finales | **Sí — es la norma que rige el motor de firma** |
| `doc-icpp-01-v2.0.pdf` | Anexo I de la Res. N.º 0495/2026 | Política y DPC de la **Autoridad Certificadora Raíz** de la ICPP | Indirectamente |
| `doc-icpp-03-v1.0.pdf` | Anexo de la Res. N.º 811/2022 | Directivas obligatorias para redactar la DPC de los prestadores **cualificados** | **No** — pero es la plantilla |
| `doc-icpp-07-v1.0.pdf` | Anexo de la Res. N.º 812/2022 | Directivas para la DPC del prestador **cualificado** que genera o gestiona datos de creación de firma (firma remota con clave en HSM bajo su custodia) | **No** — pero describe nuestra arquitectura en su versión cualificada |

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
