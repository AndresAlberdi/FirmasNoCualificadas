# ADR-0005 · Aislamiento multi-tenant lógico con partición por cliente B2B

* **Estado:** Aceptado
* **Fecha:** 2026-08-23
* **Decisores:** Arquitectura, SecOps

## Contexto

La plataforma sirve a múltiples clientes corporativos (aseguradoras, bancos, fintech) cuyos
datos incluyen biometría y cédulas de sus propios usuarios. Una fuga cruzada entre
inquilinos sería, además de un incidente de seguridad, un incumplimiento contractual y
regulatorio con obligación de notificación en 24 horas.

## Decisión

Aislamiento **lógico** con partición obligatoria por `b2b_client_id`, reforzado en cuatro
capas:

1. **Autenticación:** cada credencial HMAC/mTLS resuelve exactamente un `b2b_client_id`;
   el identificador nunca se toma del cuerpo de la petición.
2. **Acceso a datos:** el repositorio rechaza en tiempo de ejecución toda consulta cuya
   clave de partición no coincida con el tenant del contexto de seguridad
   (`TenantMismatchError`), y no expone ninguna operación de `Scan`.
3. **Almacenamiento:** los objetos se ubican bajo el prefijo `s3://{bucket}/{tenant}/{tx}/`
   y las políticas IAM del servicio restringen el prefijo mediante condiciones.
4. **Observabilidad:** todo log estructurado incluye `b2b_client_id`; las métricas y
   alarmas se dimensionan por tenant.

Los clientes que contractualmente exijan aislamiento físico se despliegan en una cuenta AWS
dedicada reutilizando los mismos módulos de Terraform (modelo *silo* opcional).

## Justificación

El aislamiento físico universal multiplicaría el costo operativo y el tiempo de despliegue
sin beneficio proporcional en el segmento inicial. El aislamiento lógico con verificación
en el repositorio —no solo en la capa HTTP— evita que un error de enrutamiento en la API se
traduzca en una fuga de datos.

## Consecuencias

* Existe una prueba obligatoria en la batería de CI que verifica que toda consulta sin
  contexto de tenant falla, y otra que intenta acceso cruzado y espera `TenantMismatchError`.
* La partición se refleja en GSI2 (`CLIENT#{tenant}`), lo que habilita reportes y
  facturación por consumo sin consultas de tabla completa.
* Se prohíbe cualquier endpoint administrativo que agregue datos de varios inquilinos sin
  un rol interno explícito y registro en el log de auditoría de acceso.
