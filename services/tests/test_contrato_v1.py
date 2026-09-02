"""Contrato público v1 (ADR-0007, ADR-0009).

Cubre las dos reglas inviolables que faltaban:

* **Regla 4 — datos sensibles aislados.** Ni el acta ni la constancia pública
  llevan cédula, nombre, datos de salud ni el código del OTP.
* **Regla 14 — FNC no vuelve a decidir la identidad.** Recibe la decisión del
  tenant y la asienta; solo lee su veredicto.

Cierra además con el caso que da sentido a todo el contrato: **SeguroLoTengo
integrándose en modo `TENANT_VERIFIED` + hash-only**, que es el plan de
convergencia de su validación legal.

Todos los datos son sintéticos.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from jwcrypto import jwk as jose_jwk
from jwcrypto import jws as jose_jws

from conftest import KmsFiel
from pscnc.crypto.tenant_keys import TenantKeyRing
from pscnc.evidence.acta import ActaSealer
from pscnc.evidence.claves_publicas import jwk_desde_der
from pscnc.models.motivos import RETRYABLE_REASONS, TERMINAL_REASONS, RejectionReason
from pscnc.models.v1 import (
    ConfirmTransactionRequest,
    CreateTransactionRequest,
    DocumentRef,
    IdentityDecision,
    OtpChannel,
    OtpMode,
    OtpProof,
    ServiceLevel,
    TransactionStatus,
)
from pscnc.orchestrator.transacciones import (
    TransactionRejectedError,
    TransactionRepository,
    TransactionService,
    generate_verification_code,
)

TENANT = "segurolotengo"
OTRO_TENANT = "banco-py"
ENTORNO = "dev"
CERRADO = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)
HASH_DOC = "a" * 64

#: Datos del firmante que NUNCA deben aparecer en un artefacto público.
DATOS_DEL_FIRMANTE = ("4829153", "Juan Pérez", "hipertensión", "654321")


@pytest.fixture()
def kms() -> KmsFiel:
    return KmsFiel(
        [
            f"alias/fnc/{ENTORNO}/{TENANT}/acta-seal/v1",
            f"alias/fnc/{ENTORNO}/{OTRO_TENANT}/acta-seal/v1",
        ]
    )


@pytest.fixture()
def llavero(kms: KmsFiel) -> TenantKeyRing:
    return TenantKeyRing(TENANT, environment=ENTORNO, region="us-east-1", client=kms)


@pytest.fixture()
def servicio(llavero: TenantKeyRing) -> TransactionService:
    return TransactionService(
        repositorio=TransactionRepository(),
        sellador=ActaSealer(llavero),
        jurisdiccion_por_defecto="PY",
    )


def _decision(*, aprobada: bool = True) -> IdentityDecision:
    """Decisión con la política real del primer tenant: 99 sobre 100."""
    return IdentityDecision(
        approved=aprobada,
        threshold_applied=0.99,
        score=0.995,
        score_scale="0-100",
        model_version="rekognition-2026-07",
        policy_version="slt-identidad-v4",
        provider_reference="onb_72189312",
        liveness_verified=True,
        verified_at=CERRADO - timedelta(minutes=5),
    )


def _crear(**cambios: Any) -> CreateTransactionRequest:
    base: dict[str, Any] = {
        "tenant_reference": "EXP-99887",
        "document": DocumentRef(
            sha256=HASH_DOC, version=2, code="PROP-2026-000123", closed_at=CERRADO
        ),
        "identity_decision": _decision(),
    }
    base.update(cambios)
    return CreateTransactionRequest(**base)


def _confirmar(**cambios: Any) -> ConfirmTransactionRequest:
    base: dict[str, Any] = {
        "otp_proof": OtpProof(
            otp_reference="otp_abc123",
            channel=OtpChannel.WHATSAPP,
            destination_masked="+595 98* *** *56",
            sent_at=CERRADO,
            verified_at=CERRADO + timedelta(seconds=40),
        ),
        "consent_statement": "Acepto firmar electrónicamente la propuesta y el FIPF.",
        "consent_statement_version": "p8-consentimiento-v3",
        "document_sha256": HASH_DOC,
        "signer_ip": "190.104.128.5",
    }
    base.update(cambios)
    return ConfirmTransactionRequest(**base)


# --------------------------------------------------- Identidad del tenant ---
class TestIdentidadDelTenant:
    """Regla inviolable 14: FNC no vuelve a decidir la identidad."""

    def test_asienta_la_decision_aprobada_sin_revisarla(self, servicio: TransactionService) -> None:
        """Un puntaje que FNC habría rechazado con su viejo umbral igual pasa.

        El umbral propio dejó de ser un control: si FNC volviera a decidir,
        aprobaría casos que la política del tenant rechaza, o al revés. Dos
        controles sobre el mismo acto no se suman, gana el más laxo.
        """
        decision = _decision()
        object.__setattr__(decision, "score", 0.93)  # por debajo del viejo 0.95

        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(identity_decision=decision))

        assert creada.status is TransactionStatus.CREATED

    def test_rechaza_si_el_tenant_declaro_que_no_aprobo(self, servicio: TransactionService) -> None:
        """Leer el veredicto ajeno no es tomar uno propio."""
        with pytest.raises(TransactionRejectedError) as error:
            servicio.crear(
                tenant_id=TENANT, peticion=_crear(identity_decision=_decision(aprobada=False))
            )

        assert error.value.motivo is RejectionReason.IDENTITY_NOT_APPROVED

    def test_un_puntaje_sin_normalizar_se_rechaza(self) -> None:
        """La escala del primer tenant es 0-100: mandar `98` crudo es el error real."""
        with pytest.raises(ValueError, match="less than or equal to 1"):
            IdentityDecision(
                approved=True,
                threshold_applied=0.99,
                score=98.0,  # sin normalizar
                score_scale="0-100",
                model_version="m",
                policy_version="p",
                provider_reference="r",
            )

    def test_un_puntaje_normalizado_con_escala_de_origen_es_valido(self) -> None:
        """99,5 sobre 100 llega como 0.995 y declara de dónde viene."""
        decision = IdentityDecision(
            approved=True,
            threshold_applied=0.99,
            score=0.995,
            score_scale="0-100",
            model_version="m",
            policy_version="p",
            provider_reference="r",
        )

        assert decision.score == 0.995

    def test_la_escala_de_origen_queda_registrada(self) -> None:
        """La escala del tenant se conserva: es dato pericial."""
        assert _decision().score_scale == "0-100"


# --------------------------------------------------------- OTP del tenant ---
class TestOtpDelTenant:
    def test_la_prueba_del_tenant_alcanza_para_confirmar(
        self, servicio: TransactionService
    ) -> None:
        """En TENANT_VERIFIED el OTP es evidencia, no un control que se revalida."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())

        confirmada = servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )

        assert confirmada.status is TransactionStatus.CONFIRMED

    def test_sin_prueba_de_otp_no_se_confirma(self, servicio: TransactionService) -> None:
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(otp_proof=None),
            )

        assert error.value.motivo is RejectionReason.OTP_NOT_VERIFIED

    def test_no_se_admiten_las_dos_vias_a_la_vez(self) -> None:
        """Recibir ambas dejaría sin definir cuál gobierna el acto."""
        with pytest.raises(ValueError, match="nunca ambos"):
            _confirmar(otp_code="123456")

    def test_el_destino_debe_viajar_enmascarado(self) -> None:
        """Atrapa el error más frecuente: mandar el número entero por costumbre."""
        with pytest.raises(ValueError, match="enmascarado"):
            OtpProof(
                otp_reference="otp_1",
                channel=OtpChannel.WHATSAPP,
                destination_masked="+595981123456",
                sent_at=CERRADO,
                verified_at=CERRADO,
            )

    def test_el_otp_no_puede_verificarse_antes_de_enviarse(self) -> None:
        with pytest.raises(ValueError, match="antes de enviarse"):
            OtpProof(
                otp_reference="otp_1",
                channel=OtpChannel.SMS,
                destination_masked="+595 *** *56",
                sent_at=CERRADO,
                verified_at=CERRADO - timedelta(seconds=1),
            )


