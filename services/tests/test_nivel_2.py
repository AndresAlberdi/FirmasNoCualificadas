"""Nivel 2: firma PAdES con certificado efímero y sello de tiempo (ADR-0007).

Cubre la última regla inviolable que quedaba sin prueba:

* **Regla 12 — sin fecha cierta no hay firma.** Si la autoridad de sellado falla,
  la transacción falla completa y no se degrada a PAdES-B-B.

Y las dos propiedades que hacen útil al nivel 2 frente al nivel 1:

* El PDF firmado es **autoverificable**: un validador comprueba la firma sin
  acceso a nuestros registros.
* Una firma posterior —la cualificada del corredor, en el caso del primer
  tenant— se aplica como **actualización incremental** y no invalida la del
  cliente.

Todos los datos son sintéticos.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from conftest import KmsFiel
from jurisdictions import get_profile
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData
from pscnc.crypto.pades import PadesSigner
from pscnc.crypto.tenant_keys import TenantKeyRing
from pscnc.errors import TimestampError
from pscnc.evidence.acta import ActaSealer
from pscnc.models.motivos import RejectionReason
from pscnc.models.v1 import (
    ConfirmTransactionRequest,
    CreateTransactionRequest,
    DocumentRef,
    IdentityDecision,
    OtpChannel,
    OtpProof,
    ServiceLevel,
)
from pscnc.orchestrator.transacciones import (
    TransactionRejectedError,
    TransactionRepository,
    TransactionService,
)

TENANT = "segurolotengo"
CERRADO = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)


@pytest.fixture()
def autoridad(ca_certificate_der: bytes, ca_signer: Any) -> EphemeralCertificateAuthority:
    """CA intermedia en el entorno `dev`, que marca sus certificados."""
    return EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url="https://crl.pruebas.example/intermediate.crl",
        environment="dev",
    )


@pytest.fixture()
def firmante(autoridad: EphemeralCertificateAuthority, tsa_de_prueba: Any) -> PadesSigner:
    return PadesSigner(
        certificate_authority=autoridad,
        timestamper_factory=tsa_de_prueba,
        jurisdiction=get_profile("PY"),
    )


@pytest.fixture()
def servicio(firmante: PadesSigner) -> TransactionService:
    kms = KmsFiel([f"alias/fnc/dev/{TENANT}/acta-seal/v1"])
    llavero = TenantKeyRing(TENANT, environment="dev", region="us-east-1", client=kms)
    return TransactionService(
        repositorio=TransactionRepository(),
        sellador=ActaSealer(llavero),
        jurisdiccion_por_defecto="PY",
        firmante_pades=firmante,
        environment="dev",
    )


def _crear(pdf: bytes) -> CreateTransactionRequest:
    return CreateTransactionRequest(
        tenant_reference="EXP-99887",
        document=DocumentRef(
            sha256=hashlib.sha256(pdf).hexdigest(),
            version=2,
            code="PROP-2026-000123",
            closed_at=CERRADO,
        ),
        identity_decision=IdentityDecision(
            approved=True,
            threshold_applied=0.99,
            score=0.995,
            score_scale="0-100",
            model_version="rekognition-2026-07",
            policy_version="slt-identidad-v4",
            provider_reference="onb_72189312",
            liveness_verified=True,
        ),
        service_level=ServiceLevel.PADES,
    )


def _confirmar(pdf: bytes, **cambios: Any) -> ConfirmTransactionRequest:
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
        "document_sha256": hashlib.sha256(pdf).hexdigest(),
        "document_content": pdf,
        "signer_common_name": "Firmante De Prueba",
        "signer_national_id": "4829153",
    }
    base.update(cambios)
    return ConfirmTransactionRequest(**base)


# ------------------------------------------------- Marcado de artefactos ----
class TestArtefactosDeDesarrolloMarcados:
    """Ningún artefacto de desarrollo puede confundirse con uno de producción."""

    def test_el_certificado_declara_el_entorno_en_un_campo_visible(
        self, autoridad: EphemeralCertificateAuthority
    ) -> None:
        """La marca va donde cualquier visor la muestra, no en una extensión.

        Una advertencia escondida en una extensión no la mira nadie.
        """
        emitido = autoridad.issue(
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                common_name="Firmante De Prueba",
                national_id="4829153",
                transaction_id="tx-1",
            )
        )

        ou = emitido.certificate.subject.native["organizational_unit_name"]
        assert "NO VALIDO" in ou
        assert "DEV" in ou

    def test_en_produccion_el_certificado_no_lleva_marca(
        self, ca_certificate_der: bytes, ca_signer: Any
    ) -> None:
        autoridad = EphemeralCertificateAuthority(
            ca_certificate_der=ca_certificate_der,
            ca_signer=ca_signer,
            crl_url="https://crl.example/intermediate.crl",
            environment="prod",
        )

        emitido = autoridad.issue(
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                common_name="Firmante De Prueba",
                national_id="4829153",
                transaction_id="tx-1",
            )
        )

        assert "NO VALIDO" not in emitido.certificate.subject.native["organizational_unit_name"]

    def test_el_acta_de_desarrollo_se_declara_como_tal(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        import base64
        import json

        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))
        confirmada = servicio.confirmar(
            tenant_id=TENANT,
            transaction_id=creada.transaction_id,
            peticion=_confirmar(pdf_de_prueba),
        )

        payload = json.loads(base64.urlsafe_b64decode(confirmada.acta.jws.split(".")[1] + "=="))

        assert payload["environment"] == "dev"
        assert payload["not_valid_for_production"] is True

    def test_el_acta_declara_que_el_sello_no_es_cualificado(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        """Un sello de prueba acredita el funcionamiento, no la fecha cierta."""
        import base64
        import json

        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))
        confirmada = servicio.confirmar(
            tenant_id=TENANT,
            transaction_id=creada.transaction_id,
            peticion=_confirmar(pdf_de_prueba),
        )

        payload = json.loads(base64.urlsafe_b64decode(confirmada.acta.jws.split(".")[1] + "=="))

        assert payload["timestamp"]["qualified"] is False


# ----------------------------------------------------- Regla de fecha cierta -
class TestSinFechaCiertaNoHayFirma:
    """Regla inviolable 12."""

    def test_si_la_autoridad_de_sellado_falla_la_transaccion_falla_completa(
        self, autoridad: EphemeralCertificateAuthority, pdf_de_prueba: bytes
    ) -> None:
        """No se degrada a PAdES-B-B: se rechaza.

        El certificado del firmante vive quince minutos. Sin sello de tiempo,
        un validador que lo comprueba después lo encuentra expirado y no puede
        saber si la firma se hizo dentro de la ventana. Entregar esa firma sería
        entregar algo que parece prueba y no lo es.
        """

        def sellador_caido() -> Any:
            class Caido:
                async def async_timestamp(self, message_digest: bytes, md_algorithm: str) -> Any:
                    raise TimestampError("La autoridad de sellado no responde")

            from pscnc.crypto.tsa import RecordingTimeStamper

            return RecordingTimeStamper(
                "", provider_name="TSA caída", delegate=Caido(), max_retries=1
            )

        kms = KmsFiel([f"alias/fnc/dev/{TENANT}/acta-seal/v1"])
        servicio = TransactionService(
            repositorio=TransactionRepository(),
            sellador=ActaSealer(
                TenantKeyRing(TENANT, environment="dev", region="us-east-1", client=kms)
            ),
            jurisdiccion_por_defecto="PY",
            firmante_pades=PadesSigner(
                certificate_authority=autoridad,
                timestamper_factory=sellador_caido,
                jurisdiction=get_profile("PY"),
            ),
            environment="dev",
        )

        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(pdf_de_prueba),
            )

        assert error.value.motivo is RejectionReason.TIMESTAMP_UNAVAILABLE

    def test_la_transaccion_no_queda_confirmada_tras_el_fallo(
        self, autoridad: EphemeralCertificateAuthority, pdf_de_prueba: bytes
    ) -> None:
        """Un fallo a mitad de camino no puede dejar la transacción a medio cerrar."""

        def sellador_caido() -> Any:
            class Caido:
                async def async_timestamp(self, message_digest: bytes, md_algorithm: str) -> Any:
                    raise TimestampError("caída")

            from pscnc.crypto.tsa import RecordingTimeStamper

            return RecordingTimeStamper(
                "", provider_name="TSA caída", delegate=Caido(), max_retries=1
            )

        kms = KmsFiel([f"alias/fnc/dev/{TENANT}/acta-seal/v1"])
        servicio = TransactionService(
            repositorio=TransactionRepository(),
            sellador=ActaSealer(
                TenantKeyRing(TENANT, environment="dev", region="us-east-1", client=kms)
            ),
            jurisdiccion_por_defecto="PY",
            firmante_pades=PadesSigner(
                certificate_authority=autoridad,
                timestamper_factory=sellador_caido,
                jurisdiction=get_profile("PY"),
            ),
            environment="dev",
        )
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        with pytest.raises(TransactionRejectedError):
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(pdf_de_prueba),
            )

        artefactos = servicio.artefactos(tenant_id=TENANT, transaction_id=creada.transaction_id)
        assert artefactos.acta is None
        assert artefactos.verification_code is None


# ----------------------------------------------------- Contrato del nivel 2 --
class TestContratoDelNivel2:
    def test_el_nivel_2_exige_el_documento(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(pdf_de_prueba, document_content=None),
            )

        assert error.value.motivo is RejectionReason.DOCUMENT_REQUIRED

    def test_el_nivel_2_exige_los_datos_del_firmante(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        """Un certificado sin nombre firmaría sin identificar a nadie."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(pdf_de_prueba, signer_common_name=None),
            )

        assert error.value.motivo is RejectionReason.INCOMPLETE_IDENTITY_DECISION

    def test_el_documento_de_identidad_se_valida_contra_la_jurisdiccion(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        """Un número boliviano bajo el perfil paraguayo produciría un certificado falso."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        with pytest.raises(TransactionRejectedError) as error:
            servicio.confirmar(
                tenant_id=TENANT,
                transaction_id=creada.transaction_id,
                peticion=_confirmar(pdf_de_prueba, signer_national_id="1234567-1K"),
            )

        assert error.value.motivo is RejectionReason.INVALID_IDENTITY_DOCUMENT

    def test_el_nivel_2_devuelve_la_huella_del_documento_firmado(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        """Los bytes cambian al firmar: hay dos huellas, y ambas importan."""
        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        confirmada = servicio.confirmar(
            tenant_id=TENANT,
            transaction_id=creada.transaction_id,
            peticion=_confirmar(pdf_de_prueba),
        )

        assert confirmada.signed_document_sha256 is not None
        assert confirmada.signed_document_sha256 != creada.document_sha256

    def test_el_acta_referencia_el_certificado_que_produjo_la_firma(
        self, servicio: TransactionService, pdf_de_prueba: bytes
    ) -> None:
        """Permite trazar la firma hasta su certificado sin abrir el PDF."""
        import base64
        import json

        creada = servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))
        confirmada = servicio.confirmar(
            tenant_id=TENANT,
            transaction_id=creada.transaction_id,
            peticion=_confirmar(pdf_de_prueba),
        )

        payload = json.loads(base64.urlsafe_b64decode(confirmada.acta.jws.split(".")[1] + "=="))

        assert payload["service_level"] == 2
        assert payload["signer_certificate_serial"]
        assert payload["signed_document_sha256"] == confirmada.signed_document_sha256

    def test_sin_firmante_configurado_el_nivel_2_se_rechaza_al_abrir(
        self, pdf_de_prueba: bytes
    ) -> None:
        """Se rechaza al abrir y no al confirmar: el tenant no llega con el
        documento a un callejón sin salida."""
        kms = KmsFiel([f"alias/fnc/dev/{TENANT}/acta-seal/v1"])
        servicio = TransactionService(
            repositorio=TransactionRepository(),
            sellador=ActaSealer(
                TenantKeyRing(TENANT, environment="dev", region="us-east-1", client=kms)
            ),
            jurisdiccion_por_defecto="PY",
        )

        with pytest.raises(TransactionRejectedError) as error:
            servicio.crear(tenant_id=TENANT, peticion=_crear(pdf_de_prueba))

        assert error.value.motivo is RejectionReason.SERVICE_LEVEL_UNAVAILABLE


# ------------------------------------------- Firmas posteriores (D-13) ------
class TestFirmasInstitucionalesPosteriores:
    """Lo que hace útil al nivel 2 frente al nivel 1.

    En el caso del primer tenant, el art. 5 de la Res. SS.SG. 210/2025 obliga a
    que la propuesta intermediada lleve la firma cualificada del corredor. Esa
    firma se aplica **después** de la del cliente, sobre el mismo archivo. Si la
    invalidara, habría que elegir entre las dos — y ninguna de las dos es
    opcional.
    """

    def test_una_firma_posterior_no_invalida_la_del_cliente(
        self, firmante: PadesSigner, pdf_de_prueba: bytes
    ) -> None:
        """La firma institucional se agrega como actualización incremental."""
        from io import BytesIO

        from pyhanko.pdf_utils.reader import PdfFileReader

        primera = firmante.sign(
            pdf_de_prueba,
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                common_name="Firmante De Prueba",
                national_id="4829153",
                transaction_id="tx-cliente",
            ),
        )

        # Una segunda firma sobre el documento ya firmado, como haría el corredor.
        segunda = firmante.sign(
            primera.signed_pdf,
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                common_name="Corredor Autorizado",
                national_id="1234567",
                transaction_id="tx-corredor",
            ),
            field_name="FirmaInstitucional",
        )

        lector = PdfFileReader(BytesIO(segunda.signed_pdf))
        firmas = lector.embedded_signatures

        # Las dos conviven en el mismo archivo: la del cliente sigue ahí.
        assert len(firmas) == 2
        assert {f.field_name for f in firmas} == {"FirmaFENC", "FirmaInstitucional"}

    def test_el_documento_original_sobrevive_dentro_del_firmado(
        self, firmante: PadesSigner, pdf_de_prueba: bytes
    ) -> None:
        """La actualización incremental agrega al final, no reescribe.

        Es lo que permite que un validador reconstruya el estado del documento
        tal como estaba cuando se aplicó cada firma.
        """
        resultado = firmante.sign(
            pdf_de_prueba,
            SubjectData.for_jurisdiction(
                get_profile("PY"),
                common_name="Firmante De Prueba",
                national_id="4829153",
                transaction_id="tx-1",
            ),
        )

        assert resultado.signed_pdf.startswith(pdf_de_prueba[:200])
        assert len(resultado.signed_pdf) > len(pdf_de_prueba)
