# Pendientes explícitos

Lo que **no** está resuelto, con quién depende de ello. La regla que gobierna este archivo:
un pendiente se declara acá o no existe. **Nada se simula en silencio.**

Un pendiente simulado sin declarar es peor que uno abierto: produce un artefacto que parece
válido, y alguien lo va a presentar como si lo fuera.

Última revisión: 2026-09-02.

**Resuelto desde la última revisión:** T-11 (persistencia en DynamoDB del almacén de
idempotencia y del repositorio de transacciones).

---

## 1. Bloqueantes del nivel 2 en producción

Las tres condiciones del ADR-0007. Hasta que las tres se cumplan, **el nivel 2 no puede
ofrecerse a ningún tenant en producción**, con independencia de que el código esté terminado
y probado.

| # | Pendiente | Depende de | Estado |
| :-- | :---- | :---- | :---- |
| B-01 | **Contratar la TSA cualificada** con un PCSC habilitado en Paraguay (Confirma, VIT, CODE 100, Documenta, SOS Tecnología). Sin fecha cierta de un tercero, una firma con certificado efímero es inverificable a futuro (ADR-0004) | Negocio | Abierto |
| B-02 | **Emitir el certificado real de la CA intermedia** sobre la clave que ya vive en KMS. Hoy `dev` usa una raíz autofirmada generada por Terraform | SecOps + PKI | Abierto |
| B-03 | **Comunicar el inicio de actividades a la DGFDCE del MIC** y aparecer en el listado público de PSCNC. Plazo legal: 3 meses desde el inicio efectivo de la prestación. Requiere REPSE previo | Legal + Negocio | Abierto |

Mientras tanto, `dev` opera con CA autofirmada y TSA de prueba **etiquetadas en cada
certificado y en cada acta** (`environment=dev`, `tsa=test`).

---

## 2. Verificaciones normativas sin fuente de primera mano

Estas afirmaciones sostienen decisiones ya tomadas y **provienen de documentos de análisis,
no del texto oficial**. No están en el repositorio y nadie del equipo las leyó de primera
mano.

| # | Qué hay que verificar | Qué decisión sostiene | Riesgo si es falsa |
| :-- | :---- | :---- | :---- |
| N-01 | **Texto de la Res. MIC N.º 262/2024 (`DOC-ICPP-20 v2.0`)**: qué algoritmos admite el perfil del certificado no cualificado | ADR-0006, elección de `RSA_4096` | Si admite ECDSA, se pierde una optimización. Si **exige** algo distinto de RSA-4096, el perfil emitido no cumple la norma |
| N-02 | **Texto de la Res. SS.SG. N.º 210/2025**, arts. 4 y 9 | Norma citada en la constancia del perfil `PY` | La constancia citaría mal la norma que la habilita |
| N-03 | **Ley N.º 6822/2021 y Decreto N.º 7576/2022** | Todo el marco de PSCNC | — |
| N-04 | Número **PEN** de la organización para el OID de política de certificado | Extensión `certificatePolicies` | Hoy el OID es un marcador de posición |

**Acción concreta:** los textos oficiales tienen que entrar al repositorio antes de que se
los cite en producción. Una norma sin su PDF es una cita que nadie puede contrastar.

---

## 3. Revisión legal pendiente

| # | Pendiente | Detalle |
| :-- | :---- | :---- |
| L-01 | **Revisión legal de la lista de actos excluidos** (`legal_guard`) por asesoría paraguaya | La lista se construyó por criterio técnico. Su historial en el control de versiones es evidencia de diligencia, pero no sustituye el dictamen |
| L-02 | **Datos de identificación del prestador en la DPSC** | El documento tiene campos entre corchetes: razón social, registro público, REPSE, representante legal, dominio, contacto del CISO |
| L-03 | **Coherencia entre la DPSC y el algoritmo implementado** | La DPSC declara RSA-4096. Si N-01 cambia la decisión del ADR-0006, **la DPSC debe corregirse antes de presentarse** |
| L-04 | **Póliza de responsabilidad civil voluntaria** | No exigible a un PSCNC, pero recomendada por el tratamiento de biometría de terceros. Decisión de negocio |
| L-05 | **Consulta escrita al MIC** sobre el alcance del registro | Cierra el único punto opinable del encuadre |

