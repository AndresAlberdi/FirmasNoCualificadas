# ADR-0010 · El nombre del firmante viaja en dos campos, no en uno

* **Estado:** Aceptado
* **Fecha:** 2026-09-03
* **Decisores:** Arquitectura, Producto, Legal
* **Reemplaza parcialmente:** ADR-0009 §4 (contrato de confirmación)

## Contexto

El perfil de certificado de la jurisdicción paraguaya —`DOC-ICPP-20 v2.0`, aprobado por la
Res. MIC N.º 262/2024 y archivado en `docs/diseno/normativa/`— exige en su §4.1 **tres**
atributos de nombre en el sujeto del certificado de firma electrónica, los tres marcados
obligatorios:

| Campo | Contenido exigido |
| :---- | :---- |
| 6.5 `Surname` | Apellido del titular, según documento de identificación |
| 6.6 `Given Name` | Nombre del titular, según documento de identidad |
| 6.7 `Common Name` | Nombre y apellido según documento |

El contrato público v1 recibe una sola cadena, `signer_common_name`. Con eso no se puede
emitir un certificado conforme.

**La salida obvia es la que hay que descartar.** Partir la cadena por el primer espacio, o
por el último, o por la mitad, funciona con «Juan Pérez» y falla con todo lo demás: apellidos
compuestos («Ruiz Díaz», universal en Paraguay), nombres de pila dobles («José María»),
partículas («De la Cruz»), y las combinaciones de ambos. No hay heurística que resuelva
«María José Ruiz Díaz» sin conocer el documento.

Lo que hace inaceptable la heurística no es su tasa de error, es **dónde deposita el error**.
Un certificado con el apellido mal partido no falla ruidosamente: se emite, valida
criptográficamente, y afirma sobre una persona un apellido que ella nunca declaró. Es
exactamente la clase de afirmación falsa que el ADR-0008 justifica evitar cuando dice que un
literal equivocado «no rompe una prueba, emite un certificado que afirma algo falso sobre una
persona».

**El modelo de evidencia ya lo tenía bien.** `IdentityEvidence` guarda `first_name` y
`last_name` por separado desde el primer día, porque es lo que devuelve la verificación
documental del proveedor de identidad. El dato existe del lado del tenant: el contrato
público simplemente no lo pedía.

## Decisión

### 1. El contrato pide el nombre y el apellido por separado

`ConfirmTransactionRequest` incorpora `signer_given_name` y `signer_surname`. Ambos son
opcionales en el esquema —para no romper la validación de ninguna petición existente— y
**exigidos para emitir un certificado de nivel 2**.

### 2. El `commonName` se deriva, no se pide

El perfil define el `Common Name` como «nombre y apellido», que es exactamente la
concatenación de los otros dos. Pedirlo por separado abriría la puerta a que los tres campos
se contradigan entre sí, y un certificado que se contradice internamente es peor que uno
incompleto.

`signer_common_name` se conserva en el contrato y pasa a ser un **anulador explícito**: si
viene, gobierna el `CN`; si no viene, el `CN` se compone. Sirve para el caso en que el
documento de identidad muestre el nombre completo en un orden distinto del que produce la
concatenación.

### 3. Sin los dos campos, el nivel 2 se rechaza con un motivo propio

Se agrega `INCOMPLETE_SIGNER_NAME` al catálogo de motivos. **Agregar un motivo es compatible**
con los tenants existentes (ADR-0009); lo que rompería su `match` sería renombrar uno.

No se degrada a un `CN` suelto ni se adivina la partición. Un rechazo explícito es recuperable
—el tenant reenvía con los dos campos— mientras que un certificado con el apellido inventado
no se detecta hasta que alguien lo impugna.

### 4. `signer_common_name` a solas deja de bastar para el nivel 2

Es un cambio incompatible para un integrante de nivel 2, y se acepta a sabiendas por dos
razones:

1. **No hay ninguno.** El nivel 2 no puede ofrecerse en producción hasta que se cumplan los
   tres bloqueantes del ADR-0007, que siguen abiertos (`docs/PENDIENTES.md` §1). El costo de
   compatibilidad hoy es cero, y crece con cada tenant que se integre.
2. **La alternativa compatible es peor.** Mantener el campo suelto obligaría a adivinar la
   partición, que es justamente lo que esta decisión existe para impedir.

El **nivel 1 no se toca**: no emite certificados, así que no necesita ninguno de los tres
campos.

## Consecuencias

* `api/openapi.yaml` y el SDK de TypeScript incorporan los dos campos; la suite de contrato
  del SDK verifica el rechazo por nombre incompleto.
* Un tenant que hoy integre el nivel 2 tiene que enviar tres datos de identidad —tipo de
  documento, nombre y apellido— en lugar de dos cadenas. Todos salen de la misma verificación
  documental que ya realizó.
* El certificado emitido pasa a llevar `givenName` y `surname` además del `commonName`, que es
  lo que el perfil exige.
* Queda **sin resolver** qué hacer con un firmante sin apellido, o con una identidad que no se
  descompone en «nombre» y «apellido». El perfil paraguayo asume que sí, porque asume cédula o
  pasaporte. Si aparece una jurisdicción donde no valga, la descomposición tendrá que pasar a
  ser parte del perfil y no del contrato.

## Alternativas descartadas

**Partir la cadena en el servidor.** Descartada arriba: deposita el error dentro de un
documento probatorio, en silencio.

**Pedir la partición al tenant solo cuando el perfil la exija.** Haría que el contrato dependa
de la jurisdicción de la transacción, y un integrador tendría que implementar dos formas de
llamar al mismo endpoint según el país. El ADR-0008 mantiene la jurisdicción fuera del
contrato a propósito.

**Derivar los tres campos del acta de evidencia** en lugar de pedirlos. El acta la construye
FNC con lo que el tenant envía; no hay una fuente independiente de la que derivarlos.
