# Documentos de diseño — qué es cada uno y qué decisión respalda

Estos once documentos son la **fuente de verdad de negocio y de arquitectura** de
FirmasNoCualificadas (FNC). No son documentación generada por el proyecto: son el material
de partida a partir del cual se tomaron las decisiones registradas en `docs/adr/`.

Regla de uso: **ningún ADR ni módulo de código cita una norma de memoria.** Si una regla de
negocio necesita respaldo normativo, la cita sale de uno de estos documentos y, en el
código, del perfil de jurisdicción correspondiente (`jurisdictions/<país>/`), nunca de un
literal disperso.

Advertencia general sobre el material: varios de estos documentos fueron redactados como
*prompts* dirigidos a un asistente de IA y terminan con secciones del tipo «PROMPT PARA
CLAUDE AI» o «¿qué te gustaría hacer a continuación?». Esas secciones **no son
especificación**: son residuos de la conversación que los produjo. Lo que vale es el cuerpo
técnico y normativo de cada documento.

---

## 1. Arquitectura y producto

### `blueprint-firma-no-cualificada-paraguay-v2.md`
Especificación técnica maestra del sistema: marco legal paraguayo (Ley N.º 6822/2021,
Decreto N.º 7576/2022, Res. MIC N.º 262/2024), arquitectura AWS, ciclo de firma PAdES
incremental, sellado RFC 3161, pista de auditoría y ruta de formalización ante el MIC.

**Respalda:** ADR-0001 (motor pyHanko), ADR-0004 (certificados efímeros), el nivel 2 de
servicio, los tres endpoints de la API pública y el plazo de notificación de incidentes de
24 h al perfil de jurisdicción `PY`.

**Contradicción conocida con el ADR-0004, ya resuelta:** el §4.1 del blueprint fija la
vigencia del certificado efímero en `T−5 min` a `T+1 h`; el ADR-0004 la reduce a 15 minutos.
**Manda el ADR** — la ventana más corta reduce la superficie de riesgo sin costo probatorio,
porque la fecha cierta la aporta el sello de tiempo, no la vigencia del certificado.

### `aws-kms-key-architecture-pscnc.md`
Diseño del subsistema criptográfico: clave de la CA intermedia en KMS, política de clave con
separación de funciones, rol de ejecución de Fargate, ciclo de vida de los certificados
cortos, publicación de CRL y procedimiento break-glass.

**Respalda:** ADR-0004, ADR-0006 (jerarquía de claves y sellado de actas) y
`docs/RUNBOOK-break-glass.md`.

**Diferencias deliberadas respecto de lo que se implementa:** el documento describe una
única clave (la de la CA). El diseño de FNC agrega dos familias de claves **por tenant** —
sello de acta y cifrado de evidencias — que el documento no contempla, porque fue escrito
para un despliegue mono-cliente. Además, su §6 pide «habilitando la rotación de claves»
sobre una clave asimétrica: **AWS KMS no admite rotación automática de claves asimétricas**;
la rotación es un procedimiento manual con alias versionados (ADR-0006).

### `esquema-base-datos-auditoria-pscnc.md`
Modelo de datos de la pista de auditoría en DynamoDB: diseño de tabla única, claves, GSIs,
esquema JSON completo del expediente y modelo Pydantic de validación. Incluye la
fundamentación probatoria frente al Código Procesal Civil paraguayo.

**Respalda:** ADR-0003 (single-table + espejo WORM) y los modelos de
`services/src/pscnc/models/audit_trail.py`.

**Literales paraguayos que el módulo `jurisdictions/` tiene que absorber:** el patrón
`CI#PY-[0-9]+` de `GSI1PK`, el `document_type` acotado a `CI_PY`/`PASAPORTE` y la retención
de 2 años.

### `arquitectura-integracion-api-aseguradoras.md`
Flujo de integración B2B extremo a extremo entre el intermediario (Interseguros), el core de
la aseguradora y el prestador cualificado que estampa la firma cualificada de la póliza.
Define el traspaso del expediente de evidencias y el webhook de póliza emitida.

**Respalda:** el contrato de la API pública (§4 del encargo) y, en particular, la decisión de
que **el registro de evidencia del tenant es el autoritativo del contrato** y el de FNC es el
acta del acto de firma: acá se ve por qué, porque el expediente viaja al core de la
aseguradora y es ahí donde vive la relación contractual.

### `esquema-dashboard-b2b-pscnc.md`
Especificación funcional del panel B2B: vista general con KPIs, explorador de transacciones,
visualizador forense por pestañas, descargas con URL pre-firmadas de 5 minutos,
enmascaramiento de PII, RBAC con cuatro roles y MFA obligatorio.

**Respalda:** la fase 8 del plan de trabajo y el TTL de 300 s de `presigned_url_ttl` en la
configuración del servicio.

