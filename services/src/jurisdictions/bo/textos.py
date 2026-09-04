"""Textos de producto del perfil boliviano.

**Perfil sin validación legal.** Los textos son estructuralmente equivalentes a los
paraguayos y existen para demostrar que la capa de presentación está parametrizada,
no para usarse ante un firmante real. Toda referencia normativa lleva el prefijo
``[SIN VERIFICAR]`` justamente para que no pueda pasar inadvertida si alguien
intentara habilitar este perfil sin la revisión legal previa.
"""

from __future__ import annotations

_ADVERTENCIA = "[SIN VERIFICAR] "

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
        _ADVERTENCIA + "Documento generado automáticamente por la plataforma del "
        "prestador. Contiene la pista de auditoría de una firma electrónica no "
        "cualificada. El marco normativo boliviano aplicable no ha sido verificado."
    ),
    "expediente.pie": (
        _ADVERTENCIA + "Expediente de evidencias — perfil de jurisdicción sin validación legal"
    ),
    "expediente.valor_probatorio": (
        _ADVERTENCIA + "El valor probatorio de la firma electrónica no cualificada en "
        "el Estado Plurinacional de Bolivia no ha sido analizado por asesoría legal "
        "local. Este perfil existe para verificar que la plataforma generaliza a otra "
        "jurisdicción, no para producir evidencia oponible."
    ),
    # ----------------------------------------------------------- Firma ------
    "firma.motivo": _ADVERTENCIA + "Firma Electronica No Cualificada",
    "firma.lugar": "Bolivia",
    # ------------------------------------------------------- Rechazos -------
    "rechazo.acto_excluido": (
        "El documento contiene indicios de un acto jurídico que requiere forma solemne o "
        "está excluido de la firma electrónica no cualificada. La operación se bloquea "
        "conforme a la política de uso del servicio."
    ),
    "rechazo.documento_invalido": (
        "El número de documento no tiene el formato de una cédula de identidad boliviana."
    ),
    # Estructural, como el resto del perfil: no hay constancia de qué exige la
    # norma boliviana en este calificador.
    "certificado.aviso_de_uso": (
        "[SIN VERIFICAR] Sujeto a las condiciones de uso expuestas en la Declaración "
        "de Prácticas del prestador emisor."
    ),
    # Estructural. La redacción y los rótulos dependen de la norma boliviana,
    # que sigue sin verificar.
    "bloque_firma.titulo": "[SIN VERIFICAR] titulo",
    "bloque_firma.firmante": "[SIN VERIFICAR] firmante",
    "bloque_firma.documento": "[SIN VERIFICAR] documento",
    "bloque_firma.caracter": "[SIN VERIFICAR] caracter",
    "bloque_firma.documento_firmado": "[SIN VERIFICAR] documento firmado",
    "bloque_firma.codigo": "[SIN VERIFICAR] codigo",
    "bloque_firma.fecha": "[SIN VERIFICAR] fecha",
    "bloque_firma.autenticacion": "[SIN VERIFICAR] autenticacion",
    "bloque_firma.operacion": "[SIN VERIFICAR] operacion",
    "bloque_firma.version": "[SIN VERIFICAR] version",
    "bloque_firma.huella": "[SIN VERIFICAR] huella",
    "bloque_firma.estado": "[SIN VERIFICAR] estado",
    "bloque_firma.estado_validada": "[SIN VERIFICAR] estado validada",
    "bloque_firma.declaracion": "[SIN VERIFICAR] declaracion",
}
