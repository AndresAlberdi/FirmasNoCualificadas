# ADR-0008 · La jurisdicción es configuración, no código

* **Estado:** Aceptado
* **Fecha:** 2026-09-02
* **Decisores:** Arquitectura, Producto, Legal

## Contexto

El scaffolding nació paraguayo y lo lleva escrito en todas partes: el patrón `CI#PY-` en la
clave del índice de auditoría, `C=PY` en el certificado, la lista de actos jurídicos
excluidos del `legal_guard`, la retención de dos años, el correo de la DGFDCE, el plazo de
24 horas para notificar incidentes, el nombre de las TSA paraguayas.

Cada uno de esos literales es correcto hoy y **falso en cuanto la plataforma cruce la
frontera**. Peor: son falsos de forma silenciosa. Un `serialNumber=PY-{cédula}` emitido para
un firmante boliviano produce un certificado que valida criptográficamente y miente sobre la
identidad del titular.

El producto se diseñó desde el primer día para salir de Paraguay. Si la jurisdicción vive
dispersa en el código, salir implica una refactorización con riesgo regulatorio; si vive en
un perfil, implica agregar un archivo de datos.

## Decisión

### 1. Un módulo `jurisdictions/` con un perfil por país

Todo lo que dependa del país vive en `jurisdictions/<código ISO>/` y en ningún otro lugar:

| Qué | Ejemplo en `PY` |
| :---- | :---- |
| Norma citada en la constancia | `Res. SS.SG. 210/2025, arts. 4 y 9` |
| Formato y validación del documento de identidad | Cédula paraguaya |
| Campo del `SerialNumber` del certificado | `PY-{cédula}` |
| Plazo mínimo de conservación de evidencia | 2 años desde el vencimiento del contrato |
| Actos jurídicos excluidos | Hipoteca, donación, testamento, matrimonio… |
| Catálogo de TSA aceptadas | PCSC habilitados por el MIC |
| Autoridad regulatoria y plazo de notificación | DGFDCE del MIC y CERT-Py, 24 h |
| Textos de producto | `jurisdictions/py/textos.py` |

### 2. La regla que lo hace verificable

**Ningún módulo fuera de `jurisdictions/` puede contener un literal de norma, de país o de
organismo.** Un test de la batería recorre el árbol de código y falla si encuentra `PY`,
`Paraguay`, `MIC`, `DGFDCE`, `CERT-Py`, `210/2025`, `6822/2021`, `262/2024` o
`DOC-ICPP-20` fuera del módulo de jurisdicciones y de la documentación.

Sin ese test la regla es una intención. Con él, la violación rompe la compilación de la
suite, que es la única forma de que una convención sobreviva a la tercera persona que toca el
código.

### 3. `legal_guard` lee del perfil

La lista de exclusiones deja de ser una constante del módulo de cumplimiento y pasa a ser un
dato del perfil de jurisdicción. El motor de detección léxica —normalización, análisis,
veredicto— es común; **qué** se bloquea es jurisdiccional. Un testamento está excluido en
Paraguay por su forma solemne, y esa razón no se exporta sola a otro ordenamiento.

### 4. Bolivia (`BO`) como segunda jurisdicción

Se modela un segundo perfil para demostrar que la generalización funciona y que ningún
literal paraguayo quedó fuera del módulo.

**Advertencia que acompaña al perfil y no puede borrarse:** el perfil `BO` es **estructural,
no validado legalmente**. No hay en este repositorio ningún documento normativo boliviano, y
el equipo no va a inventar citas de normas que no leyó. El perfil declara los mismos campos
que `PY` con valores marcados `sin_validacion_legal=True`, y el código **rechaza operar en
producción con una jurisdicción marcada así**. Sirve para lo que se lo creó: probar que la
arquitectura generaliza. Habilitarlo comercialmente exige que entren los documentos fuente
bolivianos y una revisión legal local, registradas en `docs/PENDIENTES.md`.

Se dejó constancia de una limitación conocida de esta elección: Bolivia se parece a Paraguay
—cédula numérica, español, familia normativa común—, de modo que un literal paraguayo
escondido podría pasar sus tests igual. El test de literales del punto 2 es lo que cubre ese
hueco, y por eso es obligatorio y no opcional.

## Justificación

1. **El costo de separar es hoy bajo y mañana alto.** El scaffolding tiene cinco módulos con
   literales paraguayos; una plataforma con tres países tendrá decenas.
2. **El riesgo no es técnico sino regulatorio.** Un literal olvidado no rompe un test: emite
   un certificado que afirma algo falso sobre una persona.
3. **La configuración es auditable.** Un regulador puede leer el perfil de su país y verificar
   qué norma se cita, sin leer el código.

## Consecuencias

* La jurisdicción viaja en el contrato del tenant y se asienta en el acta sellada
  (`jurisdiction`): dos tenants en jurisdicciones distintas conviven en el mismo despliegue.
* `object_lock_retention_days` sale del perfil y el `plan` de Terraform **falla** si el valor
  configurado es menor al mínimo de la jurisdicción activa. En modo COMPLIANCE la retención
  es irreversible: un valor corto no se corrige después.
* La constancia entregada al firmante cita la norma del perfil, no una constante.
  Es lo que permite que el equivalente de la constancia de SeguroLoTengo funcione con el
  emisor y la norma parametrizados.
* Las TSA se seleccionan del catálogo del perfil: una TSA paraguaya sellando un acto
  boliviano es válida criptográficamente y discutible jurídicamente.
* Deuda registrada: la validación del documento de identidad de `PY` incluye el dígito
  verificador de la cédula, que hoy no se comprueba.
