# ADR-0006 · Jerarquía de claves en AWS KMS y sellado criptográfico de actas

* **Estado:** Aceptado
* **Fecha:** 2026-09-02
* **Decisores:** Arquitectura, SecOps, Producto
* **Reemplaza a:** ninguno. **Extiende** el ADR-0004, que fijó la CA intermedia en KMS pero
  contemplaba una sola clave y un solo cliente.

## Contexto

El ADR-0004 resolvió la custodia de la clave de la CA intermedia. Con la plataforma
convertida en un SaaS multi-tenant aparecen tres necesidades que aquella decisión no cubre:

1. **Sellar el acta de evidencia del nivel 1**, donde no hay firma PAdES sobre el documento y
   lo único que prueba el acto es el registro. Un registro que nosotros mismos podemos
   reescribir no prueba nada: hace falta una firma que un tercero pueda verificar sin acceso
   a nuestros sistemas.
2. **Cifrar las evidencias en reposo con separación por inquilino**, de modo que el
   aislamiento del ADR-0005 no dependa solo de una comprobación en la capa de repositorio.
3. **Sellar el expediente como persona jurídica**, que es lo que el §5.2 del blueprint
   describe como Sello Electrónico y hoy no existe.

Hay además una confusión conceptual recurrente que conviene dejar escrita, porque induce
diseños equivocados: **KMS no guarda firmas.** Guarda claves que nunca salen del HSM y
ejecuta operaciones con ellas. Lo que se conserva son los artefactos producidos —firmas
PAdES, actas selladas, evidencias cifradas—; KMS es lo que los hace verificables y lo que
garantiza que nadie, tampoco nosotros, pudo producirlos sin pasar por la política de la
clave. Un diseño que trate a KMS como un depósito de firmas termina guardando en él lo que
debería estar en S3, y sin la traza de CloudTrail que hace auditable cada operación.

## Decisión

### 1. Cuatro claves, con ámbitos distintos

| Clave | Tipo | Para qué | Ámbito |
| :---- | :---- | :---- | :---- |
| `kms-ca-intermedia` | `RSA_4096`, `SIGN_VERIFY` | Firmar los certificados efímeros de firmante (nivel 2) | Una **por entorno**, nunca compartida |
| `kms-sello-acta-<tenant>` | `ECC_NIST_P256`, `SIGN_VERIFY` | Sellar el acta de evidencia y el resumen del expediente | Una **por tenant** |
| `kms-evidencias-<tenant>` | `SYMMETRIC_DEFAULT` | Cifrado envolvente de evidencias en S3 y de campo en DynamoDB | Una **por tenant**, con rotación anual |
| `kms-sello-electronico-pscnc` | `RSA_4096`, `SIGN_VERIFY` | Sello de persona jurídica del prestador sobre el expediente | Una por entorno |

### 2. La CA intermedia usa `RSA_4096`, y el firmante es agnóstico al algoritmo

Se descarta `ECC_NIST_P384` para la CA intermedia, pese a producir firmas más cortas. Tres
razones, en orden de peso:

1. La **Declaración de Prácticas que hay que presentar al MIC** ya declara RSA-4096 y
   `sha256WithRSAEncryption` (OID `1.2.840.113549.1.1.11`) como algoritmo del perfil
   `DOC-ICPP-20 v2.0`. Presentar una DPSC que declara un algoritmo distinto del que la clave
   usa en realidad convierte el documento regulatorio en una declaración falsa.
2. `aws-kms-key-architecture-pscnc.md` §2 restringe `kms:SigningAlgorithm` a
   `RSASSA_PSS_SHA_256` y `RSASSA_PKCS1_V1_5_SHA_256`, y los describe como *los algoritmos
   aprobados por la Infraestructura de Clave Pública del Paraguay*.
3. El motor de firma ya está construido sobre RSA.

**Salvedad que esta decisión no puede ocultar:** las dos primeras razones salen de
documentos de análisis, **no del perfil que la Res. MIC N.º 262/2024 aprueba**. El texto de
la resolución ya está en `docs/diseno/normativa/res-mic-262-2024.pdf` y se leyó de primera
mano, pero es el acto administrativo: aprueba el Anexo `DOC-ICPP-20 v2.0` sin contenerlo, de
modo que los algoritmos siguen sin verificarse (N-01). Peor aún, su título y su artículo 1.º
hablan del perfil **del certificado del prestador**, mientras este ADR razona sobre el
certificado efímero que el prestador emite al firmante: puede que la norma que se invoca ni
siquiera sea la que rige el caso (N-05). Elegir ECDSA contra una norma que
no verificamos sería una apuesta; elegir RSA es alinearse con lo que el propio proyecto ya
declaró. Verificar el texto de la resolución queda registrado en `docs/PENDIENTES.md`.

