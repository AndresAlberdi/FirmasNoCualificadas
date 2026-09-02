# Declaración de Prácticas de los Servicios de Confianza (DPSC) y Perfiles Técnicos
## En cumplimiento de la Resolución MIC N.º 262/2024 (Documento DOC-ICPP-20 Versión 2.0)
### Para Prestadores de Servicios de Confianza No Cualificados (PSCNC) de Firma Electrónica No Cualificada (FENC)

---

## Control de Documento y Repositorio Regulatorio
* **Documento:** Declaración de Prácticas de los Servicios de Confianza (DPSC) y Especificación de Perfiles Técnicos
* **Versión:** 1.0 (Modelo de Producción)
* **Fecha de Emisión:** 22 de Agosto de 2026
* **Estado:** Vigente / Listo para Fiscalización Administrativa
* **Autor de Referencia:** Dirección de Cumplimiento Técnico y Ciberseguridad (PSCNC-SaaS)
* **Destinatario Final:** Dirección General de Firma Digital y Comercio Electrónico (DGFDCE) - Ministerio de Industria y Comercio (MIC), República del Paraguay.
* **Correo Oficial de Notificación:** `info-dgce@mic.gov.py`

---

## Sección 1: Introducción, Propósito y Alcance Legal

### 1.1 Objeto y Marco Normativo
La presente **Declaración de Prácticas de los Servicios de Confianza (DPSC)** describe de manera pormenorizada las políticas operacionales, los esquemas de seguridad lógica y física, la metodología criptográfica y el ciclo de vida de los certificados e identidades de la plataforma SaaS B2B, constituida en la República del Paraguay bajo la figura de **Prestador de Servicios de Confianza No Cualificado (PSCNC)**.

Este documento se redacta en estricto cumplimiento de:
1. **Ley N.º 6822/2021:** "De los Servicios de Confianza para las Transacciones Electrónicas, del Documento Electrónico y de los Documentos Transmisibles Electrónicos", la cual regula las firmas electrónicas cualificadas y no cualificadas, disponiendo el principio de no discriminación y equivalencia probatoria.
2. **Decreto Reglamentario N.º 7576/2022:** Que reglamenta la Ley N.º 6822/2021 y establece las formalidades de notificación de inicio de actividades operativas en un plazo de tres (3) meses.
3. **Resolución MIC N.º 262/2024:** Por la cual se aprueba el perfil técnico y los atributos del certificado electrónico para prestadores no cualificados de servicios de confianza, codificado como **DOC-ICPP-20 Versión 2.0**.
4. **Artículos 308 del Código Procesal Civil y 63 de la Ley N.º 6822/2021:** Que definen el régimen de admisibilidad judicial y la necesidad de estructurar evidencias tecnológicas inmutables para peritajes informáticos forenses.

### 1.2 Validez de la Firma Electrónica No Cualificada (FENC)
De acuerdo con el **Artículo 39 de la Ley N.º 6822/2021**, no se negará validez jurídica ni admisibilidad en procedimientos judiciales a una firma electrónica por el mero hecho de presentarse en formato electrónico o de no cumplir los requisitos de una firma cualificada. 

Para salvaguardar la autoría y la integridad de los contratos privados en caso de impugnación (desconocimiento de firma conforme al Art. 308 del CPC), la plataforma recopila una **Pista de Auditoría** (*Audit Trail*) inmutable respaldada por marcas de tiempo obtenidas de una Autoridad de Sellado de Tiempo (TSA) Cualificada autorizada por el MIC.

---

## Sección 2: Identificación del Prestador de Servicios de Confianza

El servicio de firma es operado y administrado por la entidad legal registrada en territorio paraguayo:

* **Denominación Social:** [Razón Social de tu Empresa S.A. / S.R.L.]
* **Registro de Comercio / Persona Jurídica:** Inscrita en la Dirección General de los Registros Públicos bajo el N.º [Número de Registro], Folio [Número], Año [Año].
* **Registro de Prestadores de Servicios (REPSE - MIC):** Registro obtenido a través del portal de la Ventanilla Única de Exportación (VUE) con ID N.º [Número de Registro REPSE] (conforme al Decreto N.º 6866/2011).
* **Domicilio Social:** Asunción, República del Paraguay.
* **Representante Legal:** [Nombre del Representante Legal], con C.I. N.º [Número].
* **Sitio Web de Publicación de la DPSC:** `https://pscnc.[tudominio].com/legal/dpsc/`
* **Contacto Técnico y Ciberseguridad:** `ciso@[tudominio].com`

