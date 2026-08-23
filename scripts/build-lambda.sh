#!/usr/bin/env bash
#
# Empaqueta la función de publicación de CRL para AWS Lambda (arm64, py3.12).
# Genera dist/crl_publisher.zip, ruta esperada por el módulo crl-distribution.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/dist/lambda-build"
OUT_ZIP="${ROOT}/dist/crl_publisher.zip"

rm -rf "$BUILD_DIR" "$OUT_ZIP"
mkdir -p "$BUILD_DIR"

echo "Instalando dependencias para linux/arm64..."
pip install \
  --target "$BUILD_DIR" \
  --platform manylinux2014_aarch64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade \
  "${ROOT}/services"

echo "Empaquetando..."
( cd "$BUILD_DIR" && zip -qr "$OUT_ZIP" . -x '*.pyc' '*/__pycache__/*' )

echo "Artefacto generado: ${OUT_ZIP} ($(du -h "$OUT_ZIP" | cut -f1))"
