"""Emisión de certificados X.509 v3 efímeros para el firmante (ADR-0004).

Flujo por transacción:

1. Se genera un par de claves RSA-2048 en memoria del contenedor.
2. Se construye el ``TBSCertificate`` con el perfil de certificado que exige la
   jurisdicción activa (país del sujeto y formato del ``serialNumber``).
3. Se calcula su digest SHA-256 y se firma con la CA intermedia residente en KMS.
4. Tras producir el bloque CMS, la clave privada se descarta.

La construcción se realiza con ``asn1crypto`` y no con ``cryptography`` porque la
firma es externa: ``x509.CertificateBuilder.sign()`` exige un objeto de clave
privada local, que aquí no existe por diseño.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from asn1crypto import algos, keys, x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from jurisdictions import JurisdictionProfile
from pscnc.crypto.ca_signer import ALGORITMOS_SOPORTADOS, CaSigner, sha256_digest
from pscnc.errors import SigningError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)

# OID de firma de documentos (Microsoft Document Signing), reconocido por los
# lectores de PDF más difundidos.
OID_DOCUMENT_SIGNING = "1.3.6.1.4.1.311.10.3.12"

TAMANIO_CLAVE_FIRMANTE = 2048


@dataclass(frozen=True, slots=True)
class SubjectData:
    """Datos del firmante que se vuelcan al sujeto del certificado.

    El país y el prefijo del ``serialNumber`` no tienen valor por defecto a
    propósito: se toman del perfil de la jurisdicción (ADR-0008). Un certificado
    que dijera ``C=PY`` y ``serialNumber=PY-…`` sobre un firmante de otro país
    validaría criptográficamente y mentiría sobre la identidad del titular, que es
    exactamente lo que no puede pasar en un documento probatorio.
    """

    common_name: str
    national_id: str
    country: str
    #: Sigla del tipo de documento presentado (``CI``, ``PAS``…), no el país.
    serial_prefix: str
    #: Valor literal del atributo ``O``, fijado por el perfil de certificado.
    organization: str
    #: Valor literal del atributo ``OU``, fijado por el perfil de certificado.
    organizational_unit: str
    transaction_id: str = ""
    email: str | None = None

    @classmethod
    def for_jurisdiction(
        cls,
        profile: JurisdictionProfile,
        *,
        common_name: str,
        national_id: str,
        document_type: str | None = None,
        transaction_id: str = "",
        email: str | None = None,
    ) -> SubjectData:
        """Construye el sujeto con los valores que fija el perfil de la jurisdicción.

        ``document_type`` determina la sigla del ``serialNumber``. Si el inquilino
        no lo declara se asume el documento principal de la jurisdicción, y la
        suposición queda registrada acá y no escondida: un certificado que dijera
        «cédula» sobre el número de un pasaporte afirmaría un documento que el
        titular no presentó.
        """
        tipo = document_type or profile.default_document_type.code
        return cls(
            common_name=common_name,
            national_id=national_id,
            country=profile.certificate_country,
            serial_prefix=profile.document_type(tipo).certificate_prefix,
            organization=profile.certificate_subject_organization,
            organizational_unit=profile.certificate_subject_organizational_unit,
            transaction_id=transaction_id,
            email=email,
        )

    @property
    def serial_number(self) -> str:
        return f"{self.serial_prefix}{self.national_id}"


@dataclass(frozen=True, slots=True)
class IssuedCertificate:
    """Certificado efímero emitido junto con su clave privada en memoria."""

    certificate: x509.Certificate
    private_key_info: keys.PrivateKeyInfo
    private_key_pem: bytes
    serial_number: str

    @property
    def certificate_der(self) -> bytes:
        return bytes(self.certificate.dump())

    @property
    def certificate_pem(self) -> str:
        import base64

        cuerpo = base64.b64encode(self.certificate_der).decode("ascii")
        lineas = [cuerpo[i : i + 64] for i in range(0, len(cuerpo), 64)]
        return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lineas) + "\n-----END CERTIFICATE-----\n"


class EphemeralCertificateAuthority:
    """Emisor de certificados de firmante de un solo uso."""

    def __init__(
        self,
        *,
        ca_certificate_der: bytes,
        ca_signer: CaSigner,
        crl_url: str,
        policy_oid: str | None = None,
        backdate_minutes: int = 5,
        validity_minutes: int = 15,
        environment: str = "prod",
    ) -> None:
        self._ca_cert = x509.Certificate.load(ca_certificate_der)
        self._ca_signer = ca_signer
        self._crl_url = crl_url
        self._policy_oid = policy_oid or None
        self._backdate = timedelta(minutes=backdate_minutes)
        self._validity = timedelta(minutes=validity_minutes)
        self._environment = environment

        if self._ca_cert.ca is False:
            raise SigningError(
                "El certificado configurado como CA intermedia no tiene basicConstraints CA:TRUE"
            )

    # ------------------------------------------------------------------ API --
    @property
    def ca_certificate(self) -> x509.Certificate:
        return self._ca_cert

    @property
    def is_production(self) -> bool:
        return self._environment == "prod"

    @property
    def environment(self) -> str:
        return self._environment

    @property
    def ca_serial_number(self) -> str:
        return str(self._ca_cert.serial_number)

    def issue(self, subject: SubjectData, *, now: datetime | None = None) -> IssuedCertificate:
        """Emite un certificado efímero para el firmante indicado."""
        instante = now or datetime.now(UTC)
        clave_privada = rsa.generate_private_key(
            public_exponent=65537, key_size=TAMANIO_CLAVE_FIRMANTE
        )

        spki_der = clave_privada.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        public_key_info = keys.PublicKeyInfo.load(spki_der)

        serial = secrets.randbits(159) + 1  # positivo y < 20 octetos, conforme a RFC 5280
        tbs = self._build_tbs(subject, public_key_info, serial, instante)

        firma = self._ca_signer.sign_digest(sha256_digest(tbs.dump()))
        certificado = x509.Certificate(
            {
                "tbs_certificate": tbs,
                "signature_algorithm": self._signature_algorithm(),
                "signature_value": firma,
            }
        )

        pkcs8_der = clave_privada.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pem = clave_privada.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        logger.info(
            "ephemeral_certificate_issued",
            serial_number=format(serial, "x"),
            transaction_id=subject.transaction_id,
            validity_minutes=int(self._validity.total_seconds() // 60),
        )

        return IssuedCertificate(
            certificate=certificado,
            private_key_info=keys.PrivateKeyInfo.load(pkcs8_der),
            private_key_pem=pem,
            serial_number=format(serial, "x"),
        )

    # -------------------------------------------------------------- Interno --
    def _organizational_unit(self, subject: SubjectData) -> str:
        """Unidad organizativa del sujeto.

        **En producción vale exactamente lo que fija el perfil de certificado de la
        jurisdicción**, sin agregados: el campo no admite texto libre.

        Fuera de producción se antepone la marca de entorno. El campo se eligió
        porque **cualquier visor lo muestra sin desplegar extensiones**, incluido
        Adobe Reader: un artefacto de desarrollo, firmado con una CA autofirmada y
        una TSA de prueba, no puede poder confundirse con uno real, y una marca
        escondida en una extensión no lo impide — nadie la mira.

        Apartarse ahí del perfil no es un incumplimiento: en desarrollo no somos un
        prestador comunicado ante el organismo y el certificado no pretende ser
        oponible, de modo que la desviación **es** la señal de que el artefacto no
        sirve como prueba. Lo que no puede pasar es que ambos entornos emitan el
        mismo sujeto.

        El identificador de transacción viajaba acá y ya no cabe en producción. El
        vínculo entre certificado y transacción no se pierde: el acta sellada
        registra el número de serie del certificado. Dónde se reubica el
        identificador es una decisión abierta (P-03 en `docs/PENDIENTES.md`).
        """
        if self.is_production:
            return subject.organizational_unit
        marca = f"[NO VALIDO - ENTORNO {self._environment.upper()}]"
        if subject.transaction_id:
            return f"{marca} {subject.organizational_unit} - TX {subject.transaction_id}"
        return f"{marca} {subject.organizational_unit}"

    def _signature_algorithm(self) -> algos.SignedDigestAlgorithm:
        nombre = ALGORITMOS_SOPORTADOS[self._ca_signer.signing_algorithm]
        if nombre == "rsassa_pss":
            return algos.SignedDigestAlgorithm(
                {
                    "algorithm": "rsassa_pss",
                    "parameters": algos.RSASSAPSSParams(
                        {
                            "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                            "mask_gen_algorithm": algos.MaskGenAlgorithm(
                                {
                                    "algorithm": "mgf1",
                                    "parameters": algos.DigestAlgorithm({"algorithm": "sha256"}),
                                }
                            ),
                            "salt_length": 32,
                            "trailer_field": "trailer_field_bc",
                        }
                    ),
                }
            )
        return algos.SignedDigestAlgorithm({"algorithm": nombre})

    def _build_tbs(
        self,
        subject: SubjectData,
        public_key_info: keys.PublicKeyInfo,
        serial: int,
        instante: datetime,
    ) -> x509.TbsCertificate:
        not_before = instante - self._backdate
        not_after = instante + self._validity

        nombre_sujeto = x509.Name.build(
            {
                "country_name": subject.country,
                "organization_name": subject.organization,
                "common_name": subject.common_name,
                "serial_number": subject.serial_number,
                "organizational_unit_name": self._organizational_unit(subject),
            }
        )

        return x509.TbsCertificate(
            {
                "version": "v3",
                "serial_number": serial,
                "signature": self._signature_algorithm(),
                "issuer": self._ca_cert.subject,
                "validity": x509.Validity(
                    {
                        "not_before": x509.Time({"utc_time": not_before}),
                        "not_after": x509.Time({"utc_time": not_after}),
                    }
                ),
                "subject": nombre_sujeto,
                "subject_public_key_info": public_key_info,
                "extensions": self._build_extensions(subject, public_key_info),
            }
        )

    def _build_extensions(
        self, subject: SubjectData, public_key_info: keys.PublicKeyInfo
    ) -> list[x509.Extension]:
        extensiones: list[x509.Extension] = [
            x509.Extension(
                {
                    "extn_id": "basic_constraints",
                    "critical": True,
                    "extn_value": x509.BasicConstraints({"ca": False}),
                }
            ),
            x509.Extension(
                {
                    "extn_id": "key_usage",
                    "critical": True,
                    # No repudio: el certificado solo sirve para firmar, nunca para cifrar.
                    "extn_value": x509.KeyUsage({"digital_signature", "non_repudiation"}),
                }
            ),
            x509.Extension(
                {
                    "extn_id": "extended_key_usage",
                    "critical": False,
                    "extn_value": x509.ExtKeyUsageSyntax(
                        ["email_protection", OID_DOCUMENT_SIGNING]
                    ),
                }
            ),
            x509.Extension(
                {
                    "extn_id": "key_identifier",
                    "critical": False,
                    "extn_value": public_key_info.sha1,
                }
            ),
            x509.Extension(
                {
                    "extn_id": "authority_key_identifier",
                    "critical": False,
                    "extn_value": x509.AuthorityKeyIdentifier(
                        {"key_identifier": self._ca_key_identifier()}
                    ),
                }
            ),
        ]

        if self._crl_url:
            extensiones.append(
                x509.Extension(
                    {
                        "extn_id": "crl_distribution_points",
                        "critical": False,
                        "extn_value": x509.CRLDistributionPoints(
                            [
                                x509.DistributionPoint(
                                    {
                                        "distribution_point": x509.DistributionPointName(
                                            name="full_name",
                                            value=x509.GeneralNames(
                                                [
                                                    x509.GeneralName(
                                                        name="uniform_resource_identifier",
                                                        value=self._crl_url,
                                                    )
                                                ]
                                            ),
                                        )
                                    }
                                )
                            ]
                        ),
                    }
                )
            )

        if self._policy_oid:
            extensiones.append(
                x509.Extension(
                    {
                        "extn_id": "certificate_policies",
                        "critical": False,
                        "extn_value": x509.CertificatePolicies(
                            [x509.PolicyInformation({"policy_identifier": self._policy_oid})]
                        ),
                    }
                )
            )

        if subject.email:
            extensiones.append(
                x509.Extension(
                    {
                        "extn_id": "subject_alt_name",
                        "critical": False,
                        "extn_value": x509.GeneralNames(
                            [x509.GeneralName(name="rfc822_name", value=subject.email)]
                        ),
                    }
                )
            )

        return extensiones

    def _ca_key_identifier(self) -> bytes:
        identificador = self._ca_cert.key_identifier
        if identificador:
            return bytes(identificador)
        return bytes(self._ca_cert.public_key.sha1)
