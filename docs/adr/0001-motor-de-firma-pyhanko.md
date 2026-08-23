# ADR-0001 · Motor de firma PAdES sobre Python 3.12 + pyHanko

* **Estado:** Aceptado
* **Fecha:** 2026-08-23
* **Decisores:** Arquitectura, SecOps

## Contexto

El núcleo del sistema debe producir firmas PAdES incrementales sobre PDFs que pueden
contener firmas previas de terceros (incluidas firmas cualificadas), sin invalidarlas, y
debe delegar la operación criptográfica en AWS KMS, donde reside la clave de la CA
intermedia. Se evaluaron cuatro alternativas: pyHanko (Python), EU DSS (Java),
`@signpdf`/`pdf-lib` (Node) y `digitorus/pdfsign` (Go).

## Decisión

Se adopta **Python 3.12 con pyHanko** para el motor de firma y **FastAPI** para la API,
integrando AWS KMS mediante una subclase de `pyhanko.sign.signers.Signer` que implementa
`async_sign_raw` delegando en `kms:Sign` con `MessageType=DIGEST`.

## Justificación

1. pyHanko implementa de forma nativa la actualización incremental del PDF, el cálculo del
   `/ByteRange`, la construcción del `SignedData` CMS, el sellado RFC 3161 y el
   diccionario `/DSS` necesario para el nivel LTA futuro.
2. Su punto de extensión para firmantes externos (HSM/KMS) es de primera clase, lo que
   evita construir ASN.1 a mano para el bloque de firma.
3. El ecosistema Python permite compartir un único lenguaje con la capa de evidencias,
   la validación Pydantic y las funciones Lambda de CRL, reduciendo la superficie de
   mantenimiento del equipo.
4. EU DSS es funcionalmente superior en validación LTA, pero impone una JVM, un modelo de
   despliegue más pesado y una curva de mantenimiento que no se justifica para el volumen
   inicial. Node y Go carecen de soporte maduro para PAdES-B-LTA y DSS.

## Consecuencias

* **Positivas:** menor tiempo hasta la primera firma válida; verificación cruzada sencilla
  con la CLI `pyhanko sign validate`; un único runtime para backend y jobs.
* **Negativas:** la validación de la cadena para LTA deberá construirse con
  `pyhanko-certvalidator`, que exige configurar explícitamente los `ValidationContext`.
* **Mitigación:** la interfaz `pscnc.crypto.pades.PadesSigner` aísla la librería; una
  migración futura a EU DSS afectaría a un solo módulo.
* **Riesgo residual:** dependencia de un proyecto con un número reducido de mantenedores.
  Se fija la versión, se replica el paquete en un repositorio interno de artefactos y se
  monitorean sus avisos de seguridad.
