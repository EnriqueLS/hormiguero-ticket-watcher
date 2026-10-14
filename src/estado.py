"""Persistencia mínima del estado del vigilante."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import RAIZ


RUTA_ESTADO = RAIZ / "datos" / "estado.json"
log = logging.getLogger(__name__)


def estado_vacio() -> dict[str, Any]:
    return {"eventos": {}, "fallo_desde": None, "aviso_fallo_enviado": False}


def cargar_estado(ruta: Path = RUTA_ESTADO) -> dict[str, Any]:
    estado = estado_vacio()
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return estado
    except (OSError, json.JSONDecodeError) as error:
        log.warning("Estado ilegible, se empieza de cero: %s", error)
        return estado

    if isinstance(datos, dict):
        if isinstance(datos.get("eventos"), dict):
            estado["eventos"] = {
                str(k): v for k, v in datos["eventos"].items() if isinstance(v, dict)
            }
        estado["fallo_desde"] = datos.get("fallo_desde")
        estado["aviso_fallo_enviado"] = bool(datos.get("aviso_fallo_enviado"))
    return estado


def guardar_estado(estado: dict[str, Any], ruta: Path = RUTA_ESTADO) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)
