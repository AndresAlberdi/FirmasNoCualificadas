# syntax=docker/dockerfile:1.7
###############################################################################
# Imagen del servicio de firma. Construcción en dos etapas, ejecución sin root
# y sistema de archivos raíz de solo lectura (impuesto por la definición de la
# tarea de ECS).
###############################################################################

FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Usuario sin privilegios: la tarea nunca corre como root.
RUN groupadd --gid 10001 pscnc \
    && useradd --uid 10001 --gid pscnc --no-create-home --shell /usr/sbin/nologin pscnc

COPY --from=builder /opt/venv /opt/venv

# Certificado de la CA intermedia (público). La clave privada nunca se copia:
# reside exclusivamente en AWS KMS.
COPY --chown=pscnc:pscnc deploy/ca-intermediate.crt /etc/pscnc/ca-intermediate.crt

USER pscnc
WORKDIR /srv
EXPOSE 8080

# tmpfs para los archivos temporales, ya que el raíz es de solo lectura.
ENV TMPDIR=/tmp

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

CMD ["uvicorn", "pscnc.orchestrator.app:app", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
