# Runbook · Compromiso de la CA Intermedia y respuesta a incidentes

Severidad SEV-1. Este procedimiento se ejecuta ante sospecha fundada de compromiso de la
clave privada de la CA intermedia residente en AWS KMS, o ante cualquier incidente que
afecte la integridad de la pista de auditoría.

**Regla de oro:** primero se detiene la emisión, después se investiga. Una firma emitida
durante una ventana de compromiso contamina todas las evidencias posteriores.

---

## 0. Disparadores

| Señal | Origen |
| :-- | :-- |
| Volumen anómalo de `kms:Sign` fuera del patrón horario | Alarma CloudWatch `pscnc-kms-sign-anomaly` |
| `kms:Sign` desde un principal distinto del Task Role del signer | CloudTrail + EventBridge |
| Hallazgo de credenciales expuestas o de escalación de privilegios | GuardDuty |
| Divergencia entre el ítem de DynamoDB y el objeto WORM en S3 | Job de conciliación diario |
| Reporte externo de firma no reconocida por el titular | Soporte / cliente B2B |

## 1. Contención (objetivo: 15 minutos)

1. El oficial de guardia de SecOps declara SEV-1 y abre el canal de incidente.
2. Asumir el rol de emergencia con MFA obligatorio:
   ```bash
   aws sts assume-role \
     --role-arn arn:aws:iam::<ACCOUNT_ID>:role/Emergency-BreakGlass-Admin-Role \
     --role-session-name breakglass-$(date -u +%Y%m%dT%H%M%SZ) \
     --serial-number arn:aws:iam::<ACCOUNT_ID>:mfa/<USUARIO> \
     --token-code <TOTP>
   ```
3. Deshabilitar la clave de la CA intermedia (detiene toda emisión de certificados):
   ```bash
   aws kms disable-key --key-id alias/pscnc-paraguay-intermediate-ca
   ```
4. Escalar el servicio de firma a cero tareas para evitar respuestas parciales:
   ```bash
   aws ecs update-service --cluster pscnc-prod --service pscnc-signer --desired-count 0
   ```
5. Registrar en el canal de incidente la hora UTC exacta de cada acción.

> El bucket de evidencias tiene Object Lock en modo Compliance: **no intente borrar ni
> modificar objetos**. La respuesta nunca implica destruir evidencia.

## 2. Notificación regulatoria (plazo máximo: 24 horas)

| Destinatario | Canal | Responsable |
| :-- | :-- | :-- |
| DGFDCE — MIC | `info-dgce@mic.gov.py` | Oficial de cumplimiento |
| CERT-Py — MITIC | canal oficial de incidentes | Oficial de cumplimiento |
| Clientes B2B afectados | webhook `security.incident` + contacto contractual | Gerencia de cuentas |

Contenido mínimo de la notificación: fecha y hora de detección, naturaleza del incidente,
sistemas y datos afectados, número estimado de transacciones comprometidas, medidas de
contención adoptadas y punto de contacto técnico.

## 3. Delimitación de la ventana de compromiso

1. Determinar `T_compromiso_inicio` a partir del primer evento anómalo en CloudTrail.
2. Consultar las transacciones firmadas desde ese instante:
   ```bash
   aws dynamodb query --table-name PSCNC_Audit_Trail --index-name GSI2 \
     --key-condition-expression "GSI2PK = :c AND GSI2SK >= :t" \
     --expression-attribute-values '{":c":{"S":"CLIENT#<TENANT>"},":t":{"S":"<ISO8601>"}}'
   ```
3. Marcar cada sesión afectada con estado `COMPROMISED` escribiendo una versión nueva
   (`METADATA#V{n+1}`). **Nunca sobrescribir la versión previa.**

## 4. Revocación y CRL final

1. Revocar la CA intermedia en la CRL con `reasonCode = keyCompromise` y la fecha
   `T_compromiso_inicio` como `invalidityDate`:
   ```bash
   services/.venv/bin/python -m pscnc.jobs.crl_publisher \
     --revoke-intermediate --reason key-compromise --invalidity-date <ISO8601>
   ```
2. Verificar la publicación y la propagación en CloudFront (TTL corto configurado a 300 s).
3. Comunicar el punto de distribución de la CRL a los clientes B2B y al MIC.

## 5. Recuperación

1. Generar un par de claves nuevo para la CA intermedia en KMS (nunca reutilizar el alias
   anterior; crear `alias/pscnc-paraguay-intermediate-ca-v{n+1}`).
2. Reemitir la solicitud de certificación de la CA intermedia ante la autoridad
   correspondiente y desplegar la cadena nueva.
3. Rotar todas las credenciales relacionadas: secretos HMAC de clientes B2B, credenciales
   de la TSA y claves de acceso de CI/CD.
4. Restablecer el servicio de firma con despliegue canario y verificación de una firma de
   prueba contra Adobe Acrobat y el validador del MIC antes de reabrir el tráfico.

## 6. Cierre

- [ ] Informe post-mortem sin atribución de culpa, con línea de tiempo en UTC.
- [ ] Actualización de la DPSC si cambió algún control declarado.
- [ ] Comunicación final a la DGFDCE con las medidas correctivas adoptadas.
- [ ] Alta de las acciones correctivas en el backlog con responsable y fecha.
- [ ] Ejercicio de simulacro de este runbook agendado dentro de los 90 días siguientes.
