# Pendientes explícitos

Lo que **no** está resuelto, con quién depende de ello. La regla que gobierna este archivo:
un pendiente se declara acá o no existe. **Nada se simula en silencio.**

Un pendiente simulado sin declarar es peor que uno abierto: produce un artefacto que parece
válido, y alguien lo va a presentar como si lo fuera.

Última revisión: 2026-09-02.

**Resuelto desde la última revisión:** T-11 (persistencia en DynamoDB del almacén de
idempotencia y del repositorio de transacciones); T-06 (el panel pasó a `node` con suite
propia); **N-01, N-03, N-05 y N-06**, cerrados por los textos oficiales incorporados a
`docs/diseno/normativa/`. El `DOC-ICPP-20 v2.0` confirma que RSA es obligatorio —ECDSA
habría incumplido— y que el perfil alcanza al certificado del firmante, no solo al del
prestador. Lo que abre es un inventario de apartamientos concretos:
`docs/CONFORMIDAD-PERFIL-CERTIFICADO.md`.

---

## 1. Bloqueantes del nivel 2 en producción

**Reencuadrado por el ADR-0011.** FNC dejó de ser prestador, así que estos requisitos ya no
bloquean al proyecto: **B-03 no aplica**, y B-01 y B-02 pasan a ser condiciones que debe
cumplir el *cliente* que quiera operar el nivel 2 en producción. FNC entrega el motor capaz de
usarlas.

Lo que no cambia es la regla: sin fecha cierta de un tercero y sin una CA real, una firma con
certificado efímero es inverificable a futuro. El art. 63.1.b de la ley lo confirma incluso
para la firma cualificada, que **no hace fe respecto de la fecha** sin sello de tiempo de un
prestador cualificado.

| # | Pendiente | Depende de | Estado |
| :-- | :---- | :---- | :---- |
| B-01 | *(pasa al cliente)* **Contratar la TSA cualificada** con un PCSC habilitado en Paraguay (Confirma, VIT, CODE 100, Documenta, SOS Tecnología). Sin fecha cierta de un tercero, una firma con certificado efímero es inverificable a futuro (ADR-0004) | Negocio | Abierto |
| B-02 | *(pasa al cliente)* **Emitir el certificado real de la CA intermedia** sobre la clave que ya vive en KMS. Hoy `dev` usa una raíz autofirmada generada por Terraform | SecOps + PKI | Abierto |
| ~~B-03~~ | ~~**Presentar el formulario `FOR-ICPP-02`** ante la DGFDCE del MIC~~ **Cerrado por el ADR-0011: no aplica.** El art. 15 de la ley dirige la obligación a los *prestadores*, y FNC dejó de serlo. Reaparecería si el modelo de entrega pasara a alojamiento gestionado por FNC | — | **No aplica** |

Mientras tanto, `dev` opera con CA autofirmada y TSA de prueba **etiquetadas en cada
certificado y en cada acta** (`environment=dev`, `tsa=test`).

---

## 2. Verificaciones normativas sin fuente de primera mano

Estas afirmaciones sostienen decisiones ya tomadas y **provienen de documentos de análisis,
no del texto oficial**. No están en el repositorio y nadie del equipo las leyó de primera
mano.

| # | Qué hay que verificar | Qué decisión sostiene | Riesgo si es falsa |
| :-- | :---- | :---- | :---- |
| N-02 | **Texto de la Res. SS.SG. N.º 210/2025**, arts. 4 y 9 | Norma citada en la constancia del perfil `PY` | La constancia citaría mal la norma que la habilita |
| N-07 | **Artículo 404 del Código Civil Paraguayo** | Qué hay que probar cuando se impugna la autenticidad de una firma electrónica: es la remisión del art. 40 de la ley | Es el requisito central de la firma no cualificada y no está contrastado. Sustituye a la cita del art. 308 del Código Procesal Civil, que los documentos de análisis daban por buena y **es incorrecta** |
| N-04 | Número **PEN** de la organización para el OID de política de certificado | Extensión `certificatePolicies` | Hoy el OID es un marcador de posición |

**Acción concreta:** los textos oficiales tienen que entrar al repositorio antes de que se
los cite en producción. Una norma sin su PDF es una cita que nadie puede contrastar.

**Los textos que ya entraron viven en `docs/diseno/normativa/`,** con un `LEEME.md` que
distingue lo que cada uno acredita de lo que no. Conseguir un documento no cierra por sí
solo la verificación que lo motivó: la Res. 262/2024 está en el repositorio y N-01 sigue
abierto, porque lo que hace falta es su Anexo.

