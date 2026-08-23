# ADR-0004 · Certificados de firmante efímeros emitidos por una CA intermedia en AWS KMS

* **Estado:** Aceptado
* **Fecha:** 2026-08-23
* **Decisores:** Arquitectura, SecOps, Legal

## Contexto

Cada firma requiere un certificado X.509 que vincule la clave de firma con la persona
verificada en el onboarding. Existen dos modelos: certificados de larga vigencia por
usuario (requiere gestión de ciclo de vida, revocación en caliente y custodia de claves de
usuario) o certificados efímeros de un solo uso emitidos en el instante de la firma.

## Decisión

Se emiten **certificados X.509 v3 de un solo uso**, con vigencia de 15 minutos y retroceso
de 5 minutos respecto de la hora de emisión, firmados por la CA intermedia cuya clave
privada reside exclusivamente en AWS KMS (RSA-4096, `SIGN_VERIFY`, HSM FIPS 140-2 Nivel 3).
El par de claves del firmante se genera en memoria del contenedor y se destruye tras
producir el bloque CMS.

Perfil del certificado, alineado con la Resolución MIC N.º 262/2024 (`DOC-ICPP-20 v2.0`):

| Campo | Valor |
| :-- | :-- |
| `subject.CN` | Nombre y apellido del firmante según cédula |
| `subject.serialNumber` | `PY-{número de cédula}` |
| `subject.C` | `PY` |
| `subject.OU` | `Firma Electronica No Cualificada - TX {transaction_id}` |
| `keyUsage` (crítica) | `digitalSignature`, `nonRepudiation` |
| `extendedKeyUsage` | `emailProtection`, `documentSigning` (1.3.6.1.4.1.311.10.3.12) |
| `basicConstraints` (crítica) | `CA:FALSE` |
| `certificatePolicies` | OID de la política del PSCNC declarada en la DPSC |
| `crlDistributionPoints` | URL pública de la CRL de la CA intermedia |
| `authorityKeyIdentifier` | SKI de la CA intermedia |

## Justificación

1. **Reducción de la superficie de riesgo:** una clave que existe durante segundos no puede
   ser robada del reposo, y una ventana de validez de 15 minutos hace inviable el uso
   posterior de un certificado sustraído.
2. **Simplificación de la revocación:** no hay ciclo de vida de usuario que administrar. La
   CRL solo tiene que cubrir la CA intermedia, que sí se publica y refresca diariamente.
3. **Coherencia con el modelo probatorio:** el valor de la FENC no reside en el certificado
   sino en la pista de auditoría; un certificado de larga vigencia aportaría gestión sin
   aportar fuerza probatoria adicional.

## Consecuencias

* Un validador estricto que exija comprobación de revocación en el momento de la
  validación encontrará el certificado expirado. Por eso el **sellado de tiempo RFC 3161
  es obligatorio** (PAdES-B-T): acredita que la firma se produjo dentro de la ventana de
  validez. Sin TSA, la firma es inverificable a futuro.
* El nivel PAdES-B-LTA es la evolución natural y queda registrada como deuda técnica.
* La construcción del TBSCertificate se realiza con `asn1crypto` porque la firma es
  externa; `cryptography` exige un objeto de clave privada local y no es aplicable.
