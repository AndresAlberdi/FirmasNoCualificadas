# Política de Seguridad — PSCNC FENC Paraguay

## 1. Reporte de vulnerabilidades

Las vulnerabilidades deben reportarse a `secops@<dominio>.com.py` cifradas con la clave
PGP publicada en `https://<dominio>.com.py/.well-known/security.txt`. No abra issues
públicos con detalles explotables.

Compromiso de respuesta: acuse en 24 horas hábiles, triage en 72 horas.

## 2. Obligaciones regulatorias de notificación

Como PSCNC inscripto, ante cualquier incidente que afecte significativamente la
confidencialidad, integridad o disponibilidad de las firmas o de los datos personales
de los firmantes rige un **plazo máximo de 24 horas** para notificar (Art. 6 del
Decreto N.º 7576/2022 y Resolución MITIC N.º 1385/2022):

| Destinatario | Canal | Plazo |
| :-- | :-- | :-- |
| DGFDCE — Ministerio de Industria y Comercio | `info-dgce@mic.gov.py` | 24 h |
| CERT-Py — MITIC | canal oficial de reporte de incidentes | 24 h |
| Clientes B2B afectados | webhook `security.incident` + correo al contacto contractual | 24 h |

El procedimiento operativo completo está en [`docs/RUNBOOK-break-glass.md`](docs/RUNBOOK-break-glass.md).

## 3. Superficie crítica

| Activo | Clasificación | Control primario |
| :-- | :-- | :-- |
| Clave privada de la CA Intermedia | Crítico — pérdida total de confianza | AWS KMS, HSM FIPS 140-2 Nivel 3, sin exportación, política de clave con separación de funciones |
| Claves efímeras del firmante | Crítico — transitorio | Generadas en memoria del contenedor, destruidas tras la firma, nunca persistidas |
| Expediente de evidencias | Crítico — valor probatorio | S3 Object Lock modo Compliance, retención 2 años, sello electrónico |
| Datos biométricos del onboarding | Datos personales sensibles | Cifrado SSE-KMS, enmascaramiento en UI, log de revelación de PII |
| Credenciales B2B (HMAC/API Keys) | Alto | AWS Secrets Manager con rotación automática |

## 4. Reglas de desarrollo no negociables

1. Ninguna clave privada, secreto o dato personal real puede escribirse en el
   repositorio, en logs o en mensajes de excepción.
2. Toda operación de firma se realiza a través de `kms:Sign`; está prohibido introducir
   código que materialice la clave de la CA en memoria del proceso.
3. Los logs son estructurados y aplican redacción de PII (`pscnc.logging_setup`).
   La cédula de identidad se registra siempre truncada.
4. Los cambios en `services/src/pscnc/crypto/` y en `infra/terraform/modules/kms-intermediate-ca/`
   requieren revisión de dos personas (CODEOWNERS) y actualización de la DPSC si
   alteran algoritmos, perfiles de certificado o custodia de claves.
5. Toda dependencia nueva debe declararse en `services/pyproject.toml` con versión
   acotada y pasar el escaneo de vulnerabilidades del pipeline.