---

## 3. Revisión legal pendiente

| # | Pendiente | Detalle |
| :-- | :---- | :---- |
| L-01 | **Revisión legal de la lista de actos excluidos** (`legal_guard`) por asesoría paraguaya | La lista se construyó por criterio técnico. Su historial en el control de versiones es evidencia de diligencia, pero no sustituye el dictamen |
| L-02 | **Datos de identificación del prestador en la DPSC** | El documento tiene campos entre corchetes: razón social, registro público, REPSE, representante legal, dominio, contacto del CISO |
| L-03 | **Coherencia entre la DPSC y el algoritmo implementado** | La DPSC declara RSA-4096. Si N-01 cambia la decisión del ADR-0006, **la DPSC debe corregirse antes de presentarse** |
| L-04 | **Póliza de responsabilidad civil voluntaria** | No exigible a un PSCNC, pero recomendada por el tratamiento de biometría de terceros. Decisión de negocio |
| L-05 | **Consulta escrita al MIC** sobre el alcance del registro y sobre el perfil | Cierra el punto opinable del encuadre, y suma tres preguntas que el `DOC-ICPP-20` no responde: (a) si el `extendedKeyUsage` admite OID adicionales a los dos enumerados; (b) si el perfil admite apartamientos en entornos no productivos, donde el certificado debe poder distinguirse a simple vista; (c) **quién emite el certificado de la CA intermedia de un prestador no cualificado** — el `DOC-ICPP-01 v2.0` declara que la política de la ACR-Py alcanza a los certificados emitidos a prestadores *cualificados*, y no dice si emite a los no cualificados. De la respuesta depende que nuestra raíz ancle en el Estado o sea privada |

---

## 4. Conformidad del certificado efímero con el `DOC-ICPP-20 v2.0`

Apartamientos entre el perfil que la norma fija para el *certificado no cualificado de
firma electrónica* (§4.1) y lo que emite `crypto/ephemeral_ca.py`. **P-01 y P-02 están
corregidos**; queda lo de abajo. No
son alcance diferido: son **incumplimientos de campos marcados obligatorios**, detectados
al leer el texto oficial. El análisis campo por campo, con lo que la norma además
*confirma*, está en `docs/CONFORMIDAD-PERFIL-CERTIFICADO.md`.

Ninguno afecta al **nivel 1**, que no emite certificados. Todos bloquean el nivel 2 en
producción, que ya estaba bloqueado por B-01 y B-02.

| # | Apartamiento | Detalle |
| :-- | :---- | :---- |
| P-03 | **Falta decidir dónde viaja el identificador de transacción en producción** | Resuelto a medias: la OU ya vale el literal del perfil en producción y conserva la marca `[NO VALIDO - ENTORNO {ENV}]` fuera de ella, de modo que los dos entornos nunca emiten el mismo sujeto. Lo que queda es el identificador de transacción, que en producción ya no cabe en la OU. **No se perdió el vínculo**: el acta sellada registra el número de serie del certificado. Falta decidir si se reubica —extensión propia, `User Notice` de `certificatePolicies`— o si alcanza con el serial |
| P-04 | **Faltan `surname` y `givenName`, obligatorios y separados del `commonName`** | **Cambia el contrato v1:** hoy llega `signer_common_name` como una sola cadena, y partirla por el espacio sería adivinar. Necesita ADR y versión del SDK |
| P-05 | **Extensiones obligatorias incompletas** | Falta `keyEncipherment` en `keyUsage`, falta `clientAuth` en `extendedKeyUsage` (y sobra el OID de *Document Signing* de Microsoft), falta `authorityInfoAccess` entero, y `certificatePolicies` no lleva `CPS Pointer` ni `User Notice`. CRL y AIA deberían impedir el arranque en producción si no están configurados |

El orden de ataque sugerido y las tres preguntas que el texto no cierra están al final de
`docs/CONFORMIDAD-PERFIL-CERTIFICADO.md`; las preguntas viajan con L-05.

---

## 5. Alcance técnico diferido