---

## 4. Alcance técnico diferido

| # | Pendiente | Por qué se difiere |
| :-- | :---- | :---- |
| T-13 | **La CA raíz autofirmada de `dev` se genera a mano, no con Terraform** | El encargo preveía generarla en la IaC. Hoy la producen las pruebas y el entorno local; falta el recurso de Terraform que la cree y la publique para `dev`. No bloquea el desarrollo del nivel 2 |
| T-01 | **PAdES-B-LTA** para contratos de larga duración | Exige recolectar la cadena completa de validación (OCSP/CRL) e incrustarla en `/DSS`. El nivel B-T ya es suficiente mientras el sellado de tiempo esté garantizado (ADR-0004) |
| T-02 | **Habilitación comercial de la jurisdicción `BO`** | El perfil es estructural y está marcado `sin_validacion_legal`. Exige documentos fuente bolivianos y revisión legal local (ADR-0008) |
| T-03 | **Dígito verificador de la cédula paraguaya** | La validación comprueba formato, no dígito verificador |
| T-04 | **Modo COMPLIANCE de S3 Object Lock no se puede simular fielmente** en pruebas locales | Se valida en el entorno `dev` real (ADR-0003) |
| T-05 | **Alta automatizada de tenant** | Crear un tenant implica claves, alias y políticas de KMS: es una operación de infraestructura, no un registro en una tabla (ADR-0006) |
| T-06 | **El panel B2B pasa de `static` a `node` en `.devsecops.yml`** | Hoy es un prototipo con datos simulados y sin suite de pruebas. Al convertirse en producto necesita Vitest y quedar sujeto al umbral de cobertura |
| T-07 | **Límite de tiempo en la extracción de texto del PDF** | Ya no hay CVE abiertas en pypdf —se actualizó a 6.16.2—, pero la mitigación sigue teniendo sentido por sí misma: `legal_guard` analiza un PDF que envía el tenant, y ni el límite de tamaño (25 MiB) ni el de caracteres (200.000) detienen un bucle infinito. Deja de ser urgente y pasa a ser defensa en profundidad |
| T-08 | **WAF con limitación de tasa sobre CloudFront y egreso restringido** | Excepciones AWS-0011 y AWS-0104 del manifiesto, con vencimiento el 2026-12-02. El egreso definitivo depende de conocer el rango de la TSA (B-01) |
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

## 5. Configuración remota de GitHub (la ejecuta el propietario)

El bootstrap del estándar se ejecutó con `--sin-gh`: crear variables y secretos, y
aplicar rulesets, son cambios en la cuenta de GitHub y no los hace un agente.

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

**Orden que conviene respetar:** el check tiene que haber corrido y pasado **antes** de
exigirlo. Aplicar el ruleset sobre un check que nunca se ejecutó deja el repositorio
bloqueado esperando algo que puede fallar por causas todavía desconocidas, y obliga a
depurar el pipeline con `main` ya protegido.

---

## 6. Decisiones de negocio abiertas

| # | Pregunta | Quién decide |
| :-- | :---- | :---- |
| D-01 | ¿Se ofrece custodia del PDF firmado como servicio contratable? Hoy el nivel 2 procesa en memoria y no conserva | Producto |
| D-02 | ¿Aislamiento físico (cuenta AWS dedicada) para qué tipo de tenant? El ADR-0005 lo contempla como modelo *silo* opcional | Producto + Arquitectura |
| D-03 | Política de precios por nivel de servicio y por transacción | Negocio |
