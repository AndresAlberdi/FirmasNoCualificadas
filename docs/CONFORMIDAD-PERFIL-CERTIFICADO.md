# Conformidad del certificado efímero con el `DOC-ICPP-20 v2.0`

Contraste campo por campo entre el §4.1 del `DOC-ICPP-20 v2.0` —*Certificado no cualificado
de firma electrónica*, el perfil que rige el certificado que FNC emite al firmante— y lo que
hoy construye `services/src/pscnc/crypto/ephemeral_ca.py`.

**Fuente:** `docs/diseno/normativa/doc-icpp-20-v2.0.pdf`, leído de primera mano. Última
revisión: 2026-09-03.

**Estado: parcialmente corregido.** De los seis apartamientos detectados, **P-01 y P-02
están resueltos** —el `serialNumber` deriva de la sigla del documento y el sujeto lleva los
valores literales que fija el perfil— y P-03 quedó reducido a una sola pregunta abierta.
Siguen pendientes P-04 y P-05. Ninguno afecta a `dev`, donde el
certificado va deliberadamente rotulado como inválido; todos bloquean la emisión en
producción.

---

## 1. Lo que la norma ya confirma

Antes del inventario de faltantes, conviene fijar lo que la verificación **validó**, porque
eran decisiones tomadas sin respaldo de primera mano:

| Decisión | Estado |
| :---- | :---- |
| **RSA y no ECDSA** (ADR-0006) | **Confirmada.** Los tres perfiles fijan `Sha256withRsaEncryption` y `RSA Encryption` con obligatoriedad «Sí». ECDSA habría incumplido |
| **Certificado efímero de 15 minutos** (ADR-0004) | **Compatible.** La norma fija «hasta 4 años», que es un techo. Nada obliga a agotarlo |
| **`basicConstraints` crítico con `CA=FALSE`** | Conforme |
| **`keyUsage` crítico** | Conforme en criticidad |
| **Serial aleatorio** | Conforme. La norma pide «se asigna de forma aleatoria»; el código usa `secrets.randbits(159)` |
| **Clave RSA del firmante** | Conforme |
| **`subjectKeyIdentifier` y `authorityKeyIdentifier`** | Conformes |
| **SAN `rfc822Name`** | Conforme, y la norma lo marca opcional |

El perfil **alcanza al certificado del firmante**, no solo al del prestador: el §4 se titula
«Perfiles de certificado de entidades finales». Eso cierra la duda que abría el título de la
Res. 262/2024 y que quedó registrada como N-05.

---

## 2. Los apartamientos

### 2.1. `serialNumber` del sujeto con el prefijo equivocado — **corregido**

La norma (§4.1, campo 6.4) exige:

> `serialNumber="Siglas CI o PAS seguido del número de Cédula de Identidad o Pasaporte según corresponda"`

El perfil de jurisdicción produce `PY-4829153`, porque `certificate_serial_prefix` vale
`"PY"`. La norma pide `CI4829153` — la sigla del **tipo de documento**, no el código de país.

No es cosmético: el `serialNumber` es el campo por el que un validador identifica
unívocamente al firmante, y el prefijo distingue una cédula de un pasaporte. Con `PY-` esa
distinción se pierde, y además el certificado afirma algo que la norma no contempla.

**Dónde se corrige:** en `jurisdictions/py/`, no en el motor. El perfil ya conoce los tipos de
documento (`CI_PY`, `PASAPORTE`); lo que falta es que el prefijo salga del tipo y no del país.
Es exactamente el caso que el ADR-0008 previó: **si hubiera que tocar el motor, el perfil
estaría incompleto**.

### 2.2. `organizationName` del sujeto ausente — **corregido**

La norma (campo 6.2) fija un valor literal:

> `O= CERTIFICADO NO CUALIFICADO DE FIRMA ELECTRÓNICA`

El `Name.build` actual arma el sujeto con `country_name`, `common_name`, `serial_number` y
`organizational_unit_name`. **No hay `organization_name`.**

### 2.3. `organizationalUnitName` con valor propio — **corregido, con una pregunta abierta**

La norma (campo 6.3) fija:

> `OU=FIRMA ELECTRÓNICA`

El código emite `Firma Electronica No Cualificada - TX {transaction_id}`, y fuera de
producción lo antepone con `[NO VALIDO - ENTORNO DEV]`.

**Acá hay un conflicto real que conviene decidir explícitamente, no resolver por descuido.**
La marca de entorno vive en la OU justamente porque es un campo que cualquier visor muestra
sin desplegar extensiones (regla del `CLAUDE.md`: un artefacto de desarrollo no puede poder
confundirse con uno real). Pero la norma no deja espacio libre en ese campo.

La salida coherente es que **el perfil normativo rija solo en producción**. En `dev` no somos
un prestador comunicado ante el MIC y el certificado no pretende ser oponible: apartarse del
perfil ahí no es un incumplimiento, es la señal de que el artefacto no sirve como prueba. Lo
que no puede pasar es que `dev` y `prod` emitan el mismo sujeto.

El identificador de transacción, que hoy viaja en la OU, hay que reubicarlo — la norma no
prevé dónde. Candidatos: una extensión propia bajo nuestro arco OID, o el `User Notice` de
`certificatePolicies`. **Es una decisión de diseño abierta.**

### 2.4. `surname` y `givenName` ausentes — **obligatorios**

La norma los exige por separado (campos 6.5 y 6.6), además del `commonName`:

| Campo | Contenido | Obligatoriedad |
| :---- | :---- | :---- |
| 6.5 `Surname` | Apellido del titular, según documento de identificación | Sí |
| 6.6 `Given Name` | Nombre del titular, según documento de identidad | Sí |
| 6.7 `Common Name` | Nombre y apellido según documento | Sí |

El código solo emite el `commonName`. Faltan los dos atributos separados.

Esto tiene una consecuencia que excede el certificado: **el contrato público v1 no pide el
nombre y el apellido por separado.** `ConfirmTransactionRequest` recibe `signer_common_name`,
una sola cadena. Partirla por el espacio sería adivinar —un apellido compuesto o un nombre de
pila doble rompen cualquier heurística—, y en un certificado con valor probatorio adivinar no
es aceptable. Cerrar este punto **cambia el contrato con el tenant**, así que necesita su
propio ADR y una versión compatible del SDK.

### 2.5. `keyUsage` sin `keyEncipherment` — **obligatorio**

| Bit | Norma §4.1 | Implementación |
| :---- | :----: | :----: |
| `digitalSignature` | 1 | 1 |
| `contentCommitment` (no repudio) | 1 | 1 |
| **`keyEncipherment`** | **1** | **0** |
| `dataEncipherment` | 0 | 0 |
| `keyAgreement` | 0 | 0 |
| `keyCertSign` | 0 | 0 |
| `cRLSign` | 0 | 0 |

El comentario del código dice: *«No repudio: el certificado solo sirve para firmar, nunca para
cifrar»*. Es una postura de seguridad defendible —y más restrictiva que la norma—, pero la
norma marca el bit como obligatorio en 1.

Vale la pena registrar la incomodidad: habilitar `keyEncipherment` en un certificado cuya
clave vive quince minutos y solo se usa para firmar no aporta nada y amplía el uso declarado.
Aun así, **la conformidad con el perfil no es opcional para un prestador comunicado**, y
apartarse «por criterio técnico» de un campo marcado obligatorio es precisamente lo que
convierte un certificado en impugnable.

### 2.6. `extendedKeyUsage` incompleto y con un OID ajeno — **obligatorio**

| Norma §4.1 | Implementación |
| :---- | :---- |
| `emailProtection` — `1.3.6.1.5.5.7.3.4` | Presente |
| **`clientAuth` — `1.3.6.1.5.5.7.3.2`** | **Ausente** |
| — | `1.3.6.1.4.1.311.10.3.12` (*Document Signing*, arco privado de Microsoft) |

Falta el `clientAuth` que la norma exige, y sobra un OID que la norma no contempla.

El *Document Signing* de Microsoft es el que hace que Adobe reconozca el propósito del
certificado, así que quitarlo tiene costo práctico. La norma no prohíbe expresamente añadir
OID, pero tampoco los enumera como abiertos: **es una pregunta para la consulta al MIC**
(L-05), junto con la de la OU.

