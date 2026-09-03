# ADR-0011 · FNC es un motor que el cliente despliega, no un prestador de servicios de confianza

* **Estado:** Aceptado
* **Fecha:** 2026-09-03
* **Decisores:** Dirección, Arquitectura, Legal
* **Reemplaza el encuadre de:** ADR-0009 (que sigue vigente en todo lo demás)

## Contexto

El proyecto se concibió como un SaaS multi-inquilino que presta el servicio de firma
electrónica no cualificada a terceros, operando como **Prestador de Servicios de Confianza No
Cualificado**. De ese encuadre se derivaban tres obligaciones: comunicar el inicio de
actividad al Ministerio, ceñirse al perfil de certificado `DOC-ICPP-20 v2.0` y aparecer en el
listado público de prestadores.

Ese encuadre descansaba sobre una definición que **nadie del equipo había leído en el texto de
la ley**. Ahora sí está leída. La Ley N.º 6822/2021, en su artículo 4.º, numeral 48, define:

> Servicio de confianza: el servicio electrónico **prestado habitualmente a cambio de una
> remuneración**, consistente en: a) **la creación**, verificación y validación de firmas
> electrónicas, sellos electrónicos, sellos de tiempo electrónicos, servicios de entrega
> electrónica certificada y certificados relativos a estos servicios […]

Y su artículo 15 dirige la obligación de comunicar la actividad a los **prestadores** de
servicios de confianza no cualificados.

La dirección resuelve, con ese respaldo, que **FNC no va a prestar el servicio de firma a
terceros**. El producto es el motor: un cliente lo despliega en su propia infraestructura para
firmar sus propias contrataciones, que es un mecanismo interno y no un servicio de confianza.

## Decisión

**FNC deja de ser un prestador y pasa a ser un motor embebible.** El cliente lo opera; FNC no
firma nada de nadie.

### La condición de la que depende todo el encuadre

La exención no la produce la palabra «interno», sino **quién realiza la creación de la firma y
a cambio de qué**. El numeral 48 nombra expresamente «la creación […] de firmas electrónicas»
como uno de los servicios, y le pone dos condiciones acumulativas: que se preste
*habitualmente* y *a cambio de una remuneración*.

De ahí se sigue una consecuencia que no es documental sino arquitectónica:

> **Si FNC alojara la plataforma y creara las firmas de sus clientes a cambio de una
> remuneración, seguiría prestando un servicio de confianza** —por más que cada cliente firme
> sus propios contratos—, y el registro volvería a ser obligatorio.

Por lo tanto, el modelo de entrega tiene que ser **despliegue del cliente**: su cuenta de
nube, sus claves, su operación. FNC vende y mantiene el software; no opera la firma. Un
alojamiento multi-inquilino gestionado por FNC reabriría exactamente la obligación que este
ADR cierra.

### Lo que se cae

| Obligación | Estado |
| :---- | :---- |
| Comunicar el inicio de actividad (`FOR-ICPP-02`, art. 15) | **No aplica.** FNC no es prestador |
| Perfil de certificado `DOC-ICPP-20 v2.0` | **No aplica.** Sus §3 y §4 rigen al prestador y a los certificados que el prestador emite |
| Certificado de CA intermedia bajo la infraestructura del Estado | **No aplica** por lo mismo |
| Aparecer en el listado público de prestadores (Decreto, art. 5.º) | **No aplica** |
| Incidentes de seguridad en 24 h al Ministerio (Decreto, art. 6.º) | **No aplica a FNC.** Sí alcanzaría a un cliente que además fuera prestador |

### Lo que no se cae, y es lo que importa

Ninguna de las propiedades probatorias cambia, porque no venían del registro:

* **Art. 39.2** — la equivalencia con la firma manuscrita se reconoce *solo* a la firma
  cualificada. Una firma no cualificada, interna o no, nunca la tiene.
* **Art. 40** — impugnada la autenticidad, se está al artículo 404 del Código Civil. Lo que se
  exhibe entonces es el expediente de evidencias.
* **Art. 63.1.b** — ni siquiera la firma cualificada hace fe respecto de la **fecha** sin sello
  de tiempo de un prestador cualificado. La fecha cierta sigue exigiendo una TSA cualificada,
  ahora contratada por el cliente y no por nosotros.

Dicho de otro modo: **dejamos de tener obligaciones administrativas y conservamos íntegras las
probatorias.** El acta sellada, la pista de auditoría append-only, el aislamiento por clave y
la verificación pública siguen siendo la razón de ser del producto — de hecho pasan a ser la
*única* razón, porque ya no hay un registro que aporte respetabilidad por sí solo.

## Consecuencias

1. **El «inquilino» deja de ser un cliente de un servicio y pasa a ser un despliegue.** El
   aislamiento multi-inquilino (ADR-0005) no se elimina: un despliegue puede seguir teniendo
   varias unidades de negocio, y la propiedad de aislamiento sigue siendo valiosa. Lo que
   cambia es que **el operador del despliegue es el cliente**.
2. **Las claves de KMS pasan a la cuenta del cliente.** Es la diferencia entre vender el motor
   y operar el servicio, y es lo que sostiene el encuadre. El Terraform ya está parametrizado
   por entorno; hay que revisar qué supone que la cuenta es nuestra.
3. **Los tres bloqueantes del ADR-0007 dejan de bloquear a FNC.** Pasan a ser requisitos del
   cliente que quiera nivel 2: contratar la TSA y emitir su CA. FNC entrega el motor capaz de
   usarlas.
4. **El perfil de jurisdicción no pierde sentido**, lo gana: sigue fijando qué norma se cita,
   qué documentos se admiten y cuánto se conserva la evidencia, que es lo que un cliente
   necesita para operar en su país.
5. **La conformidad con `DOC-ICPP-20` deja de ser obligatoria y pasa a ser una opción de
   producto.** Se conserva el trabajo ya hecho: un cliente que sí sea prestador la necesita, y
   emitir certificados conformes no perjudica a quien no lo es. Los pendientes P-03, P-05 y
   P-06 bajan de prioridad, no se cancelan.

## Riesgo que esta decisión no elimina

**El encuadre depende de una lectura, no de un pronunciamiento.** El texto es claro y la
lectura es directa, pero quien la sostiene hoy es el propio equipo. Sigue pendiente el
dictamen escrito de asesoría paraguaya (L-05), y su valor no es interpretativo sino de
oponibilidad: si el encuadre se discute, la empresa exhibe una opinión profesional fechada y
no una lectura propia.

Conviene además que la consulta incluya la pregunta que abre este ADR: **hasta dónde puede
llegar el soporte al cliente sin que FNC pase a «prestar» el servicio.** Alojar la
infraestructura casi con seguridad cruza la línea; operar las claves en nombre del cliente
también. Entre eso y vender una licencia hay un espacio gris que conviene delimitar antes de
construir sobre él.

## Alternativas descartadas

**Seguir como prestador y registrarse.** Es viable y el trabajo está hecho a medias, pero
arrastra tres bloqueantes —TSA contratada, CA emitida, registro ante el Ministerio—, un plazo
legal de tres meses desde el inicio de actividad y la supervisión permanente del organismo.
La dirección resuelve que ese costo no se justifica para el mercado al que apunta el producto.

**Un modelo mixto: motor embebido y, además, servicio alojado para quien lo prefiera.** Se
descarta *por ahora* porque la variante alojada reabre la obligación de registro completa, y
tenerla abierta para una parte del negocio equivale a tenerla abierta. Puede reconsiderarse
cuando exista el dictamen legal y con un ADR propio.
