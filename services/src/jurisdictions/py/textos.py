"""Textos de producto de la jurisdicción paraguaya.

Se separan del perfil porque cambian por razones distintas: el perfil cambia
cuando cambia la norma; estos textos, cuando cambia cómo se le explica al
firmante. Todo texto que llegue a una persona en Paraguay sale de acá.
"""

from __future__ import annotations

TEXTOS: dict[str, str] = {
    # ------------------------------------------------------- Constancia -----
    "constancia.titulo": "Constancia de firma electrónica",
    "constancia.naturaleza": (
        "Firma electrónica no cualificada, generada por el prestador identificado en "
        "este documento."
    ),
    "constancia.pilar.identificacion.titulo": "Quién firmó",
    "constancia.pilar.identificacion.explicacion": (
        "La identidad se verificó antes de firmar, y el código de un solo uso se envió "
        "al canal que la persona ya había verificado."
    ),
    "constancia.pilar.integridad.titulo": "Qué se firmó",
    "constancia.pilar.integridad.explicacion": (
        "El documento se cerró y se le calculó una huella SHA-256 antes de habilitar la "
        "firma. Cualquier cambio posterior da una huella distinta."
    ),
    "constancia.pilar.trazabilidad.titulo": "Desde dónde y cuándo",
    "constancia.pilar.trazabilidad.explicacion": (
        "El acto quedó asentado con su fecha, su dirección IP y su dispositivo, en un "
        "registro que no se sobrescribe ni se borra."
    ),
    # ------------------------------------------------------- Expediente -----
    "expediente.titulo": "Expediente de Evidencias Técnicas",
    "expediente.autor": "Prestador de Servicios de Confianza No Cualificado",
    "expediente.introduccion": (
        "Documento generado automáticamente por la plataforma del Prestador de Servicios "
        "de Confianza No Cualificado. Contiene la pista de auditoría de una firma "
        "electrónica no cualificada conforme a la Ley N.º 6822/2021 y su Decreto "
        "Reglamentario N.º 7576/2022."
    ),
    "expediente.pie": (
        "Expediente de evidencias — Prestador de Servicios de Confianza No Cualificado "
        "(Ley N.º 6822/2021, Paraguay)"
    ),
    "expediente.valor_probatorio": (
        "La firma electrónica no cualificada goza de validez jurídica por el principio de "
        "no discriminación (Art. 39 de la Ley N.º 6822/2021), pero carece de presunción "
        "automática de autoría. Este expediente es la evidencia que sostiene la "
        "atribución del acto ante una pericia informática forense."
    ),
    # ----------------------------------------------------------- Firma ------
    "firma.motivo": "Firma Electronica No Cualificada - Ley N 6822/2021 (Paraguay)",
    "firma.lugar": "Paraguay",
    # ------------------------------------------------------ Certificado -----
    # Aviso al usuario del calificador `User Notice` de `certificatePolicies`.
    # El perfil de certificado exige el calificador; el texto es de la
    # jurisdicción, porque nombra la declaración de prácticas del prestador.
    "certificado.aviso_de_uso": (
        "Sujeto a las condiciones de uso expuestas en la Declaración de Prácticas "
        "del prestador no cualificado de servicios de confianza emisor."
    ),
    # --------------------------------------------------- Constancia visible --
    # Rótulos del bloque que se imprime dentro del PDF firmado. Son texto de
    # producto de la jurisdicción: el motor no los conoce.
    "bloque_firma.titulo": "FIRMA ELECTRONICA DEL PROPONENTE",
    "bloque_firma.firmante": "Firmante",
    "bloque_firma.documento": "Documento de identidad",
    "bloque_firma.caracter": "Caracter",
    "bloque_firma.documento_firmado": "Documento firmado",
    "bloque_firma.codigo": "Codigo de solicitud",
    "bloque_firma.fecha": "Fecha y hora de firma",
    "bloque_firma.autenticacion": "Metodo de autenticacion",
    "bloque_firma.operacion": "Identificador de la operacion",
    "bloque_firma.version": "Version del documento",
    "bloque_firma.huella": "Huella digital SHA-256",
    "bloque_firma.estado": "Estado",
    "bloque_firma.estado_validada": "Firma electronica validada",
    # La declaración de consentimiento. Es lo único del bloque que no describe un
    # dato sino que afirma un acto, y por eso su redacción es materia legal: se
    # revisa con asesoría antes de cambiarla (L-01 de docs/PENDIENTES.md).
    "bloque_firma.declaracion": (
        "El firmante declara haber revisado integramente este documento y manifiesta "
        "su consentimiento libre, expreso e inequivoco respecto de la solicitud, las "
        "declaraciones, autorizaciones y condiciones contenidas en el. La firma "
        "electronica se encuentra vinculada al presente documento mediante su "
        "identificador unico y huella digital."
    ),
    # ------------------------------------------------------- Rechazos -------
    "rechazo.acto_excluido": (
        "El documento contiene indicios de un acto jurídico que requiere forma solemne o "
        "está excluido de la firma electrónica no cualificada. La operación se bloquea "
        "conforme a la política de uso del servicio."
    ),
    "rechazo.documento_invalido": (
        "El número de documento no tiene el formato de una cédula de identidad paraguaya."
    ),
}
