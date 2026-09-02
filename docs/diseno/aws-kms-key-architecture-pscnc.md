# Diseño de Arquitectura Criptográfica: Gestión de Llaves en AWS KMS e IAM para PSCNC en Paraguay

Este documento técnico contiene la especificación de ingeniería para implementar el subsistema de custodia criptográfica de la **Entidad de Certificación Intermedia (Intermediate CA)** y las firmas electrónicas no cualificadas (FENC). Está diseñado con un nivel de detalle riguroso (JSON, flujos y políticas IAM) para ser procesado directamente por **Claude AI** o herramientas IAC (Terraform/CloudFormation) para automatizar el despliegue bajo los principios de *Security by Design* y mínimo privilegio.

---

## 1. Diseño del Par de Claves de la Intermediate CA en AWS KMS

Para operar como un PSCNC cumpliendo con las normativas paraguayas (Ley N.º 6822/2021) y estándares internacionales compatibles con los lectores estándar (ej. Adobe Acrobat), el sistema actuará como una CA subordinada o intermedia. La clave privada de esta CA se creará de forma exclusiva dentro de **AWS KMS** como una clave asimétrica para firmas.

### 1.1 Configuración Técnica de la Clave KMS
*   **Key Spec (Especificación de Clave):** `RSA_4096` (o en su defecto `RSA_2048` para reducir la latencia de cómputo en firmas masivas, aunque `RSA_4096` es el estándar recomendado para CAs subordinadas en políticas corporativas de largo plazo).
*   **Key Usage (Uso de Clave):** `SIGN_VERIFY`. Esto restringe la llave para que solo pueda realizar operaciones de firma digital y verificación, impidiendo operaciones de cifrado/descifrado (`ENCRYPT_DECRYPT`).
*   **Hardware de Resguardo:** Módulos de Seguridad de Hardware (HSM) dedicados de AWS con certificación **FIPS 140-2 Nivel 3**.
*   **Bypass de Extracción:** El diseño garantiza que la clave privada nunca saldrá del HSM de AWS KMS en texto plano ni cifrado bajo ninguna circunstancia. Toda firma de certificados efímeros de usuarios o emisión de CRLs se realiza enviando el hash a la API `Sign` de KMS.

---

## 2. Política de Clave de AWS KMS (KMS Key Policy) de Producción

En AWS KMS, las políticas de clave son la primera y más importante línea de defensa. Esta política implementa la **separación de funciones** (*Separation of Duties*) dividiendo el acceso entre Administradores de Ciberseguridad (SecOps) y el motor de firma automatizado (Fargate Task).

```json
{
  "Version": "2012-10-17",
  "Id": "KMS-Key-Policy-PSCNC-Paraguay-Intermediate-CA",
  "Statement": [
    {
      "Sid": "Allow-Root-Account-Full-Control-Manage-Only",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow-SecOps-Administrators-Key-Management",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::123456789012:role/SecOps-KMS-Admin-Role",
          "arn:aws:iam::123456789012:role/Emergency-BreakGlass-Admin-Role"
        ]
      },
      "Action": [
        "kms:Create*",
        "kms:Describe*",
        "kms:Enable*",
        "kms:List*",
        "kms:Put*",
        "kms:Update*",
        "kms:Revoke*",
        "kms:Disable*",
        "kms:Get*",
        "kms:TagResource",
        "kms:UntagResource",
        "kms:ScheduleKeyDeletion",
        "kms:CancelKeyDeletion"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Allow-Fargate-Signing-Service-Only-Sign-And-GetPublicKey",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/ECS-Fargate-Signer-Task-Execution-Role"
      },
      "Action": [
        "kms:Sign",
        "kms:GetPublicKey",
        "kms:DescribeKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:SigningAlgorithm": [
            "RSASSA_PSS_SHA_256",
            "RSASSA_PKCS1_V1_5_SHA_256"
          ]
        }
      }
    },
    {
      "Sid": "Enforce-CloudTrail-Logging-And-Prevent-Anonymous-Access",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "kms:*",
      "Resource": "*",
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
```