| # | Pendiente | Por qué se difiere |
| :-- | :---- | :---- |
| T-16 | **La infraestructura todavía supone que la cuenta de nube es de FNC** | El ADR-0011 traslada el despliegue al cliente —su cuenta, sus claves, su operación—, y de eso depende el encuadre legal entero, no solo el modelo comercial. Hay que revisar qué da por sentado el Terraform: nombres de bucket, políticas de clave que nombran principales nuestros, el rol de servicio, y la publicación de la CRL. **Mientras la operación siga de nuestro lado, la exención del art. 15 no se sostiene** |
| T-13 | **La CA raíz autofirmada de `dev` se genera a mano, no con Terraform** | El encargo preveía generarla en la IaC. Hoy la producen las pruebas y el entorno local; falta el recurso de Terraform que la cree y la publique para `dev`. No bloquea el desarrollo del nivel 2 |
| T-01 | **PAdES-B-LTA** para contratos de larga duración | Exige recolectar la cadena completa de validación (OCSP/CRL) e incrustarla en `/DSS`. El nivel B-T ya es suficiente mientras el sellado de tiempo esté garantizado (ADR-0004) |
| T-02 | **Habilitación comercial de la jurisdicción `BO`** | El perfil es estructural y está marcado `sin_validacion_legal`. Exige documentos fuente bolivianos y revisión legal local (ADR-0008) |
| T-03 | **Dígito verificador de la cédula paraguaya** | La validación comprueba formato, no dígito verificador |
| T-04 | **Modo COMPLIANCE de S3 Object Lock no se puede simular fielmente** en pruebas locales | Se valida en el entorno `dev` real (ADR-0003) |
| T-05 | **Alta automatizada de tenant** | Crear un tenant implica claves, alias y políticas de KMS: es una operación de infraestructura, no un registro en una tabla (ADR-0006) |
| T-14 | **El panel B2B sigue alimentándose de datos sintéticos** | `src/lib/mockData.ts` reemplaza a `GET /v1/signing-sessions/{id}/evidence`. La verificación pública del acta sí es real —comprueba la firma con WebCrypto contra las claves publicadas—, pero el expediente que muestra el visor forense no proviene de la API. Cerrarlo exige el cliente HTTP del panel y la autenticación de sesión del auditor |
| T-07 | **Límite de tiempo en la extracción de texto del PDF** | Ya no hay CVE abiertas en pypdf —se actualizó a 6.16.2—, pero la mitigación sigue teniendo sentido por sí misma: `legal_guard` analiza un PDF que envía el tenant, y ni el límite de tamaño (25 MiB) ni el de caracteres (200.000) detienen un bucle infinito. Deja de ser urgente y pasa a ser defensa en profundidad |
| T-08 | **WAF con limitación de tasa sobre CloudFront** | Excepción AWS-0011 del manifiesto, con vencimiento el 2026-12-02. **El egreso ya está restringido**: el grupo de seguridad declara destinos concretos —listas de prefijos de AWS y un rango configurable para la TSA— en lugar de abrir el puerto 443 entero, de modo que una exfiltración desde el contenedor no tiene salida. La lista de rangos externos está vacía hasta contratar la TSA (B-01), lo que impide que el nivel 2 opere: es lo que el ADR-0007 ya declara |
| T-09 | **Las condiciones de las políticas de clave de KMS no están verificadas contra AWS real** | Ver el detalle abajo: es una limitación del simulador, no un olvido |
| T-12 | **El modo `otp_mode: FNC_MANAGED` está declarado pero no implementado** | Exige el proveedor de mensajería. Hoy se rechaza con un motivo propio en lugar de fallar de forma ambigua. El primer tenant usa `TENANT_VERIFIED`, así que no bloquea su integración |
| T-10 | **`moto` ignora `MessageType="DIGEST"` de `kms:Sign`** | Vuelve a aplicar SHA-256 sobre el digest, mientras AWS lo firma tal cual. Por eso el sellado de actas se prueba contra un doble fiel a la semántica documentada y no contra `moto`. Conviene reverificarlo contra `dev` real junto con la prueba de humo de T-09 |

### T-09 · Qué prueban y qué no prueban los tests de aislamiento por clave

Distinción que conviene no perder de vista al leer `test_tenant_keys.py`, porque de ella
depende cuánta confianza merece:

**Lo que sí queda demostrado, y es criptográfico:** un texto cifrado para el inquilino A no
puede descifrarse en el contexto del inquilino B ni en el de otra transacción. El contexto
de cifrado va **autenticado junto con el texto cifrado**, de modo que alterarlo invalida el
descifrado por construcción del cifrado autenticado, no por una regla que alguien pueda
desactivar. Ese comportamiento es idéntico en `moto` y en AWS, y está comprobado.

