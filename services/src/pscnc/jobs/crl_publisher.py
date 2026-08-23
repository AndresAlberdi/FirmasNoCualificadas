"""Generación y publicación de la Lista de Revocación de Certificados (CRL).

Aunque los certificados de firmante son de un solo uso y de vigencia mínima, los
validadores de PDF exigen un punto de distribución de CRL alcanzable y **vigente**
para la CA intermedia. Una CRL cuyo ``nextUpdate`` haya vencido hace que Adobe
Acrobat marque la firma como no verificable, incluso si nada fue revocado.

Por eso la CRL se regenera todos los días aunque su contenido no cambie.

Uso como función Lambda (EventBridge diario) o desde la línea de comandos::

    python -m pscnc.jobs.crl_publisher
    python -m pscnc.jobs.crl_publisher --revoke-intermediate --reason key-compromise \\
        --invalidity-date 2026-08-23T04:00:00Z
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from asn1crypto import algos, core, crl, x509

from pscnc.crypto.ca_signer import ALGORITMOS_SOPORTADOS, CaSigner, KmsCaSigner, sha256_digest
from pscnc.logging_setup import configurar_logging, get_logger

logger = get_logger(__name__)

RAZONES_VALIDAS = {
    "unspecified",
    "key-compromise",
    "ca-compromise",
    "affiliation-changed",
    "superseded",
    "cessation-of-operation",
    "certificate-hold",
}


def _razon_asn1(razon: str) -> str:
    """Traduce la razón de la línea de comandos al nombre ASN.1 de asn1crypto."""
    return razon.replace("-", "_")


def build_crl(
    *,
    ca_certificate_der: bytes,
    ca_signer: CaSigner,
    crl_number: int,
    validity_hours: int = 72,
    revoked: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> bytes:
    """Construye y firma una CRL en formato DER.

    ``revoked`` acepta entradas ``{"serial": int, "date": datetime, "reason": str}``.
    """
    instante = now or datetime.now(UTC)
    ca_cert = x509.Certificate.load(ca_certificate_der)

    nombre_algoritmo = ALGORITMOS_SOPORTADOS[ca_signer.signing_algorithm]
    sda = algos.SignedDigestAlgorithm({"algorithm": nombre_algoritmo})

    entradas = []
    for entrada in revoked or []:
        extensiones = []
        razon = entrada.get("reason")
        if razon:
            extensiones.append(
                crl.CRLEntryExtension(
                    {
                        "extn_id": "crl_reason",
                        "critical": False,
                        "extn_value": crl.CRLReason(_razon_asn1(str(razon))),
                    }
                )
            )
        entradas.append(
            crl.RevokedCertificate(
                {
                    "user_certificate": int(entrada["serial"]),
                    "revocation_date": x509.Time({"utc_time": entrada.get("date") or instante}),
                    "crl_entry_extensions": crl.CRLEntryExtensions(extensiones),
                }
            )
        )

    extensiones_crl = crl.TBSCertListExtensions(
        [
            crl.TBSCertListExtension(
                {
                    "extn_id": "crl_number",
                    "critical": False,
                    "extn_value": core.Integer(crl_number),
                }
            ),
            crl.TBSCertListExtension(
                {
                    "extn_id": "authority_key_identifier",
                    "critical": False,
                    "extn_value": x509.AuthorityKeyIdentifier(
                        {"key_identifier": bytes(ca_cert.key_identifier or ca_cert.public_key.sha1)}
                    ),
                }
            ),
        ]
    )

    tbs = crl.TbsCertList(
        {
            "version": "v2",
            "signature": sda,
            "issuer": ca_cert.subject,
            "this_update": x509.Time({"utc_time": instante}),
            "next_update": x509.Time({"utc_time": instante + timedelta(hours=validity_hours)}),
            "revoked_certificates": crl.RevokedCertificates(entradas),
            "crl_extensions": extensiones_crl,
        }
    )

    firma = ca_signer.sign_digest(sha256_digest(tbs.dump()))
    lista = crl.CertificateList(
        {"tbs_cert_list": tbs, "signature_algorithm": sda, "signature": firma}
    )

    logger.info(
        "crl_built",
        crl_number=crl_number,
        revoked_entries=len(entradas),
        next_update_hours=validity_hours,
    )
    return lista.dump()


def publicar(contenido: bytes, *, bucket: str, key: str, distribution_id: str = "") -> None:
    """Sube la CRL a S3 e invalida la caché de CloudFront."""
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=contenido,
        ContentType="application/pkix-crl",
        CacheControl="max-age=300",
    )
    logger.info("crl_published", bucket=bucket, key=key, bytes=len(contenido))

    if distribution_id:
        cloudfront = boto3.client("cloudfront")
        cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": [f"/{key}"]},
                "CallerReference": f"crl-{datetime.now(UTC).timestamp()}",
            },
        )
        logger.info("crl_cache_invalidated", distribution_id=distribution_id)


def _siguiente_numero_crl(bucket: str, key: str) -> int:
    """Obtiene el número de CRL siguiente a partir del objeto publicado.

    El ``crlNumber`` debe ser estrictamente creciente: un retroceso invalida la
    confianza en la secuencia ante un validador estricto.
    """
    s3 = boto3.client("s3")
    try:
        actual = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        lista = crl.CertificateList.load(actual)
        numero = lista["tbs_cert_list"]["crl_extensions"]
        for extension in numero:
            if extension["extn_id"].native == "crl_number":
                return int(extension["extn_value"].parsed.native) + 1
    except Exception as exc:
        logger.warning("crl_number_reset", error=str(exc))
    return 1


def handler(event: dict[str, Any] | None = None, context: object | None = None) -> dict[str, Any]:
    """Punto de entrada para AWS Lambda."""
    configurar_logging()
    evento = event or {}

    bucket = os.environ["PSCNC_CRL_BUCKET"]
    key = os.environ.get("PSCNC_CRL_OBJECT_KEY", "pscnc/intermediate.crl")
    validity = int(os.environ.get("PSCNC_CRL_VALIDITY_HOURS", "72"))
    distribution = os.environ.get("PSCNC_CRL_DISTRIBUTION_ID", "")
    ca_cert_path = os.environ.get("PSCNC_CA_CERT_PATH", "/var/task/ca-intermediate.der")

    firmante = KmsCaSigner(
        os.environ["PSCNC_KMS_CA_KEY_ID"],
        region=os.environ.get("AWS_REGION", "us-east-1"),
        signing_algorithm=os.environ.get(
            "PSCNC_KMS_SIGNING_ALGORITHM", "RSASSA_PKCS1_V1_5_SHA_256"
        ),
    )

    with open(ca_cert_path, "rb") as archivo:
        ca_der = archivo.read()

    contenido = build_crl(
        ca_certificate_der=ca_der,
        ca_signer=firmante,
        crl_number=_siguiente_numero_crl(bucket, key),
        validity_hours=validity,
        revoked=evento.get("revoked", []),
    )
    publicar(contenido, bucket=bucket, key=key, distribution_id=distribution)

    return {"status": "published", "bytes": len(contenido), "key": key}


def main() -> None:
    """Ejecución manual, incluido el escenario de revocación de emergencia."""
    configurar_logging(json_output=False)
    parser = argparse.ArgumentParser(description="Publicación de la CRL del PSCNC")
    parser.add_argument("--revoke-intermediate", action="store_true")
    parser.add_argument("--reason", choices=sorted(RAZONES_VALIDAS), default="unspecified")
    parser.add_argument("--invalidity-date", help="Fecha ISO-8601 del compromiso")
    argumentos = parser.parse_args()

    revocados: list[dict[str, Any]] = []
    if argumentos.revoke_intermediate:
        ca_der = open(os.environ["PSCNC_CA_CERT_PATH"], "rb").read()  # noqa: SIM115
        ca_cert = x509.Certificate.load(ca_der)
        fecha = (
            datetime.fromisoformat(argumentos.invalidity_date.replace("Z", "+00:00"))
            if argumentos.invalidity_date
            else datetime.now(UTC)
        )
        revocados.append(
            {"serial": ca_cert.serial_number, "date": fecha, "reason": argumentos.reason}
        )
        logger.warning(
            "emergency_revocation_requested",
            serial=str(ca_cert.serial_number),
            reason=argumentos.reason,
        )

    resultado = handler({"revoked": revocados})
    print(resultado)


if __name__ == "__main__":
    main()
