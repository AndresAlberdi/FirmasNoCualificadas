# ADR-0007 · Dos niveles de servicio seleccionables por tenant y por transacción

* **Estado:** Aceptado
* **Fecha:** 2026-09-02
* **Decisores:** Producto, Arquitectura, Legal

## Contexto

El scaffolding implementa un único modo de operación: recibir el PDF, firmarlo en PAdES-B-T
con certificado efímero y sello de tiempo, y devolverlo. Ese modo tiene tres dependencias
externas que hoy no están resueltas —el registro de FNC en el listado de PSCNC del MIC, una
TSA cualificada contratada y el certificado real de la CA intermedia— y una consecuencia de
privacidad: exige que el documento completo viaje al servicio.

El primer tenant previsto, SeguroLoTengo, tiene un documento cuya sección FIPF contiene
**declaraciones de salud**. Recibir ese PDF convierte a FNC en encargado del tratamiento de
datos de salud de terceros, con todo lo que eso arrastra.

Al mismo tiempo, existe un modo de servicio más liviano que ya satisface el art. 4 de la
Res. SS.SG. N.º 210/2025: autenticación previa, identificación, integridad y trazabilidad,
sin necesidad de emitir certificados ni de modificar el documento.

## Decisión

Se ofrecen **dos niveles de servicio**, seleccionables por contrato de tenant y por
transacción. El recorrido del firmante es idéntico en ambos: el nivel es una propiedad del
contrato, no del flujo.

### Nivel 1 — Firma simple con acta de evidencia sellada

El tenant envía el hash SHA-256 del documento cerrado (modo *hash-only*, el predeterminado)
o, si quiere, el PDF. FNC verifica el OTP de firma o asienta la prueba de que el tenant ya lo
verificó, arma el acta de evidencia con los tres pilares —identificación, integridad,
trazabilidad—, **la sella con la clave del tenant en KMS** y devuelve la constancia
verificable. **El PDF no se modifica.**

Lo que hace verificable a este nivel no es el archivo: es el acta sellada. Un tercero puede
comprobar el sello con la clave pública publicada en `/.well-known/fnc-keys.json`, sin
acceso a nuestros registros y sin confiar en nosotros.

### Nivel 2 — Firma PAdES con certificado efímero y sello de tiempo

Todo lo del nivel 1, y además: se emite un certificado X.509 efímero para el firmante desde
la CA intermedia en KMS, se aplica una firma PAdES incremental con pyHanko, se agrega el
sello RFC 3161 de la TSA configurada y, si el tenant lo contrata, se eleva a PAdES-B-LTA.

El nivel 2 permite que las firmas cualificadas institucionales posteriores —en el caso de
SeguroLoTengo, la FEC obligatoria del corredor por el art. 5 de la 210/2025— se apliquen como
actualizaciones incrementales sobre el mismo archivo, sin invalidar la firma del cliente.

El nivel 2 **necesita el PDF**. En ese caso el documento se procesa en memoria, se firma, se
devuelve y **no se conserva**, salvo que el tenant contrate custodia de forma explícita.

### El nivel contratado por SeguroLoTengo es el 2

Decisión de negocio del 2026-09-02. Se registra junto con su condición, que no es negociable:

**El nivel 2 no puede ofrecerse en producción hasta que se cumplan tres condiciones
externas**, ninguna de las cuales depende de este equipo:

1. FNC comunicado a la DGFDCE del MIC y **publicado en el listado de PSCNC**.
2. TSA cualificada contratada con un PCSC habilitado en Paraguay.
3. Certificado real de la CA intermedia emitido sobre la clave de KMS.

Las tres están en `docs/PENDIENTES.md`. Mientras no se cumplan, el entorno `dev` opera con
CA raíz autofirmada y TSA de prueba, **etiquetadas como tales en cada certificado y en cada
acta** (`environment=dev`, `tsa=test`).

Esto significa que **el nivel 1 se construye igual y primero**, no como alternativa sino
como cimiento: el nivel 2 es el nivel 1 más el sellado de los bytes. El acta sellada existe
en los dos niveles y es lo que se entrega si la firma PAdES no está disponible.

## Justificación

1. **Desacopla el valor probatorio de la infraestructura regulatoria.** El nivel 1 produce
   evidencia oponible hoy; el nivel 2 agrega autoverificabilidad del archivo cuando los
   trámites estén cerrados. Un solo nivel obligaría a esperar.
2. **Resuelve el problema de los datos de salud** sin un contrato de tratamiento: en
   hash-only, FNC nunca ve el contenido. Es privacidad por diseño, no por política.
3. **Hace cumplible la promesa de producto** de subir de nivel sin cambiar la integración:
   la diferencia vive en la respuesta, no en la petición.
4. La distinción se corresponde con la que el propio análisis del primer tenant plantea entre
   la variante *(a) criptográfica* y la *(b) evidencia + sello visual*: FNC es la (a) elevada
   a servicio, con la (b) disponible como nivel 1.

## Consecuencias

* **Tests de contrato obligatorios** que verifiquen que la misma petición produce una
  respuesta válida en ambos niveles y que la promesa de migración se sostiene. Sin esos
  tests, la promesa es una afirmación de marketing.
* El campo `service_level` viaja en el acta sellada: un verificador tiene que poder
  distinguir un acta de nivel 1 de una de nivel 2 sin ambigüedad. Un acta que no dice su
  nivel invita a leer un nivel 1 como si sellara los bytes.
* `hash-only` es el **valor predeterminado**. Recibir el PDF es la excepción y debe pedirse.
* La responsabilidad del nivel 1 es más acotada, y eso debe reflejarse en el contrato con el
  tenant: FNC responde por el acta, no por la custodia de un documento que nunca recibió.
* Riesgo asumido: un tenant puede interpretar que el nivel 1 «firma el PDF». La constancia y
  la documentación deben decir explícitamente que en nivel 1 **el documento no se modifica**
  y que lo que prueba el acto es el acta.