**Lo que NO queda demostrado:** que las *condiciones de la política de clave* funcionen.
`moto` no evalúa políticas de KMS — se verificó explícitamente: permite cifrar **sin**
contexto de cifrado, que es justamente lo que la política de producción deniega. En
consecuencia, estas condiciones están escritas y revisadas, pero no ejercitadas:

* `kms:EncryptionContext:tenant_id` obligatorio e igual al inquilino de la clave.
* `kms:EncryptionContext:transaction_id` obligatorio.
* `kms:ViaService` acotado a S3 y DynamoDB de la región.
* La denegación de `kms:ScheduleKeyDeletion` fuera del rol de emergencia.
* La separación de funciones: que los roles de administración no puedan firmar.

**Cómo se cierra:** una prueba de humo contra el entorno `dev` real, una vez que exista la
cuenta de AWS (B-01/B-02), que intente cada operación denegada y espere `AccessDenied`.
Mientras tanto, el control existe en la política pero su eficacia se apoya en la revisión
del código, no en una comprobación automática.

---

## 6. Configuración remota de GitHub (la ejecuta el propietario)

El bootstrap del estándar se ejecutó con `--sin-gh`: crear variables y secretos, y
aplicar rulesets, son cambios en la cuenta de GitHub y no los hace un agente.

**Dos identidades, a propósito.** `AndresAlberdi` es la persona que revisa y aprueba;
`segurolotengopy` es la identidad de automatización que empuja ramas y abre los PR. No es
una duplicación pendiente de limpiar: es lo que hace efectiva la separación de funciones.
GitHub no permite aprobar el propio PR, de modo que si el agente abriera los PR con la
cuenta de la persona, el ruleset de `main` no podría satisfacerse — y quitarle la
aprobación obligatoria para resolverlo eliminaría la revisión por pares, que es la razón
de ser del ruleset. Por eso `aprobado_por` de cada excepción de seguridad nombra a la
persona: una excepción aprobada por la identidad de automatización no es una aprobación.

**Secretos** (Settings → Secrets → Actions). Ninguno es imprescindible hoy, porque el
manifiesto declara `produccion: false`:

| Secreto | Para qué | ¿Hace falta ya? |
| :---- | :---- | :---- |
| `GITLEAKS_LICENSE` | Solo si el repositorio pasa a una organización | No |
| `RELEASE_TOKEN` | PAT fine-grained para que el tag de `release.yml` dispare el pipeline | No, hasta el primer release |
| Credenciales de despliegue | Se generan con `setup-oidc-aws.sh` cuando exista la cuenta | No, hasta B-01/B-02 |

**Variables** (Settings → Variables → Actions): `MODO=A`, `GHAS_ENABLED=false`,
`NODE_VERSION=22`, `PYTHON_VERSION=3.12`, `COVERAGE_MIN=70`, `BLOQUEAR_EN=CRITICAL,HIGH`,
`WORKFLOW_PRODUCCION=ci-multicloud.yml`, `TAG_FIRMADO_REQUERIDO=false`. Las de despliegue
(`STAGING_URL`, `PROD_URL` y las de la nube) quedan para cuando exista la cuenta.

**Ruleset de `main`**: exigir el check `compuerta-pr` y revisión por pares. Es lo que impide
que un cambio entre sin pasar el pipeline.

**Estado (2026-09-02): el pipeline pasa por completo.** Corrió por primera vez en el PR #9,
donde se corrigieron ocho fallos —cuatro de configuración del repositorio y cuatro defectos
del propio estándar—. `compuerta-pr` termina en verde con 34 checks.

**Orden que conviene respetar:** el check tiene que haber corrido y pasado **antes** de
exigirlo. Aplicar el ruleset sobre un check que nunca se ejecutó deja el repositorio
bloqueado esperando algo que puede fallar por causas todavía desconocidas, y obliga a
depurar el pipeline con `main` ya protegido.

---

## 7. Decisiones de negocio abiertas

| # | Pregunta | Quién decide |
| :-- | :---- | :---- |
| D-01 | ¿Se ofrece custodia del PDF firmado como servicio contratable? Hoy el nivel 2 procesa en memoria y no conserva | Producto |
| D-02 | ¿Aislamiento físico (cuenta AWS dedicada) para qué tipo de tenant? El ADR-0005 lo contempla como modelo *silo* opcional | Producto + Arquitectura |
| D-03 | Política de precios por nivel de servicio y por transacción | Negocio |
