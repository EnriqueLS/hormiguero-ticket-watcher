"""Persistencia mínima del estado de alertas."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUTA_ESTADO = Path("datos/estado.json")


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cargar_estado() -> dict[str, Any]:
    if not RUTA_ESTADO.exists():
        return {"eventos": {}}

    try:
        datos = json.loads(RUTA_ESTADO.read_text(encoding="utf-8"))
        if isinstance(datos, dict) and isinstance(datos.get("eventos"), dict):
            # Solo necesitamos conservar la hora del último aviso por evento.
            eventos = {}
            for identificador, registro in datos["eventos"].items():
                if isinstance(registro, dict) and registro.get("ultima_alerta"):
                    eventos[str(identificador)] = {
                        "ultima_alerta": registro["ultima_alerta"]
                    }
            return {"eventos": eventos}
    except (OSError, json.JSONDecodeError):
        pass

    return {"eventos": {}}


def guardar_estado(estado: dict[str, Any]) -> None:
    RUTA_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    temporal = RUTA_ESTADO.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporal.replace(RUTA_ESTADO)
