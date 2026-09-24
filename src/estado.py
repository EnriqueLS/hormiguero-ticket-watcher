"""Persistencia del estado y del histórico del vigilante."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUTA_ESTADO = Path("datos/estado.json")
RUTA_HISTORIAL = Path("datos/historial.csv")


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cargar_estado() -> dict[str, Any]:
    if not RUTA_ESTADO.exists():
        return {"eventos": {}}

    try:
        datos = json.loads(RUTA_ESTADO.read_text(encoding="utf-8"))
        if isinstance(datos, dict) and isinstance(datos.get("eventos"), dict):
            return datos
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


def registrar_historico(fila: dict[str, Any]) -> None:
    RUTA_HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "timestamp", "identificador", "fecha", "hora",
        "invitado", "estado", "motivo",
    ]

    existe = RUTA_HISTORIAL.exists()
    with RUTA_HISTORIAL.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        if not existe:
            escritor.writeheader()
        escritor.writerow({campo: fila.get(campo, "") for campo in campos})