### Controles de Seguridad Aplicados en la Política KMS:
1.  **Mínimo Privilegio Operativo:** El rol del microservicio de firma (`ECS-Fargate-Signer-Task-Execution-Role`) solo tiene permisos de ejecución para `kms:Sign` y lectura de metadata pública de la clave. No puede modificar ni eliminar la clave.
2.  **Restricción de Algoritmo:** La condición `kms:SigningAlgorithm` fuerza al servicio a utilizar únicamente algoritmos aprobados por la Infraestructura de Clave Pública de Paraguay (ICPP): `RSASSA_PSS_SHA_256` o `RSASSA_PKCS1_V1_5_SHA_256`.
3.  **Forzar Encriptación en Tránsito (mTLS/TLS 1.3):** El bloque `Deny` con la condición `aws:SecureTransport: false` bloquea cualquier intento de llamada a la API de KMS que no viaje sobre canales TLS seguros.

---

## 3. Roles de IAM y Políticas de Mínimo Privilegio para el Signer Task

El microservicio de firma que corre sobre **Amazon ECS / AWS Fargate** requiere políticas de IAM granulares adjuntas a su rol de ejecución de tareas (*Task Role*).

### 3.1 Trust Policy del Fargate Task Role (Relación de Confianza)
Establece que únicamente el servicio de contenedores ECS puede asumir este rol para mitigar ataques de escalación lateral.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:ecs:us-east-1:123456789012:namespace/pscnc-signing-namespace"
        }
      }
    }
  ]
}
```

### 3.2 IAM Inline Policy para Operaciones del Signer (Firma e Integridad)
Esta política se adjunta directamente al rol de ejecución de Fargate y le permite interactuar exclusivamente con la clave KMS intermedia de la CA subordinada y registrar las evidencias en la base de datos inmutable.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowKMSSigningOnSpecificKeyOnly",
      "Effect": "Allow",
      "Action": [
        "kms:Sign",
        "kms:GetPublicKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/ca1ab23c-45de-67fg-89hi-jklmnopq1234"
    },
    {
      "Sid": "AllowS3UploadForSignedPDFsAndEvidences",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectTagging"
      ],
      "Resource": [
        "arn:aws:s3:::pscnc-paraguay-signed-vault/*",
        "arn:aws:s3:::pscnc-paraguay-evidence-trail/*"
      ]
    },
    {
      "Sid": "AllowDynamoDBLogAuditTrailWrite",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:123456789012:table/PSCNC_Audit_Trail"
    }
  ]
}
```

---

## 4. Ciclo de Vida de los Certificados Cortos (Short-Lived Certificates) y CRLs

El sistema no emite certificados cualificados de larga vigencia, sino certificados X.509 de un solo uso o de muy corta duración (ej. 15 minutos de vigencia) asociados lógicamente al onboarding biométrico de cada transacción.

### 4.1 Flujo Lógico de Firma Efímera con Custodia Criptográfica

```
[Onboarding Completado] ──(Genera Par de Claves Efímero en AWS Fargate)
                                       │
                                       ▼
  (Genera CSR con datos de Cédula Paraguaya del Firmante)
                                       │
                                       ▼
  (Envía CSR a la CA Intermedia en AWS KMS para Firma de Certificado)
                                       │
                                       ▼
   (Inyecta Certificado X.509 Corto + Hash de Firma del PDF)
                                       │
                                       ▼
(Destruye Clave Privada Efímera del Usuario - Sin Dejar Rastro del Llavero)
```

### 4.2 Automatización de la Publicación de CRL (Listas de Revocación)
Aunque los certificados son de corto ciclo, el estándar de firma de PDF exige que el sistema PSCNC sea capaz de validar y, de ser necesario, revocar la autoridad de la CA intermedia.

