#!/usr/bin/env python3
"""Exporta a Terraform los datos de una jurisdicción que la infraestructura necesita.

Terraform no puede leer el módulo `jurisdictions`, y duplicar en HCL el plazo de
conservación sería tener dos fuentes de verdad para un dato con consecuencia
legal: si divergieran, la infraestructura conservaría la evidencia menos tiempo
del que la constancia le promete al firmante. Este script cierra esa brecha
generando un `.auto.tfvars.json` a partir del perfil.

Uso:

    python scripts/exportar-jurisdiccion.py PY infra/terraform/envs/dev

El archivo generado se versiona: forma parte de la evidencia de control de
cambios que una auditoría puede revisar en el historial (ADR-0002).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "services" / "src"))

from jurisdictions import get_profile  # noqa: E402

NOMBRE_ARCHIVO = "jurisdiccion.auto.tfvars"


def exportar(codigo: str, destino: Path) -> Path:
    perfil = get_profile(codigo)

    def hcl(valor: object) -> str:
        if isinstance(valor, bool):
            return "true" if valor else "false"
        if isinstance(valor, int):
            return str(valor)
        return json.dumps(str(valor), ensure_ascii=False)

    campos = (
        ("jurisdiction_code", perfil.code),
        ("jurisdiction_name", perfil.name),
        # El mínimo que la infraestructura no puede incumplir. En modo COMPLIANCE
        # la retención de S3 Object Lock es irreversible, así que un valor menor
        # no se corrige: se hereda durante todo el plazo.
        ("jurisdiction_minimum_retention_days", perfil.retention.minimum_days),
        ("jurisdiction_retention_legal_basis", perfil.retention.legal_basis),
        (
            "jurisdiction_incident_notification_hours",
            perfil.regulator.incident_notification_hours,
        ),
        ("jurisdiction_legally_validated", perfil.legally_validated),
    )

    ancho = max(len(nombre) for nombre, _ in campos)
    lineas = [f"{nombre.ljust(ancho)} = {hcl(valor)}" for nombre, valor in campos]

    archivo = destino / NOMBRE_ARCHIVO
    archivo.write_text(
        "# Generado por scripts/exportar-jurisdiccion.py — NO editar a mano.\n"
        "# Fuente: services/src/jurisdictions/. Regenerar con `make tf-jurisdiccion`.\n"
        f"# Jurisdicción: {perfil.code} ({perfil.name})\n"
        f"# Conservación mínima: {perfil.retention.minimum_days} días desde "
        f"{perfil.retention.counted_from} ({perfil.retention.legal_basis}).\n\n"
        + "\n".join(lineas)
        + "\n",
        encoding="utf-8",
    )
    return archivo


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    codigo, destino = sys.argv[1], Path(sys.argv[2])
    if not destino.is_dir():
        print(f"El destino no existe o no es un directorio: {destino}", file=sys.stderr)
        return 2

    archivo = exportar(codigo, destino)
    print(f"Escrito {archivo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