### 2.7. `certificatePolicies` incompleta y `authorityInfoAccess` ausente — **obligatorios**

La norma exige (campo 12) el `Policy Identifier` **más** los calificadores `CPS Pointer`
(dirección web de la DPC) y `User Notice`. El código emite únicamente el `policy_identifier`,
y solo si está configurado.

El `authorityInfoAccess` (campo 15, obligatorio) **no se emite en absoluto**.

El `crlDistributionPoints` (campo 14, obligatorio) se emite solo si hay URL configurada. Para
un campo obligatorio, «si está configurado» no alcanza: la ausencia de configuración debería
impedir arrancar en producción, como ya hace la validación de configuración con los backends
de desarrollo.

---

## 3. Lo que depende del certificado de la CA (B-02)

El `Issuer` del certificado efímero es el `Subject` del certificado de nuestra CA intermedia,
que todavía no existe (B-02). La norma lo fija en el §3:

| Campo | Valor exigido |
| :---- | :---- |
| `C` | `PY` |
| `O` | `Prestador NO Cualificado de Servicio de Confianza` |
| `OU` | Denominación oficial del prestador |
| `serialNumber` | `RUC` seguido del número de RUC del PSC |
| `CN` | `PNCSC-{nombre del PSC}` |
| `Validity` | 10 años |
| `basicConstraints` | AC, **`pathLenConstraint = 0`** |
| `keyUsage` | `keyCertSign` y `cRLSign` en 1; `digitalSignature` en **0** |

Dos consecuencias que conviene anticipar antes de emitirla:

1. **`pathLenConstraint = 0`** significa que nuestra CA intermedia no puede emitir otras CA,
   solo entidades finales. Coincide con la arquitectura, pero hay que fijarlo en la solicitud.
2. **`digitalSignature = 0` en la CA.** La clave de la CA firma certificados y CRL, nunca
   documentos. Es la misma separación que el ADR-0006 impone por política de KMS, ahora
   también declarada en el certificado.

Queda abierto **quién emite el certificado de nuestra CA intermedia**. El §3 del
`DOC-ICPP-20` pone como `Issuer` a una «AC Raíz», y el `DOC-ICPP-01 v2.0` —la DPC de la
Autoridad Certificadora Raíz del Paraguay— declara que su política criptográfica alcanza a la
ACR-Py «y, en lo pertinente, a los certificados emitidos a **PCSC**», es decir a prestadores
*cualificados*. No dice que emita a no cualificados, ni dice que no lo haga.

De la respuesta depende algo grande: si la ACR-Py no certifica a los no cualificados, nuestra
raíz es privada y la cadena no ancla en el Estado. **No se resuelve por lectura, se pregunta**
(L-05).

---

## 4. Qué hacer, en qué orden

1. **Trasladar al perfil de jurisdicción los valores que la norma fija** — prefijo del
   `serialNumber`, `O` y `OU` del sujeto. Son literales de norma: por el ADR-0008 van en
   `jurisdictions/py/`, nunca en el motor.
2. **Completar las extensiones obligatorias** — `keyEncipherment`, `clientAuth`, `AIA`,
   calificadores de `certificatePolicies` — y convertir en obligatoria la configuración de
   CRL y AIA cuando el entorno sea productivo.
3. **Decidir dónde va la marca de entorno de `dev`** ahora que la OU tiene valor fijo, y
   dónde viaja el identificador de transacción.
4. **Escribir el ADR que parta el nombre del firmante** en `given_name` y `surname` en el
   contrato v1, con su versión del SDK.
5. **Llevar a la consulta al MIC** las tres preguntas que el texto no cierra: si se admiten
   OID adicionales en el `extendedKeyUsage`, si el perfil admite apartamientos en entornos no
   productivos, y quién emite el certificado de la CA intermedia de un prestador no
   cualificado.

Los cinco puntos están en `docs/PENDIENTES.md`. **Ninguno bloquea el nivel 1**, que no emite
certificados; todos bloquean el nivel 2 en producción, que ya estaba bloqueado por B-01 y
B-02.
