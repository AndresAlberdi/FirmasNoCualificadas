# Textos normativos oficiales

Fuentes de **primera mano**. Todo lo que está en este directorio se leyó del documento
oficial, no de un análisis que lo resume.

La distinción importa porque gobierna qué se puede afirmar. Un análisis de terceros dice qué
*entiende* su autor que exige una norma; el texto oficial dice qué exige. Cuando los dos
discrepan, manda el texto — y cuando el texto no está, la afirmación va a la tabla §2 de
`docs/PENDIENTES.md` como verificación pendiente, no al código.

| Archivo | Norma | Qué contiene y qué **no** |
| :---- | :---- | :---- |
| `res-mic-262-2024.pdf` | Resolución MIC N.º 262, del 4 de abril de 2024 | El acto que aprueba el perfil. **No contiene el Anexo** `DOC-ICPP-20 v2.0`, que es donde viven los campos y algoritmos del certificado |

## Qué queda acreditado con la Res. 262/2024

Leído del documento, no inferido:

* Su título exacto: *«Por la cual se aprueba el perfil del certificado del prestador no
  cualificado de servicios de confianza DOC-ICPP-20 versión 2.0»*.
* Fecha: Asunción, 4 de abril de 2024. Firma el ministro Francisco Javier Giménez.
* **Artículo 1.º** modifica parcialmente el artículo 3.º de la **Resolución N.º 1384/2022**,
  cuyo Anexo II establecía el perfil anterior.
* **Artículo 2.º** aprueba el perfil «que forma parte como Anexo de la presente Resolución» y
  deja sin efecto la versión 1.0.
* **Artículo 3.º**: vigencia desde la promulgación.
* En los considerandos, el Ministerio afirma que la Ley N.º 6822/2021 instituye al MIC como
  Autoridad de Aplicación en su artículo 96, a través de la Dirección General de Comercio
  Electrónico, y que los servicios de confianza no cualificados **no necesitan autorización
  administrativa para iniciar su actividad, pero deben comunicarlo a la Autoridad de
  Aplicación dentro de los tres meses** desde que la inicien.

## La pregunta que el texto abre y no cierra

El título y el artículo 1.º hablan del perfil **del certificado del prestador**. El
repositorio venía asumiendo que `DOC-ICPP-20 v2.0` gobierna además el certificado efímero
que el prestador **emite al firmante**, y sobre ese supuesto se apoya la elección de
algoritmo del ADR-0006.

Son dos cosas distintas y el acto administrativo, por sí solo, no permite decidir cuál rige:
lo dirime el Anexo. Hasta tenerlo, el supuesto sigue siendo un supuesto — anotado en la
tabla §2 de `docs/PENDIENTES.md` (N-01) junto con la Res. 1384/2022 y su Anexo II.
