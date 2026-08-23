# ADR-0003 · Pista de auditoría en DynamoDB single-table con espejo WORM en S3

* **Estado:** Aceptado
* **Fecha:** 2026-08-23
* **Decisores:** Arquitectura, Legal, SecOps

## Contexto

La pista de auditoría es el activo probatorio del negocio. Debe soportar tres patrones de
acceso — por transacción, por cédula del firmante y por cliente B2B — con latencia baja, y
simultáneamente ser **inmutable** frente a administradores de base de datos, desarrolladores
y atacantes, requisito derivado del Art. 63 de la Ley N.º 6822/2021 y de la retención
mínima de dos años exigida por el marco del MITIC.

## Decisión

1. **DynamoDB** con diseño de tabla única `PSCNC_Audit_Trail`, `PK = TX#{uuid}`,
   `SK = METADATA#V{n}`, GSI1 por cédula y GSI2 por cliente B2B; cifrado SSE-KMS con clave
   gestionada por el cliente y Point-in-Time Recovery activo.
2. **DynamoDB Streams → Lambda → S3 Object Lock (modo Compliance, 2 años)** como espejo
   inmutable. El objeto S3, no el ítem de DynamoDB, es la copia con valor probatorio.
3. Las correcciones no sobrescriben: se escribe una versión nueva `METADATA#V{n+1}` y el
   histórico permanece.

## Justificación

* DynamoDB no ofrece inmutabilidad real: un rol con `dynamodb:UpdateItem` puede alterar una
  evidencia. S3 Object Lock en modo Compliance no admite borrado ni acortamiento de
  retención ni siquiera por el usuario raíz de la cuenta, que es exactamente la propiedad
  que una pericia necesita.
* El modelo single-table evita joins y mantiene costo predecible bajo carga B2B irregular.
* La partición por `CLIENT#` en GSI2 sostiene el aislamiento multi-tenant (ADR-0005) y la
  facturación por consumo.

## Consecuencias

* Toda consulta forense oficial debe resolverse contra el objeto de S3 y contrastarse con
  el ítem de DynamoDB; una divergencia entre ambos es un incidente de seguridad de
  severidad máxima y dispara el runbook correspondiente.
* El costo de almacenamiento crece de forma monótona: no hay expiración antes de los dos
  años. Se aplica ciclo de vida a Glacier Instant Retrieval a los 90 días.
* Las pruebas de integración usan DynamoDB Local y MinIO; el modo Compliance no puede
  simularse fielmente y se valida en el entorno `dev` real.
