# Contrato de despliegue: qué pone el cliente y qué pone FNC

El ADR-0011 fija que **FNC entrega el motor y el cliente lo opera**. Este documento dice qué
significa eso en concreto, porque de ahí depende el encuadre legal y no solo el modelo
comercial.

> La Ley N.º 6822/2021 define el servicio de confianza como el prestado **habitualmente a
> cambio de una remuneración**, y enumera entre ellos **«la creación […] de firmas
> electrónicas»** (art. 4.º num. 48). Si la creación de la firma ocurre en infraestructura de
> FNC y a cambio de una tarifa, FNC presta un servicio de confianza aunque cada cliente firme
> sus propios contratos. **La línea la marca dónde se crea la firma, no cómo se llama el
> producto.**

---

## 1. Lo que aporta el cliente

| Recurso | Por qué es suyo y no nuestro |
| :---- | :---- |
| **Cuenta de nube** | Es donde ocurre la creación de la firma. Si fuera nuestra, seríamos nosotros quienes la creamos |
| **Claves de KMS** | La clave privada que firma define quién firma. Custodiarla nosotros nos convierte en el operador del acto |
| **Dominio de la CRL y del punto de verificación** | Lo que un tercero consulta para validar debe pertenecer a quien emitió, no a su proveedor de software |
| **Contrato con la autoridad de sellado de tiempo** | Solo si opera el nivel 2. Es un contrato entre el cliente y un prestador cualificado |
| **Certificado de su CA intermedia** | Ídem. Sin él, el nivel 2 no emite |
| **Operación**: despliegue, rotación de claves, respuesta a incidentes | Es la actividad. Delegarla en FNC traslada la prestación |

## 2. Lo que aporta FNC

* El motor: código, imágenes, módulos de Terraform y el SDK de integración.
* Mantenimiento, correcciones y perfiles de jurisdicción actualizados.
* Documentación y soporte **sobre el software**, no sobre la operación.

## 3. La frontera, en una regla operable

**FNC no debe poder firmar nada de un cliente.** Es la misma forma de la regla 8 del
`CLAUDE.md` —ningún rol humano tiene `kms:Sign`— aplicada un nivel más arriba: si el personal
de FNC pudiera invocar la firma en la cuenta del cliente, el encuadre se cae, con
independencia de lo que digan los contratos.

De ahí salen tres comprobaciones concretas antes de dar por bueno un despliegue:

1. **Ningún principal de FNC aparece en la política de las claves del cliente.** Ni para
   firmar, ni para administrar.
2. **El estado de Terraform vive en la cuenta del cliente**, no en la nuestra. El estado
   contiene identificadores y configuración de sus claves.
3. **Los nombres de los recursos no dicen «pscnc».** Un bucket llamado `pscnc-crl-prod` en la
   cuenta de un cliente lo etiqueta como prestador de servicios de confianza, que es
   exactamente lo que el encuadre niega. Por eso el prefijo es la variable
   `resource_prefix`, con `fenc` por defecto.

## 4. Lo que el motor ya no da por sentado

La configuración deriva la cuenta con `aws_caller_identity`, de modo que se despliega en la de
quien la ejecuta sin cambios. Lo que faltaba —y este documento cierra— era **decirlo, fijar el
prefijo como variable y dejar escritas las tres comprobaciones de arriba**, porque una
propiedad que nadie enunció es una propiedad que el próximo cambio rompe sin que nadie lo note.

## 5. El entorno se declara, y se comprueba

Fuera de producción, todo artefacto del motor va marcado. El certificado lleva
`[NO VALIDO - ENTORNO {ENV}]` en la unidad organizativa; el acta declara `environment` y
`not_valid_for_production`; el sello de una autoridad de pruebas figura como
`timestamp.qualified: false`. Un artefacto de pruebas que parece real es peor que uno que falta,
porque alguien lo termina presentando como válido.

Todas esas marcas salen de **una sola variable**: `PSCNC_ENVIRONMENT`, con los valores
`sandbox`, `dev`, `staging` o `prod`. Si no se declara, vale `dev`. El módulo de Terraform
`signer-service` la fija desde `var.environment`.

Dos comprobaciones antes de dar por bueno un despliegue:

1. **`PSCNC_ENVIRONMENT` coincide con el entorno real.** Un staging declarado `prod` emite
   artefactos sin marca, indistinguibles de los de producción.
2. **Firmar un documento de prueba en ese entorno y mirar el certificado.** Fuera de `prod`, la
   OU empieza con la marca; en `prod`, no la lleva.

### Estado en `main` al 2026-09-11: la comprobación 2 puede fallar fuera de producción

Hay caminos que todavía **no heredan el entorno**. Están corregidos en PR abiertos, y hasta que
se fusionen el flujo heredado no marca lo que produce:

| Qué falla hoy | Consecuencia | Lo corrige |
| :-- | :-- | :-- |
| `build_signing_service` construye la CA sin el entorno, y el constructor asume `"prod"` | Los certificados del flujo heredado (`/v1/signing-sessions/*`) salen sin marca | #48 (o su duplicado, #46) |
| `acta.py` y `transacciones.py` asumen `"prod"` si el llamador no pasa el entorno | Un llamador que lo olvide produce actas sin marca. El flujo v1 sí lo pasa | #52 |
| `build_signing_service` no le dice a la TSA si es de pruebas, y el valor por defecto es «cualificada» | La evidencia del flujo heredado declara cualificado un sello de prueba | Rama `fix/qualified-flujo-legado`, todavía sin PR |
| El bloque visible de constancia no lleva la marca | Todavía no se imprime desde ningún flujo (T-19); cuando se imprima, tiene que llevarla | #47 |

`docs/produccion/orden-de-fusion-2026-09-11.md` lleva el orden en que conviene fusionarlos.
Cuando estén todos fusionados, esta subsección se reduce a las dos comprobaciones de arriba.

## 6. Lo que este documento **no** resuelve

**Hasta dónde puede llegar el soporte sin que FNC pase a prestar el servicio.** Alojar la
infraestructura casi con seguridad cruza la línea; operar las claves en nombre del cliente
también. Entre eso y vender una licencia hay un espacio gris —¿un despliegue asistido?, ¿una
guardia de incidentes?— que no se resuelve leyendo la norma y que forma parte de la consulta
legal pendiente (L-05 en `docs/PENDIENTES.md`).

Hasta tener esa respuesta, la regla práctica es la del §3: **si FNC puede firmar, FNC presta.**