Para que esa salvedad no se vuelva una trampa, **`CaSigner` no conoce el algoritmo**: lo
recibe de la configuración y lo propaga al `AlgorithmIdentifier` del certificado. Si la
norma admite ECDSA, la migración es crear un alias `v2` sobre una clave nueva y cambiar una
variable de entorno — no una refactorización con la clave ya en producción.

Las claves de **sello de acta sí son `ECC_NIST_P256`**, sin conflicto regulatorio: el acta
no es un certificado X.509 bajo `DOC-ICPP-20`, es un JWS. Ahí manda la interoperabilidad con
librerías estándar, y `ES256` es el algoritmo mejor soportado del ecosistema JOSE.

### 3. Rotación por alias versionado, nunca por `KeyId`

**AWS KMS no admite rotación automática de claves asimétricas.** Cualquier diseño que la
suponga —incluido el §6 del documento de arquitectura de claves, que la pide explícitamente—
es irrealizable. La rotación es un procedimiento manual documentado en
`docs/RUNBOOK-break-glass.md`:

* Los alias llevan versión: `alias/fnc/<entorno>/ca-intermedia/v2`.
* Durante el período de solapamiento la clave anterior **puede verificar pero no firmar**.
* El código selecciona la clave **siempre por alias**, nunca por `KeyId` fijo. Un `KeyId`
  cableado convierte cada rotación en un despliegue.

### 4. Contexto de cifrado obligatorio

Toda operación simétrica lleva `kms:EncryptionContext` con `tenant_id` y `transaction_id`, y
la política de clave lo exige por condición. Un texto cifrado del tenant A **no puede
descifrarse** en el contexto del tenant B, aunque el llamador tenga permisos sobre ambas
claves. Es el ADR-0005 hecho cumplir en la capa criptográfica y no solo en la de repositorio.

### 5. Mínimo privilegio y separación de funciones

* El rol de la API firma (`kms:Sign`) pero no puede leer la clave pública de un tenant que no
  está atendiendo.
* **Ningún rol humano tiene `kms:Sign`.** Un operador que pueda firmar puede fabricar
  evidencia.
* `kms:ScheduleKeyDeletion` se bloquea por condición en la política y exige el procedimiento
  break-glass.
* CloudTrail registra todas las operaciones de KMS en el mismo espejo WORM: **una firma sin
  su registro en CloudTrail no es auditable.** Alarmas sobre `kms:Sign` fuera del rol de la
  API y sobre cualquier `DisableKey` o `ScheduleKeyDeletion`.

### 6. Formato del acta sellada

JSON canónico según **RFC 8785 (JCS)**, con `tenant_id`, `transaction_id`, `jurisdiction`,
nivel de servicio, hash del documento con su versión, hash del acta, algoritmo, `key_alias`,
`key_version`, marca de tiempo de KMS y, si existe, el token de la TSA. La firma viaja en un
sobre **JWS** con `kid` igual al alias versionado, para que el tenant la verifique con
cualquier librería JOSE.

La canonicalización no es un detalle de formato: sin un orden de claves determinista, dos
serializaciones del mismo acta producen hashes distintos y la verificación falla por
motivos que nada tienen que ver con la integridad.

## Consecuencias

* **Costo por tenant:** dos claves por inquilino. A la escala prevista es marginal frente al
  costo de una fuga cruzada, y es lo que permite publicar la clave pública de sello sin
  exponer nada de los demás.
* **El alta de un tenant deja de ser un registro en una tabla** y pasa a ser una operación de
  infraestructura que crea claves, alias y políticas. Se automatiza con un módulo de
  Terraform parametrizado.
* La retención de S3 Object Lock sale del perfil de jurisdicción y **el `plan` de Terraform
  falla si es menor al mínimo de la jurisdicción activa** (ADR-0008). Object Lock solo se
  habilita al crear el bucket y en modo COMPLIANCE la retención es irreversible: un valor
  equivocado no se corrige, se hereda.
* Mientras no exista el certificado real de la CA, el entorno `dev` opera con una raíz
  autofirmada generada por Terraform y una TSA de prueba, **etiquetadas `environment=dev` y
  `tsa=test` en cada certificado y en cada acta**, para que ningún artefacto de desarrollo
  pueda confundirse con uno de producción.
* Pruebas obligatorias: aislamiento por clave entre tenants con `moto`/LocalStack, y
  verificación del acta sellada con una librería JOSE ajena a nuestro código — verificar con
  el mismo código que firma no demuestra interoperabilidad.