# ------------------------------------------------------------- Documento ---
class TestDocumento:
    def test_hash_only_es_el_modo_por_defecto(self) -> None:
        """Lo que no se recibe no se filtra."""
        peticion = _crear()

        assert not hasattr(peticion, "document_content")
        assert peticion.document.sha256 == HASH_DOC

    def test_una_huella_distinta_al_confirmar_se_rechaza(
        self, servicio: TransactionService
    ) -> None:
        """Si el documento se regeneró, lo que se firma no es lo que se revisó."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(document_sha256="f" * 64),
            )

        assert error.value.motivo is RejectionReason.DOCUMENT_TAMPERED

    def test_el_nivel_2_se_rechaza_con_un_motivo_propio(self, servicio: TransactionService) -> None:
        """Distinguirlo de un fallo transitorio evita que el tenant reintente."""
        with pytest.raises(TransactionRejectedError) as error:
            servicio.crear(tenant_id=TENANT, peticion=_crear(service_level=ServiceLevel.PADES))

        assert error.value.motivo is RejectionReason.SERVICE_LEVEL_UNAVAILABLE


# ------------------------------------------------- Aislamiento y estados ---
class TestAislamientoYEstados:
    def test_otro_inquilino_no_accede_a_la_transaccion(self, servicio: TransactionService) -> None:
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())

        with pytest.raises(TransactionRejectedError) as error:
            servicio.artefactos(tenant_id=OTRO_TENANT, transaction_id=creada.transaction_id)

        assert error.value.motivo is RejectionReason.TRANSACTION_OF_ANOTHER_TENANT

    def test_una_transaccion_inexistente_se_distingue_de_una_ajena(
        self, servicio: TransactionService
    ) -> None:
        """El inquilino está autenticado: ocultarle que existe no lo protege."""
        with pytest.raises(TransactionRejectedError) as error:
            servicio.artefactos(tenant_id=TENANT, transaction_id="no-existe")

        assert error.value.motivo is RejectionReason.TRANSACTION_NOT_FOUND

    def test_no_se_confirma_dos_veces(self, servicio: TransactionService) -> None:
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())
        servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
            )

        assert error.value.motivo is RejectionReason.TRANSACTION_ALREADY_CONFIRMED

    def test_una_transaccion_expirada_no_se_confirma(self, llavero: TenantKeyRing) -> None:
        servicio = TransactionService(
            repositorio=TransactionRepository(),
            sellador=ActaSealer(llavero),
            jurisdiccion_por_defecto="PY",
            ttl_minutos=0,
        )
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
            )

        assert error.value.motivo is RejectionReason.TRANSACTION_EXPIRED


# ----------------------------------------------------- Datos sensibles -----
class TestDatosSensiblesAislados:
    """Regla inviolable 4: nada personal sale en un artefacto."""

    def test_el_acta_no_lleva_datos_del_firmante(self, servicio: TransactionService) -> None:
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())
        confirmada = servicio.confirmar(
            tenant_id=TENANT,
            transaction_id=creada.transaction_id,
            peticion=_confirmar(
                consent_statement=(
                    "Yo, Juan Pérez, con cédula 4829153, declaro no padecer hipertensión "
                    "y acepto firmar."
                )
            ),
        )

        import base64

        payload = base64.urlsafe_b64decode(confirmada.acta.jws.split(".")[1] + "==").decode()

        for dato in DATOS_DEL_FIRMANTE:
            assert dato not in payload, f"{dato!r} no debe viajar en el acta"

    def test_del_consentimiento_solo_viaja_su_huella(self, servicio: TransactionService) -> None:
        """El texto puede llevar el nombre; lo que hay que probar es que fue *ese*."""
        import base64

        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())
        confirmada = servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )
        payload = json.loads(base64.urlsafe_b64decode(confirmada.acta.jws.split(".")[1] + "=="))

        assert len(payload["evidence_sha256"]) == 64
        assert "consent_statement" not in payload

    def test_la_constancia_publica_no_expone_al_firmante(
        self, servicio: TransactionService
    ) -> None:
        """La consulta cualquiera que reciba el documento: no puede revelar quién firmó."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())
        confirmada = servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )

        constancia = servicio.verificar(confirmada.verification_code)
        texto = constancia.model_dump_json()

        assert constancia.exists is True
        for dato in DATOS_DEL_FIRMANTE:
            assert dato not in texto

    def test_un_codigo_inexistente_no_revela_nada(self, servicio: TransactionService) -> None:
        """Quien prueba códigos al azar no debe poder averiguar cuáles existen."""
        constancia = servicio.verificar("AAAAAAAAAAAA")

        assert constancia.exists is False
        assert constancia.status is None
        assert constancia.document_sha256 is None


