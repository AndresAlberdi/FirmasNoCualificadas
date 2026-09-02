# Ruta de Cumplimiento Administrativo ante el MIC (PSCNC)

Checklist operativo para la constitución y mantenimiento del estatus de **Prestador de
Servicios de Confianza No Cualificado** en la República del Paraguay. Este documento se
mantiene sincronizado con la ejecución técnica del repositorio: cada control técnico
declarado ante la autoridad debe existir en el código o en Terraform.

> Fuente normativa: Ley N.º 6822/2021 · Decreto Reglamentario N.º 7576/2022 ·
> Resolución MIC N.º 262/2024 (`DOC-ICPP-20 v2.0`) · Decreto N.º 6866/2011 (REPSE) ·
> Resoluciones MITIC N.º 277/2020, 553/2024 y 1385/2022.
> **Verificar la vigencia de cada norma con la autoridad antes de presentar.**

---

## Fase 1 — Constitución societaria (previa)

- [ ] Sociedad constituida en Paraguay (S.A., S.R.L. o EAS) con objeto social que incluya
      tecnología de la información o servicios de software.
- [ ] RUC en estado **ACTIVO**.
- [ ] Patente comercial municipal vigente.
- [ ] Acta de la última asamblea (sociedades anónimas).
- [ ] Póliza de responsabilidad civil profesional dimensionada según el régimen de
      responsabilidad aplicable (ver `diseno/regimen-responsabilidad-seguros-servicios-confianza-paraguay.md`).

## Fase 2 — Inscripción en el REPSE

| Ítem | Dato |
| :-- | :-- |
| Ventanilla | Portal VUE — `www.vue.org.py` |
| Modalidad | 100 % electrónica |
| Costo | Gratuito |
| SLA declarado | 48 horas hábiles |

- [ ] Constancia de RUC.
- [ ] Cédula de identidad de directores o representantes legales.
- [ ] Escritura de constitución inscripta.
- [ ] Acta de la última asamblea.
- [ ] Patente comercial vigente.
- [ ] Planilla de IPS o factura comercial, si hay empleados registrados.
- [ ] Responsable técnico designado, inscripto a su vez en el REPSE, con título o matrícula
      y contrato que lo vincule a la sociedad.

## Fase 3 — Notificación de inicio de actividades a la DGFDCE

**Plazo improrrogable: tres (3) meses desde el inicio efectivo de la prestación comercial**
(Art. 15 Ley N.º 6822/2021 y Art. 5 Decreto N.º 7576/2022). El incumplimiento habilita
sumario administrativo y multa.

| Ítem | Dato |
| :-- | :-- |
| Destinatario | Dirección General de Firma Digital y Comercio Electrónico (MIC) |
| Canal | `info-dgce@mic.gov.py` |
| Autorización previa | No requerida (régimen de comunicación posterior) |

- [ ] Formulario oficial de comunicación técnica, firmado digitalmente.
- [ ] **Declaración de Prácticas de los Servicios de Confianza (DPSC)** — base en
      `diseno/declaracion-practicas-perfiles-pscnc.md`. Debe describir con exactitud lo
      que este repositorio implementa:
  - [ ] Algoritmos: SHA-256, RSASSA-PKCS1-v1_5 / RSASSA-PSS, RSA-4096 para la CA.
  - [ ] Custodia de claves: AWS KMS, HSM FIPS 140-2 Nivel 3, sin exportación.
  - [ ] Perfil de certificado efímero conforme a `DOC-ICPP-20 v2.0` (ver ADR-0004).
  - [ ] Onboarding: OCR/MRZ, biometría facial con prueba de vida, umbral ≥ 95 %, AML/PEP.
  - [ ] Evidencias: DynamoDB + S3 Object Lock modo Compliance, retención ≥ 2 años.
  - [ ] Seguridad perimetral: WAF, API Gateway, TLS 1.3, mTLS/HMAC, rate limiting.
  - [ ] Plan de continuidad, respaldo y respuesta a incidentes.
- [ ] Evidencia de adecuación del perfil de certificados a la Resolución N.º 262/2024.
- [ ] Constancia de inscripción en el REPSE.

## Fase 4 — Obligaciones permanentes post-registro

| Obligación | Frecuencia / plazo | Control técnico en este repositorio |
| :-- | :-- | :-- |
| Notificación de incidentes a DGFDCE y CERT-Py | 24 horas | `docs/RUNBOOK-break-glass.md`, alarmas SNS del módulo `observability` |
| Publicación en el listado oficial (`www.acraiz.gov.py`) | Al alta | — |
| Retención de evidencias | ≥ 2 años tras el fin de efectos jurídicos | S3 Object Lock Compliance en `evidence-vault-s3` |
| Prohibición de uso comercial de datos biométricos | Permanente | Política de acceso y log de revelación de PII |
| Análisis de vulnerabilidades y pentesting | Antes de cada despliegue crítico | Workflow `security.yml`, pentest externo anual |
| Actualización de la DPSC ante cambios técnicos | Ante cada cambio material | CODEOWNERS sobre `crypto/` y `kms-intermediate-ca/` |
| Publicación y refresco de la CRL | Diaria | Módulo `crl-distribution` + `pscnc.jobs.crl_publisher` |

## Fase 5 — Restricciones de uso del servicio

El agente de cumplimiento (`pscnc.compliance.legal_guard`) bloquea la firma de documentos
cuyo objeto esté excluido de la firma electrónica simple o requiera forma solemne.
La lista configurada debe ser revisada y aprobada por asesoría legal paraguaya antes de
producción, y toda modificación queda registrada en el control de versiones como evidencia
de diligencia.