### `blueprint-wireframe-react.md`
Wireframe del «Folleto Forense» (el visualizador de evidencias del dashboard), con la
distribución espacial de las cuatro pestañas y las directivas de enmascaramiento de PII.
Complementa al anterior en la capa visual.

**Respalda:** `dashboard/src/components/ForensicViewer.tsx`.

### `mockup-ui-folleto-forense.jpg`
Mockup visual del folleto forense. Referencia de estilo, no especificación funcional.

---

## 2. Cumplimiento regulatorio

### `declaracion-practicas-perfiles-pscnc.md`
Borrador de la Declaración de Prácticas de los Servicios de Confianza (DPSC) exigida por la
Res. MIC N.º 262/2024, más la especificación campo por campo del perfil de certificado X.509
v3 conforme a `DOC-ICPP-20 v2.0`.

**Respalda:** el perfil de certificado del ADR-0004 y el módulo
`services/src/pscnc/crypto/ephemeral_ca.py`. Es, además, **el documento que hay que
presentar al MIC**: sus campos entre corchetes (`[Razón Social]`, `[Número PEN]`) son
pendientes reales, registrados en `docs/PENDIENTES.md`.

**Tensión con el ADR-0004:** la DPSC declara RSA-4096 con `sha256WithRSAEncryption`. El
ADR-0006 elige `ECC_NIST_P384` para la CA intermedia. Si la DPSC se presenta con RSA-4096 y
la clave real es ECDSA, la declaración es falsa: **el algoritmo elegido debe reflejarse en la
DPSC antes de presentarla.**

### `guia-registro-prestadores-confianza-paraguay.md`
Ruta administrativa para constituirse como PSCNC: inscripción en el REPSE por la VUE,
notificación de inicio de actividades a la DGFDCE dentro de 3 meses, documentación técnica
exigida y obligaciones permanentes post-registro.

**Respalda:** `docs/CUMPLIMIENTO-MIC.md` y los plazos del perfil de jurisdicción `PY`
(notificación de incidentes en 24 h, plazo de comunicación de inicio de 3 meses).

### `regimen-responsabilidad-seguros-servicios-confianza-paraguay.md`
Aclara que la póliza de responsabilidad civil de 500 salarios mínimos **es exigible solo a
los prestadores cualificados (PCSC)**, no a los no cualificados, y describe el régimen de
responsabilidad patrimonial directa que sí aplica a FNC.

**Respalda:** la decisión de no incluir la contratación de una póliza como bloqueante del
lanzamiento. Recomienda contratarla igual, de forma voluntaria, por el tratamiento de
biometría de terceros — anotado en `docs/PENDIENTES.md` como decisión de negocio pendiente.

### `marco-regulatorio-firma-electronica-seguros-paraguay.pdf`
Análisis externo del marco de firma electrónica aplicado al ramo seguros. Cubre la
Res. SS.SG. N.º 210/2025 (comercialización por medios electrónicos), la
Res. SS.SG. N.º 231/2025 (pólizas electrónicas) y la coexistencia obligatoria entre la firma
simple del proponente y la firma cualificada de la aseguradora.

**Respalda:** el caso de uso del primer tenant (SeguroLoTengo) y el nivel 1 de servicio.

**Se contradice a sí mismo, y hay que saberlo antes de citarlo:** el cuerpo principal
sostiene que operar un mecanismo de firma propio «adquiere la condición de PSCNC» y obliga a
registrarse; su complemento sostiene lo contrario para un mecanismo interno, gratuito y no
ofrecido a terceros. El criterio que resuelve la contradicción está en
`~/segurolotengo-demo/docs/VALIDACION_LEGAL_FIRMA_INTERNA.md` §4 y es la definición legal de
servicio de confianza: **el que se presta habitualmente a cambio de una remuneración**. De
ahí sale la asimetría que gobierna este proyecto:

| | SeguroLoTengo | FirmasNoCualificadas |
| :---- | :---- | :---- |
| Qué hace | Firma sus propias contrataciones | Presta el servicio a terceros |
| Figura | Mecanismo interno | **PSCNC, sin discusión** |
| Registro ante el MIC | No corresponde | **Obligatorio** |

---

## 3. Documento externo de referencia (no vive en este repositorio)

`~/segurolotengo-demo/docs/VALIDACION_LEGAL_FIRMA_INTERNA.md` — validación legal del primer
tenant. Su **§5 contiene la tabla de diferencias entre FNC y SeguroLoTengo**, que es el
backlog de compatibilidad de la API pública (umbral biométrico, escala 0-1 frente a 0-100,
hash-only frente a PDF completo, quién emite el OTP, qué registro de evidencia es
autoritativo, `legal_guard`, TSA), y su **§6 el plan de convergencia en dos fases**. Ese
documento es de otro repositorio y **no se modifica desde este proyecto**; se cita.