---

## Sección 3: Declaración de Prácticas de los Servicios de Confianza (DPSC)

La plataforma tecnológica reside en la nube de **Amazon Web Services (AWS)** en la región de alta disponibilidad de Norteamérica (o Sudamérica según conveniencia de latencia), implementando seguridad física y lógica de extremo a extremo.

### 3.1 Proceso de Enrolamiento y Onboarding Completo (Identificación Remota)
Para garantizar el vínculo unívoco entre la persona física del firmante y el par de claves generado de forma temporal, se ejecuta un proceso asíncrono de Onboarding digital:
1. **Captura FOTO-CI:** Captura fotográfica de ambos lados de la Cédula de Identidad vigente emitida por la Policía Nacional del Paraguay.
2. **Motor OCR e Inteligencia Artificial:** Extracción de datos del documento (Nombres, Apellidos, Sexo, Nacionalidad, Fecha de Nacimiento y N.º de Cédula) y validación de coincidencia del formato.
3. **Validación de Zona MRZ (Machine Readable Zone):** Decodificación del formato estándar internacional de lectura mecánica de la cédula para validar que los datos lógicos internos correspondan unívocamente con el anverso visual.
4. **Biometría Facial y Prueba de Vida (Liveness Test):** Captura de una selfie en tiempo real mediante técnicas de análisis activo/pasivo para comprobar que el firmante es una persona física real en vivo (evitando ataques de presentación de fotos o videos).
5. **Score de Match Biométrico:** Contraste biométrico entre la selfie y la foto extraída de la cédula de identidad, requiriendo un **porcentaje de coincidencia mínimo de noventa y cinco por ciento (95%)** para autorizar la transacción.
6. **Verificación de Canales:** Validación activa del correo electrónico institucional o personal y del número de teléfono celular (WhatsApp) mediante el envío de un código de un solo uso (**OTP** de 6 dígitos con vigencia máxima de 5 minutos).
7. **Control AML/PEP:** Contraste automático contra bases de datos de personas expuestas políticamente (PEP) y listas de control de lavado de activos (AML) antes de habilitar la sesión de firma.
8. **Evidencia Tecnológica de Dispositivo:** Captura de la dirección IP pública del firmante, puerto de origen, marcas de tiempo UTC del servidor y la cabecera `User-Agent` del navegador.

### 3.2 Seguridad de la Infraestructura en la Nube (AWS)
La plataforma aplica el principio de **Seguridad por Diseño** (*Security by Design*) bajo las directivas del MITIC:
* **AWS WAF (Web Application Firewall):** Protege los endpoints públicos contra inyecciones SQL, scripts de sitios cruzados (XSS) y ataques distribuidos de denegación de servicio (DDoS).
* **Autenticación mTLS (Mutual TLS):** API Gateway configurada con TLS 1.3 forzado y autenticación de certificados mutuos para la conexión B2B con los sistemas ERP/CRM de los clientes corporativos.
* **Cifrado AES-256 en Reposo (SSE-KMS):** Los repositorios de evidencias en Amazon S3 y las bases de datos de auditoría en Amazon DynamoDB se encuentran cifrados con llaves administradas por el cliente en AWS KMS.

### 3.3 Gestión de Claves y Criptografía de la CA Subordinada (AWS KMS)
* **Hardware de Seguridad Criptográfica (HSM):** El PSCNC crea y resguarda la clave privada de su Entidad de Certificación Subordinada o Intermedia (Intermediate CA) en **AWS KMS**, operando sobre hardware dedicado certificado bajo el estándar de seguridad federal de EE. UU. **FIPS 140-2 Nivel 3**.
* **Protección de la Clave Privada:** La clave privada del PSCNC nunca es extraída, expuesta ni compartida. Todas las operaciones de firma sobre los certificados efímeros de los usuarios se ejecutan de manera lógica dentro del perímetro de seguridad de AWS KMS a través de la llamada API asimétrica `Sign`.
* **Algoritmos Criptográficos:** Se utilizan llaves asimétricas **RSA de 4096 bits** con funciones de hash **SHA-256** para el sellado de los certificados del usuario final.