# ---------------------------------------------- Verificación y constancia ---
class TestConstanciaPublica:
    def test_cita_la_norma_de_la_jurisdiccion(self, servicio: TransactionService) -> None:
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())
        confirmada = servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )

        constancia = servicio.verificar(confirmada.verification_code)

        assert "210/2025" in (constancia.legal_basis or "")

    def test_entrega_el_acta_para_que_un_tercero_la_verifique(
        self, servicio: TransactionService, llavero: TenantKeyRing
    ) -> None:
        """El sentido del código público: verificar sin credenciales ni confianza."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear())
        confirmada = servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )

        constancia = servicio.verificar(confirmada.verification_code)
        clave = jose_jwk.JWK(
            **jwk_desde_der(llavero.public_key_der(), kid=llavero.acta_seal_alias).to_dict()
        )

        verificador = jose_jws.JWS()
        verificador.deserialize(constancia.acta_jws or "")
        verificador.verify(clave)  # no lanza: el acta es auténtica

    def test_el_codigo_evita_caracteres_que_se_confunden(self) -> None:
        """Se transcribe a mano desde un papel: I/L/O/0/1 son un problema real."""
        codigos = "".join(generate_verification_code() for _ in range(200))

        for confuso in ("I", "L", "O", "0", "1"):
            assert confuso not in codigos


# ------------------------------------------------------------- Motivos -----
class TestMotivosEstables:
    def test_los_motivos_son_cadenas_estables(self) -> None:
        """El tenant programa contra estos valores: renombrarlos rompe su `match`."""
        assert RejectionReason.IDENTITY_NOT_APPROVED.value == "IDENTITY_NOT_APPROVED"
        assert RejectionReason.DOCUMENT_TAMPERED.value == "DOCUMENT_TAMPERED"
        assert (
            RejectionReason.TRANSACTION_ALREADY_CONFIRMED.value == "TRANSACTION_ALREADY_CONFIRMED"
        )

    def test_ningun_motivo_es_a_la_vez_reintentable_y_terminal(self) -> None:
        """Una contradicción acá haría que el SDK reintentara un acto consumido."""
        assert not (RETRYABLE_REASONS & TERMINAL_REASONS)

    def test_el_otp_consumido_no_es_reintentable(self) -> None:
        """Un OTP es de un solo uso: reintentar con el mismo código no lo revive."""
        assert RejectionReason.OTP_ALREADY_USED in TERMINAL_REASONS


# ---------------------------------------- Integración del primer tenant ----
class TestIntegracionSeguroLoTengo:
    """El recorrido completo del plan de convergencia: TENANT_VERIFIED + hash-only.

    Reproduce lo que hará el adaptador `firma-cliente-fnc` detrás del puerto de
    firma del tenant, **sin cambiar el recorrido del cliente**: el mismo OTP, la
    misma pantalla, los mismos pasos.
    """

    def test_recorrido_completo(self, servicio: TransactionService, llavero: TenantKeyRing) -> None:
        # 1. El tenant ya verificó identidad (99/100) y ya cerró el paquete
        #    documental con su huella. Abre la transacción en hash-only.
        creada = servicio.crear(
            tenant_id=TENANT,
            peticion=_crear(otp_mode=OtpMode.TENANT_VERIFIED),
        )
        assert creada.jurisdiction == "PY"
        assert creada.service_level is ServiceLevel.SEALED_ACTA
        assert creada.tenant_reference == "EXP-99887"

        # 2. El tenant emitió y verificó su tercer OTP, el de propósito FIRMA, y
        #    manda la prueba como evidencia.
        confirmada = servicio.confirmar(
            tenant_id=TENANT, transaction_id=creada.transaction_id, peticion=_confirmar()
        )
        assert confirmada.status is TransactionStatus.CONFIRMED
        assert confirmada.acta.algorithm == "ES256"

        # 3. Los dos registros se citan mutuamente (ADR-0009): el del tenant es el
        #    autoritativo del contrato, el de FNC es el acta del acto de firma.
        import base64

        payload = json.loads(base64.urlsafe_b64decode(confirmada.acta.jws.split(".")[1] + "=="))
        assert payload["tenant_reference"] == "EXP-99887"
        assert payload["transaction_id"] == creada.transaction_id

        # 4. El expediente del tenant puede recuperar el acta cuando la necesite.
        artefactos = servicio.artefactos(tenant_id=TENANT, transaction_id=creada.transaction_id)
        assert artefactos.acta is not None
        assert artefactos.verification_code == confirmada.verification_code

        # 5. Y el cliente final —o su abogado— verifica sin credenciales.
        constancia = servicio.verificar(confirmada.verification_code)
        clave = jose_jwk.JWK(
            **jwk_desde_der(llavero.public_key_der(), kid=llavero.acta_seal_alias).to_dict()
        )
        verificador = jose_jws.JWS()
        verificador.deserialize(constancia.acta_jws or "")
        verificador.verify(clave)

        assert constancia.document_sha256 == HASH_DOC
        assert constancia.document_code == "PROP-2026-000123"

    def test_el_documento_nunca_llega_al_servicio(self, servicio: TransactionService) -> None:
        """La razón de hash-only: la Solicitud lleva declaraciones de salud.

        Recibir el PDF convertiría a FNC en encargado del tratamiento de datos de
        salud sin contrato que lo respalde.
        """
        peticion = _crear()
        campos = set(peticion.model_dump())

        assert "document_content" not in campos
        assert "pdf" not in campos
        assert set(peticion.document.model_dump()) == {
            "sha256",
            "version",
            "code",
            "closed_at",
        }
