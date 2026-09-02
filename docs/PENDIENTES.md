# Pendientes explícitos

Lo que **no** está resuelto, con quién depende de ello. La regla que gobierna este archivo:
un pendiente se declara acá o no existe. **Nada se simula en silencio.**

Un pendiente simulado sin declarar es peor que uno abierto: produce un artefacto que parece
válido, y alguien lo va a presentar como si lo fuera.

Última revisión: 2026-09-02.

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
| T-01 | **PAdES-B-LTA** para contratos de larga duración | Exige recolectar la cadena completa de validación (OCSP/CRL) e incrustarla en `/DSS`. El nivel B-T ya es suficiente mientras el sellado de tiempo esté garantizado (ADR-0004) |
| T-02 | **Habilitación comercial de la jurisdicción `BO`** | El perfil es estructural y está marcado `sin_validacion_legal`. Exige documentos fuente bolivianos y revisión legal local (ADR-0008) |
| T-03 | **Dígito verificador de la cédula paraguaya** | La validación comprueba formato, no dígito verificador |
| T-04 | **Modo COMPLIANCE de S3 Object Lock no se puede simular fielmente** en pruebas locales | Se valida en el entorno `dev` real (ADR-0003) |
| T-05 | **Alta automatizada de tenant** | Crear un tenant implica claves, alias y políticas de KMS: es una operación de infraestructura, no un registro en una tabla (ADR-0006) |

---

## 5. Decisiones de negocio abiertas

| # | Pregunta | Quién decide |
| :-- | :---- | :---- |
| D-01 | ¿Se ofrece custodia del PDF firmado como servicio contratable? Hoy el nivel 2 procesa en memoria y no conserva | Producto |
| D-02 | ¿Aislamiento físico (cuenta AWS dedicada) para qué tipo de tenant? El ADR-0005 lo contempla como modelo *silo* opcional | Producto + Arquitectura |
| D-03 | Política de precios por nivel de servicio y por transacción | Negocio |