### 3.4 Privacidad, Consentimiento y Protección de Datos Personales
De conformidad con el **Artículo 9 de la Ley N.º 6822/2021**:
* Los datos personales y biométricos se recolectan únicamente de forma directa y con el **consentimiento expreso e informado** del firmante, formalizado al iniciar el flujo de enrolamiento.
* Queda terminantemente prohibido utilizar los datos biométricos, fotos o selfies para cualquier finalidad comercial distinta a la autenticación de la firma en la transacción específica.
* Los registros biométricos del onboarding temporal se eliminan lógicamente del servidor en caliente una vez completado el match biométrico y la generación del expediente de evidencias, reteniendo únicamente el vector o score resultante y las capturas estáticas necesarias para la pista de auditoría forense.

### 3.5 Retención de Datos y Custodia Inmutable
* **Almacenamiento WORM:** La pista de auditoría completa, el documento PDF firmado resultante y el Documento de Evidencias consolidado se almacenan en buckets de **Amazon S3** con la opción **S3 Object Lock** configurada en modo **Cumplimiento** (*Compliance Mode*).
* **Plazo de Retención Mínimo:** Conforme a las directivas generales de servicios de confianza, los registros de auditoría y firmas se custodian por un período **mínimo de dos (2) años** a partir de la finalización de los efectos legales del documento comercial firmado. Durante este lapso, ninguna llamada API de borrado, administrador de base de datos ni usuario externo puede modificar o destruir los expedientes.

### 3.6 Plan de Respuesta y Reporte Obligatorio de Incidentes (24 Horas)
De acuerdo con el **Artículo 6 del Decreto Reglamentario N.º 7576/2022** y la **Resolución MIC N.º 1385/2022**:
* El CISO del PSCNC cuenta con un plan de mitigación automatizado en AWS. Ante cualquier quiebre, intrusión de base de datos o evento crítico que comprometa la disponibilidad o integridad del servicio de confianza o los datos de los usuarios, se notificará al MIC en un plazo **máximo e improrrogable de veinticuatro (24) horas** desde el conocimiento del incidente.
* La comunicación se enviará electrónicamente al correo **`info-dgce@mic.gov.py`** y al Centro de Respuestas a Incidentes Cibernéticos del MITIC (**CERT-Py**), remitiendo el reporte inicial con la descripción del incidente, medidas de contención y afectación estimada.

---

## Sección 4: Especificación del Perfil del Certificado Electrónico (DOC-ICPP-20 v2.0)

Conforme a la **Resolución N.º 262/2024 del MIC**, los certificados emitidos por un Prestador No Cualificado (PSCNC) para sus firmantes deben ceñirse de forma estricta a la plantilla técnica oficial. 

Nuestra plataforma implementa **Certificados de Corto Ciclo de Vida** (*Short-Lived Certificates / Ephemeral Certificates*). Este enfoque de ciberseguridad elimina el riesgo de robo o mal uso de la identidad a largo plazo, ya que las claves criptográficas del firmante se generan exclusivamente para la transacción en curso y expiran de forma automática minutos después de su creación.

### 4.1 Campos Estructurados ASN.1 de la Plantilla de Certificado X.509 de Usuario

La plantilla generada dinámicamente por la CA subordinada interna en AWS KMS contiene los siguientes metadatos lógicos basados en el estándar X.509 v3:

| Campo ASN.1 | Nombre Técnico | Tipo / Formato | Contenido Específico (Conforme a Res. 262/2024) |
| :--- | :--- | :--- | :--- |
| **Version** | Versión del Certificado | Integer | `v3` (Valor hexadecimal `0x02`). |
| **Serial Number** | Número de Serie | Positive Integer | Número entero positivo único autogenerado por la sesión criptográfica del PSCNC, no repetible. |
| **Signature Algorithm** | Algoritmo de Firma | Object Identifier (OID) | `sha256WithRSAEncryption` (OID: `1.2.840.113549.1.1.11`). |
| **Issuer** | Emisor del Certificado | Distinguished Name (DN) | Estructura jerárquica de la CA intermedia registrada:<br> `C=PY`<br>`O=[Razón Social del PSCNC]`<br>`CN=Autoridad Certificadora Subordinada [Nombre del PSCNC] FENC` |
| **Validity (NotBefore)** | Inicio de Validez | UTCTime / GeneralizedTime | Timestamp de la firma en formato UTC restando una ventana de gracia temporal de cinco minutos (ej. `T-5 minutos`). Evita problemas por desalineación de relojes de sistema. |
| **Validity (NotAfter)** | Fin de Validez | UTCTime / GeneralizedTime | Timestamp de expiración automática forzada a una (1) hora posterior al acto de la firma (ej. `T+1 hora`). Garantiza que el certificado sea exclusivamente de corto ciclo. |
| **Subject** | Identidad del Firmante | Distinguished Name (DN) | Datos unívocos del firmante extraídos de forma directa del Onboarding y validados con biometría facial:<br>`C=PY` (Paraguay)<br>`O=[Nombre del Cliente B2B del SaaS o PSCNC]`<br>`CN=[Nombres y Apellidos Completos según C.I.]`<br>`serialNumber=PY-[Número de Cédula sin puntos]-[Dígito Verificador]` |
| **Subject Public Key Info**| Clave Pública del Usuario | Public Key Bit String | Llave pública RSA de 2048 o 4096 bits (o ECDSA P-256) generada temporalmente en el sandbox criptográfico seguro para el usuario. |

### 4.2 Extensiones Obligatorias del Certificado X.509 v3

La plantilla de certificado inyecta de forma obligatoria las siguientes extensiones técnicas para guiar el software de validación (como Adobe Acrobat Reader o verificadores gubernamentales paraguayos):

#### 1. Key Usage (Uso de Llaves)
* **Atributo:** Crítico (`Critical = TRUE`).
* **Valor:** `digitalSignature`, `nonRepudiation` (Hexadecimal: `0x03` o bitmask binaria `11000000`).
* **Propósito:** Restringe el uso criptográfico de este par de claves únicamente para la autenticación de firma electrónica en transacciones y para el no repudio del firmante en el documento.

#### 2. Extended Key Usage (Uso Extendido de Llaves)
* **Atributo:** No Crítico (`Critical = FALSE`).
* **OIDs Permitidos:** `clientAuth` (OID: `1.3.6.1.5.5.7.3.2`) e `emailProtection` (OID: `1.3.6.1.5.5.7.3.4`).
* **Propósito:** Declara que el certificado está configurado para la autenticación remota del usuario en aplicaciones web y para proteger correos o workflow documentales.

#### 3. Basic Constraints (Restricciones Básicas)
* **Atributo:** Crítico (`Critical = TRUE`).
* **Valor:** `cA = FALSE`, `pathLenConstraint = None`.
* **Propósito:** Asegura y prueba que este certificado final de usuario no tiene capacidades de emisión de otros certificados (no es una Autoridad de Certificación).

#### 4. Authority Key Identifier (Identificador de Clave de la Autoridad)
* **Atributo:** No Crítico (`Critical = FALSE`).
* **Valor:** Hash SHA-1 de 160 bits derivado de la clave pública de la CA subordinada residente en AWS KMS.
* **Propósito:** Permite construir la cadena de confianza rápida vinculando el certificado del usuario final con la clave del PSCNC emisor.

#### 5. Subject Key Identifier (Identificador de Clave del Sujeto)
* **Atributo:** No Crítico (`Critical = FALSE`).
* **Valor:** Hash SHA-1 de 160 bits derivado de la clave pública efímera generada para el usuario final.
* **Propósito:** Identifica de forma unívoca el par de llaves del usuario para acelerar la validación lógica en los lectores de firma de PDFs.

#### 6. Certificate Policies (Políticas de Certificado)
* **Atributo:** No Crítico (`Critical = FALSE`).
* **OID Declarado:** `1.3.6.1.4.1.[Número_PEN_de_tu_Empresa].1.1.2` (OID personalizado registrado en la DPSC ante el MIC).
* **Propósito:** Declara formalmente que el certificado cumple con la presente DPSC y se emite bajo el régimen de firma electrónica no cualificada (FENC) regulada por la Ley N.º 6822/2021 de Paraguay.

---

## Sección 5: Guía de Generación de Certificados Efímeros para Claude AI

Esta especificación lógica permite que **Claude AI** programe de manera interactiva el backend del módulo de firma utilizando el SDK nativo de Python (`cryptography`).

