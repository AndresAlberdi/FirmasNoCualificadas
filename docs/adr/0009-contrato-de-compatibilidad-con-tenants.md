# ADR-0009 · Contrato de compatibilidad con el tenant: identidad, OTP y documento

* **Estado:** Aceptado
* **Fecha:** 2026-09-02
* **Decisores:** Arquitectura, Producto, Legal

## Contexto

El scaffolding fue diseñado suponiendo que FNC controla el acto completo: consulta el
onboarding, aplica su propio umbral biométrico (`> 95%`), emite y verifica el OTP de
consentimiento y recibe el PDF entero.

El primer tenant real invalida las cuatro suposiciones. SeguroLoTengo ya verifica la
identidad con su propia política —umbral **99 sobre 100**, en escala 0-100 de Rekognition, con
la decisión registrada junto al umbral aplicado, la versión del modelo y la versión de la
política—, ya emite su OTP de firma con propósito propio, ya cierra y hashea el documento
antes de habilitar la firma, y su documento contiene declaraciones de salud.

Si FNC vuelve a decidir cualquiera de esas cosas, no agrega garantías: **las contradice**.
Un servicio que aprueba con 95% lo que la política del tenant rechaza con 99 no es más
seguro, es una segunda opinión más laxa que anula la primera.

Esta es la tabla de diferencias del §5 de `VALIDACION_LEGAL_FIRMA_INTERNA.md` convertida en
decisión de arquitectura.

## Decisión

### 1. FNC no vuelve a decidir la identidad

Recibe la decisión ya tomada por el tenant y la asienta como evidencia:

```
identity_decision: {
  approved, threshold_applied, model_version, policy_version, provider_reference
}
```

El umbral `min_facial_match_score` **deja de ser un control** y se conserva como campo
informativo del perfil del tenant. La API no rechaza una transacción por el puntaje: rechaza
una transacción cuyo `identity_decision.approved` sea falso, que es una cosa distinta.

Las puntuaciones **se normalizan a escala 0-1 en el borde**, registrando la escala de origen.
Un `98` sin escala declarada es indistinguible de un `0.98` mal convertido, y esa ambigüedad
en un dato pericial es inaceptable.

### 2. El OTP de firma puede ser del tenant o de FNC

* **`otp_mode: TENANT_VERIFIED`** — el tenant lo emitió y lo verificó. Envía
  `otp_reference`, canal, destino enmascarado y marcas de tiempo **como evidencia, nunca
  como control**, y jamás el código. Es el modo de SeguroLoTengo.
* **`otp_mode: FNC_MANAGED`** — FNC lo emite por el canal que el tenant indique.

En ninguno de los dos modos se persiste ni se registra un código en claro. Es la regla
inviolable heredada: **solo el hash del OTP se persiste**.

El motivo de fondo por el que el OTP del tenant es evidencia y no control: el OTP prueba la
voluntad de firmar *ante el tenant*, que es con quien la persona contrata. Reverificarlo en
FNC no agrega prueba; agrega un segundo código que la persona no pidió y un punto de fallo.

### 3. Hash-only por defecto

El tenant envía `document: {sha256, version, code, closed_at}` y, opcionalmente, el PDF.

Con declaraciones de salud dentro del documento, hash-only es **la única forma de no
convertir a FNC en encargado del tratamiento de datos de salud sin contrato**. El nivel 2
necesita el PDF (ADR-0007): en ese caso se procesa en memoria, se firma, se devuelve y no se
conserva salvo custodia contratada.

La `version` viaja junto al hash porque una huella suelta no dice contra qué comparar.

### 4. Dos registros de evidencia, uno autoritativo

El registro del tenant es **el autoritativo del contrato**; el de FNC es **el acta del acto
de firma**. Se referencian mutuamente por `transaction_id` ↔ `tenant_reference`, y el acta
sellada incluye ambos identificadores.

No es una jerarquía arbitraria: el expediente del tenant es el que viaja al core de la
aseguradora y el que sostiene la relación contractual. El acta de FNC prueba el acto de
firma, que es una parte de ese expediente, no su reemplazo.

### 5. Motivos enumerados y estables

Todo error devuelve un `motivo` de un enumerado cerrado y estable, **nunca un mensaje
libre**, siguiendo el patrón de `MotivoRechazoFirmaCliente`. El tenant tiene que poder mapear
cada rechazo a su propia máquina de estados; un texto que cambia de redacción entre versiones
rompe integraciones sin cambiar una sola firma de función.

### 6. Idempotencia obligatoria

`Idempotency-Key` es obligatoria en las dos escrituras. **Una confirmación repetida devuelve
el acta original, no una nueva.** Emitir dos actas para un mismo acto de firma produce dos
piezas de evidencia divergentes sobre el mismo hecho, que es exactamente lo que una pericia
usaría para impugnar las dos.

## Justificación

1. **Evita la contradicción entre políticas.** Dos controles de identidad sobre el mismo acto
   no se suman: el más laxo gana.
2. **Minimiza el dato tratado.** Lo que no se recibe no se filtra.
3. **Permite integrar sin cambiar el recorrido del cliente**, que es la condición explícita
   del plan de convergencia del primer tenant.

## Consecuencias

* El adaptador del tenant se implementa detrás de su puerto de firma sin tocar el flujo. La
  suite de contrato de `sdk/typescript/` define qué tiene que cumplir.
* FNC **no puede afirmar que verificó la identidad**. Su acta dice que el tenant la verificó,
  con qué umbral y qué versión de política. La constancia debe redactarse en esos términos:
  atribuir a FNC una verificación que no hizo sería falso en un documento probatorio.
* El campo `min_facial_match_score` de la configuración queda como informativo. Se documenta
  para que nadie lo reinterprete como control.
* Riesgo asumido y su mitigación: si el tenant miente en `identity_decision`, FNC sella una
  evidencia falsa. Mitigación: el acta registra **quién** afirmó qué (`provider_reference`,
  `policy_version`), de modo que la responsabilidad quede trazada donde corresponde. FNC
  responde por la integridad del acta, no por la veracidad de lo que el tenant declaró.
