# Servicios backend · PSCNC FENC-PY

Paquete Python único (`pscnc`) que agrupa el motor de firma, la API B2B, la capa de
evidencias y las tareas programadas. Se distribuye como una sola imagen porque los
componentes comparten el mismo dominio criptográfico y separarlos multiplicaría la
superficie de confianza sin beneficio operativo a esta escala.

## Estructura

| Paquete | Responsabilidad |
| :-- | :-- |
| `config` | Configuración validada al arranque; prohíbe el backend local fuera de desarrollo |
| `errors` | Errores del dominio con código HTTP e identificador estable |
| `logging_setup` | Logging estructurado con redacción automática de datos personales |
| `models` | Contratos Pydantic v2 de la pista de auditoría y de la API |
| `crypto.ca_signer` | Firmantes de la CA: `KmsCaSigner` (producción) y `LocalCaSigner` (desarrollo) |
| `crypto.ephemeral_ca` | Emisión de certificados X.509 efímeros conforme al perfil nacional |
| `crypto.tsa` | Cliente RFC 3161 con reintentos y retención del token para auditoría |
| `crypto.pades` | Firma PAdES-B-T incremental sobre pyHanko |
| `compliance.legal_guard` | Bloqueo de actos jurídicos excluidos y umbral biométrico |
| `repositories` | DynamoDB (auditoría) y S3 (documentos y expedientes) |
| `evidence.report` | Expediente forense en PDF |
| `onboarding.client` | Adaptador del módulo de onboarding existente |
| `orchestrator` | API FastAPI, autenticación HMAC y máquina de estados |
| `jobs.crl_publisher` | Generación y publicación de la CRL |

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -q
ruff check src tests && ruff format --check src tests
mypy src

PSCNC_ENVIRONMENT=sandbox PSCNC_CRYPTO_BACKEND=local \
  uvicorn pscnc.orchestrator.app:app --reload --port 8080 --app-dir src
```

### Material criptográfico para desarrollo

```bash
# Clave y certificado autofirmado que simulan la CA intermedia
openssl req -x509 -newkey rsa:4096 -keyout dev-ca.key -out dev-ca.crt \
  -days 365 -nodes -subj "/C=PY/O=PSCNC Desarrollo/CN=CA Intermedia FENC - DEV" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign,digitalSignature"

export PSCNC_LOCAL_CA_KEY_PATH=$PWD/dev-ca.key
export PSCNC_CA_CERT_PATH=$PWD/dev-ca.crt
```

Estos archivos están excluidos por `.gitignore` y no deben salir del equipo de
desarrollo. En `staging` y `prod` la configuración rechaza el backend local.

## Invariantes que las pruebas protegen

1. Un ítem de auditoría con claves incoherentes no se persiste.
2. Una sesión marcada como completada sin evidencia criptográfica o de
   consentimiento es inválida.
3. El código OTP nunca se almacena: solo su hash SHA-256.
4. Un certificado efímero no puede reutilizarse entre transacciones.
5. Una petición firmada para una ruta o un cuerpo distintos es rechazada.
6. Un contexto de un inquilino no puede acceder a datos de otro.

## Pendientes conocidos

* Pruebas de integración del flujo PAdES completo contra una TSA de pruebas.
* Nivel PAdES-B-LTA: recolección OCSP/CRL, diccionario `/DSS` y archive timestamp.
* Sello electrónico de persona jurídica sobre el expediente de evidencias.