A continuación se expone el código base en Python para la generación dinámica de la clave y el certificado efímero, integrando la estructura jerárquica de la **Resolución N.º 262/2024**:

```python
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generar_certificado_efimero_usuario(
    nombres_completos: str,
    cedula_paraguay: str,
    empresa_b2b: str,
    public_key_usuario: rsa.RSAPublicKey,
    private_key_ca_intermedia,  # Clave privada CA intermedia (Mantenida en AWS KMS)
    certificado_ca_intermedia_obj: x509.Certificate
) -> x509.Certificate:
    """
    Genera un Certificado Efímero X.509 v3 ajustado estrictamente a la
    Resolución MIC N.º 262/2024 (DOC-ICPP-20 Versión 2.0).
    Vigencia temporal forzada: T-5 minutos a T+1 hora.
    """
    
    # Configuración de Tiempos con Zona Horaria UTC para evitar desalineación
    ahora = datetime.datetime.now(datetime.timezone.utc)
    not_before = ahora - datetime.timedelta(minutes=5)
    not_after = ahora + datetime.timedelta(hours=1)
    
    # 1. Configuración del Subject conforme a Atributos Oficiales de Paraguay
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "PY"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, empresa_b2b),
        x509.NameAttribute(NameOID.COMMON_NAME, nombres_completos),
        # serialNumber en formato oficial PY-[Numero de Cedula]-[Digito Verificador]
        x509.NameAttribute(NameOID.SERIAL_NUMBER, f"PY-{cedula_paraguay}")
    ])
    
    # 2. Construcción del Certificado X.509
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(certificado_ca_intermedia_obj.subject)
        .public_key(public_key_usuario)
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
    )
    
    # 3. Inyección de Extensiones Obligatorias (Res. 262/24)
    # 3.1 Key Usage (Crítica): Firma Digital y No Repudio
    builder = builder.add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=True,  # nonRepudiation
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False
        ),
        critical=True
    )
    
    # 3.2 Extended Key Usage (No Crítica): Autenticación de Cliente y Protección de Email
    builder = builder.add_extension(
        x509.ExtendedKeyUsage([
            ExtendedKeyUsageOID.CLIENT_AUTH,
            ExtendedKeyUsageOID.EMAIL_PROTECTION
        ]),
        critical=False
    )
    
    # 3.3 Basic Constraints (Crítica): CA = FALSE
    builder = builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True
    )
    
    # 3.4 Authority Key Identifier (No Crítica)
    builder = builder.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(
            certificado_ca_intermedia_obj.public_key()
        ),
        critical=False
    )
    
    # 3.5 Subject Key Identifier (No Crítica)
    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(public_key_usuario),
        critical=False
    )
    
    # 3.6 Certificate Policies (No Crítica): OID de Firma Electrónica No Cualificada del PSCNC
    policy_oid = "1.3.6.1.4.1.99999.1.1.2" # Reemplazar con el PEN oficial registrado
    builder = builder.add_extension(
        x509.CertificatePolicies([
            x509.PolicyInformation(x509.ObjectIdentifier(policy_oid), [])
        ]),
        critical=False
    )
    
    # 4. Firma del Certificado con la Clave Privada de la CA Intermedia
    # Nota de Producción: En AWS, la firma se delega a AWS KMS llamando al API Sign
    certificado_firmado = builder.sign(
        private_key=private_key_ca_intermedia,
        algorithm=hashes.SHA256()
    )
    
    return certificado_firmado
```

---

## Indicaciones para Claude AI (System Prompt de Automatización)
> "Actúa como un Ingeniero Principal de Ciberseguridad y DevOps con especialización en PKI (Infraestructura de Clave Pública) y normativas de comercio electrónico para América Latina. Utiliza esta Declaración de Prácticas (DPSC) y perfiles del certificado (X.509 v3 conforme a la Resolución MIC N.º 262/2024 / DOC-ICPP-20 v2.0) para estructurar el backend del microservicio de firma desatendida en Python, asegurando que las plantillas de certificados efímeros cumplan con cada OID, restricción básica, uso de claves y vigencia temporal delimitada. El sistema debe integrarse de forma nativa con llamadas API asimétricas de AWS KMS (`kms:Sign`) para las operaciones de CA Subordinada, aislando de forma hermética las claves criptográficas."
