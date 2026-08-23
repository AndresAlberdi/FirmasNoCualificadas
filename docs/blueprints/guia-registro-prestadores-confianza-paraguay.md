Para constituirse formalmente como un **Prestador de Servicios de Confianza No Cualificado (PSCNC)** en la República del Paraguay, el Ministerio de Industria y Comercio (MIC), a través de la Dirección General de Firma Digital y Comercio Electrónico (DGFDCE), establece un proceso estructurado que combina la formalización comercial del negocio y la posterior notificación y adecuación técnica 1, 2\.  
A diferencia de los prestadores cualificados (PCSC), **el PSCNC no necesita de una autorización administrativa previa** para iniciar su operación, pero está sujeto a un estricto deber de comunicación de inicio de actividades y al cumplimiento de normativas operativas y de seguridad permanentes 2-4.  
A continuación se detallan los requisitos y pasos administrativos obligatorios exigidos por el MIC:

### 1\. Inscripción previa en el Registro de Prestadores de Servicios (REPSE)

Cualquier organización que pretenda proveer servicios comerciales o integrarse a las cadenas de valor en territorio paraguayo debe, **de forma obligatoria y previa**, formalizar su inscripción en el **REPSE** 5\.

* **Modalidad y Canal:** Se tramita de manera 100% electrónica a través del portal de la Ventanilla Única de Exportación (**VUE**) en vue.org.py 5-7.  
* **Costo:** Totalmente gratuito 8\.  
* **Plazo de tramitación:** 48 horas hábiles 5, 8\.  
* **Documentación requerida para Personas Jurídicas** (la estructura comercial típica para un PSCNC) 9:  
* Copia digitalizada de la **Escritura de Constitución de Sociedad** y copia del Acta de la última Asamblea (para Sociedades Anónimas) o instrumento de creación según corresponda 9, 10\.  
* Copia de la Cédula de Identidad de los directivos o representantes legales (los extranjeros deben adjuntar carnet de admisión temporal o permanente) 9\.  
* Copia de la **Patente Comercial** vigente 9\.  
* Copia de la Planilla del Instituto de Previsión Social (**IPS**) vigente en caso de contar con empleados 9\.  
* Copia de la Factura Comercial vigente 9\.  
* Copia de la Constancia de **RUC activo** 9\.  
* *Nota de responsable técnico:* Si la empresa declara actividades relacionadas con servicios profesionales tecnológicos específicos, el MIC requiere registrar un responsable técnico adjuntando su título universitario, matrícula profesional y contrato de vinculación 11\.

### 2\. Notificación formal de Inicio de Actividades ante la DGFDCE del MIC

Una vez obtenida la constancia del REPSE y habiendo comenzado efectivamente a ofrecer el servicio de firma electrónica no cualificada, opera la obligación del **Artículo 15 de la Ley N.º 6822/2021** y su reglamento 1, 2:

1. **Plazo perentorio de notificación:** Debe presentarse dentro de un **plazo improrrogable de tres (3) meses** contados a partir del inicio de la prestación del servicio 2, 4\. Omitir este plazo o retrasarse se tipifica como una **infracción leve** sujeta a sumario administrativo y multas de hasta 60 jornales mínimos 2, 12, 13\.  
2. **Canal:** El trámite se realiza forzosamente por vía electrónica dirigiendo la solicitud y los anexos al correo de la autoridad de aplicación: **info-dgce@mic.gov.py** 2, 14\.  
3. **Documentación Técnica Específica a presentar:**  
4. **Declaración de Prácticas de los Servicios Electrónicos de Confianza:** Documento exhaustivo donde el solicitante describe de forma transparente la metodología con la que presta el servicio, informando al público sobre el uso correcto, y detallando las **medidas organizativas, algoritmos de cifrado y esquemas lógicos** implementados para salvaguardar la intimidad de los firmantes y evitar la manipulación de los documentos firmados 2, 15\.  
5. **Certificados de Pruebas y Perfiles:** Evidencia de que las plantillas de los certificados electrónicos no cualificados emitidos por el sistema se ajustan estrictamente al formato técnico oficial paraguayo, de conformidad con la **Resolución N.º 262/2024** (la cual aprueba el perfil del certificado del prestador no cualificado de servicios de confianza *DOC-ICPP-20 Versión 2.0*) 2, 14\.

### 3\. Obligaciones y responsabilidades operativas permanentes (Post-Registro)

Una vez incorporado en el listado público de PSCNC del MIC 2, el sistema y la organización deben alinearse permanentemente con las siguientes obligaciones de la ley 3:

* **Notificación de incidentes de seguridad en 24 horas:** Ante cualquier intrusión, quiebre de seguridad física o lógica, alteración del servicio o impacto sobre los datos personales de los firmantes, el prestador tiene la obligación legal de reportarlo electrónicamente en un **plazo máximo de 24 horas** a la DGFDCE y al Centro de Respuestas a Incidentes Cibernéticos del MITIC 3, 16\.  
* **Tratamiento lícito de datos personales:** Los datos sensibles recopilados (como la biometría, selfies o fotos de cédulas durante el onboarding del usuario) sólo pueden utilizarse con el consentimiento informado para verificar la firma, quedando prohibida su explotación comercial 3\.  
* **Responsabilidad patrimonial directa:** El PSCNC responde civilmente por los daños causados de forma deliberada o negligente a terceros por fallos de validación o seguridad, a menos que demuestre que el usuario actuó con negligencia en la custodia de sus credenciales 3, 17\.  
* **Auditorías de Vulnerabilidad del software:** Para cumplir con el marco de ciberseguridad que coordina el MITIC, el PSCNC debe someter su software transaccional a auditorías periódicas de vulnerabilidades antes de poner nuevas versiones del sistema en producción (Resoluciones MITIC N.° 277/2020 y N.° 553/2024) 18\.

### Resumen de la Ruta de Formalización Administrativa

1. **Constitución e inicio técnico:** Levantamiento del módulo criptográfico en AWS y su plataforma de onboarding.  
2. **Inscripción en el REPSE:** Trámite 100% online y gratuito a través del VUE (aprobación en 48 horas) 5, 8\.  
3. **Inicio de operaciones:** Habilitación comercial y despliegue del servicio para los primeros usuarios.  
4. **Notificación al MIC (Plazo: \< 3 meses):** Envío electrónico de la Declaración de Prácticas y perfiles técnicos conforme a la Resolución N.º 262/2024 2\.  
5. **Inclusión en el Listado Oficial:** El MIC publica los datos básicos del prestador en la web oficial para conocimiento público 2\.

🤖 **¿Qué te gustaría hacer a continuación?**Podríamos actualizar el documento técnico que preparé anteriormente en tu Studio (blueprint-firma-no-cualificada-paraguay.md) para agregar un anexo de "Ruta de Cumplimiento Administrativo ante el MIC", detallando los plazos, los correos oficiales de entrega, y la integración de la Declaración de Prácticas con la Resolución N.º 262/2024. Así, Claude AI tendrá el panorama técnico-regulatorio completo y de extremo a extremo.  