1.  **Almacenamiento de CRL:** La CRL generada (un archivo `.crl` firmado por la llave maestra del PSCNC en AWS KMS) se guarda en un bucket privado de **Amazon S3** configurado con **Object Lock** en modo "Compliance" con retención de 2 años.
2.  **Distribución de Alta Disponibilidad:** Se expone la CRL mediante **Amazon CloudFront** con un TTL corto para asegurar que la descarga e inspección por software como Adobe Reader sea rápida y con baja latencia en Paraguay.
3.  **Monitoreo con AWS EventBridge:** Una regla programada ejecuta una función **AWS Lambda** cada 24 horas para generar una CRL fresca firmada por KMS, incluso si no hay certificados intermedios revocados, asegurando que la marca temporal de actualización de la CRL nunca aparezca expirada en los clientes de validación.

---

## 5. Prácticas de Revocación de Emergencia (Plano Break-Glass)

En caso de sospecha fundada de compromiso de la clave privada de la CA residente en AWS KMS:

1.  **Detección y Alerta:** Una llamada API inusual a KMS dispara alertas inmediatas a través de **AWS GuardDuty** y **Amazon EventBridge** hacia un canal seguro de incidentes (Slack/Teams via SNS).
2.  **Invocación del Rol Break-Glass:** Un oficial de seguridad de SecOps inicia sesión mediante mTLS y asume el rol `Emergency-BreakGlass-Admin-Role`.
3.  **Ejecución de Comando de Bloqueo Técnico:** Deshabilitación inmediata de la clave KMS intermedia para mitigar ataques continuos de firmado:
    ```bash
    aws kms disable-key --key-id "arn:aws:kms:us-east-1:123456789012:key/ca1ab23c-45de-67fg-89hi-jklmnopq1234"
    ```
4.  **Generación de la CRL Final:** El script automatizado genera la última CRL marcando la revocación total de todas las firmas posteriores al evento de intrusión.
5.  **Notificación Obligatoria de 24 horas al MIC/MITIC:** El oficial legal ejecuta el protocolo reglamentario de alerta enviando la incidencia por canal cifrado a la DGFDCE del MIC (`info-dgce@mic.gov.py`) y al **CERT-Py** del MITIC.

---

## 6. Prompt para Claude AI: Generación del Código IaC (Terraform)

Para que Claude AI u otro LLM de ingeniería proceda a implementar automáticamente este subsistema criptográfico en código de infraestructura, puedes proporcionarle el siguiente prompt refinado:

> **PROMPT PARA CLAUDE AI:**
> *"Actúa como un arquitecto de infraestructura en AWS experto en criptografía de clave pública y ciberseguridad. Basándote en el diseño del subsistema de firma para el PSCNC en Paraguay, genera el código de Terraform estructurado y limpio que incluya:
> 1. Un recurso `aws_kms_key` asimétrico configurado para firma RSA_4096 (con alias `alias/pscnc-paraguay-intermediate-ca`), habilitando la rotación de claves y configurando la Key Policy que se define en el documento técnico (Sid: Allow-Root, Allow-SecOps, Allow-Fargate, Enforce-CloudTrail-Logging).
> 2. El recurso `aws_iam_role` para la tarea de ECS Fargate (`ECS-Fargate-Signer-Task-Execution-Role`) con su correspondiente trust policy.
> 3. La política inline `aws_iam_role_policy` adjunta al rol de Fargate que permita exclusivamente `kms:Sign` y `kms:GetPublicKey` sobre el ARN de la llave KMS creada, y los permisos granulares para S3 (buckets de firmas y evidencias) y DynamoDB.
> 4. Asegura que todo el código cumpla con los estándares de AWS Well-Architected Framework, forzando cifrado en tránsito (TLS 1.2/1.3) y sin usar variables por defecto desprotegidas."*

---
🤖 **¿Qué te gustaría hacer a continuación?**
*   **Guardar en el plano técnico principal:** ¿Quieres que actualicemos la versión principal de tu plano de arquitectura (`blueprint-firma-no-cualificada-paraguay-v2.md`) integrando de manera definitiva esta sección criptográfica como un nuevo capítulo técnico?
*   **Simular un script de firmado en Python:** Podríamos programar un script funcional de Python que use la librería `boto3` para mandar a llamar a AWS KMS para firmar un hash SHA-256 utilizando el algoritmo `RSASSA_PSS_SHA_256`, demostrando la ingeniería de cifrado en frío.
