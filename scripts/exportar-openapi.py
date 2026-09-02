#!/usr/bin/env python3
"""Exporta el contrato público a `api/openapi.yaml`.

El archivo se genera y se versiona: un cambio en el contrato aparece como diff en
el pull request, que es donde un revisor puede notar que se rompió la
compatibilidad de un tenant. Regenerarlo es parte de cerrar una tarea que toque
la API (checklist de CLAUDE.md).

Uso:  python scripts/exportar-openapi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "services" / "src"))

import yaml  # noqa: E402

from pscnc.orchestrator.app import app  # noqa: E402

DESTINO = RAIZ / "api" / "openapi.yaml"


def main() -> int:
    esquema = app.openapi()

    # OpenAPI 3.1 es lo que FastAPI emite; se fija explícitamente para que el
    # generador del SDK no tenga que adivinarlo.
    esquema["openapi"] = "3.1.0"
    esquema["info"]["description"] = (
        "Contrato público de FirmasNoCualificadas.\n\n"
        "Reglas que un integrador debe conocer antes de programar:\n\n"
        "- La decisión de identidad llega **tomada por el tenant**; el servicio la "
        "asienta como evidencia y no la revisa.\n"
        "- El OTP verificado por el tenant viaja como prueba, nunca el código.\n"
        "- El modo predeterminado es *hash-only*: el documento no se envía.\n"
        "- Las escrituras exigen `Idempotency-Key`; una confirmación repetida "
        "devuelve el acta original.\n"
        "- Todo rechazo trae un `motivo` de un enumerado estable, nunca un mensaje "
        "libre."
    )

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        "# Generado por scripts/exportar-openapi.py — no editar a mano.\n"
        "# Regenerar con `make openapi` al cambiar el contrato.\n"
        + yaml.safe_dump(esquema, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(f"Escrito {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
