"""Configuración leída del fichero .env y de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
RUTA_ENV = RAIZ / ".env"


def cargar_env(ruta: Path = RUTA_ENV) -> None:
    """Carga KEY=VALOR desde .env sin pisar variables ya definidas."""
    if not ruta.exists():
        return

    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave.strip(), valor)


def _entero(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


@dataclass(frozen=True)
class Config:
    telegram_token: str
    telegram_chat_id: str
    intervalo_segundos: int
    hora_inicio: int
    hora_fin: int
    reaviso_minutos: int
    minutos_para_aviso_fallo: int
    comprobaciones_para_aviso_dudoso: int


def leer_config() -> Config:
    cargar_env()
    return Config(
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        intervalo_segundos=max(30, _entero("INTERVALO_SEGUNDOS", 120)),
        hora_inicio=_entero("HORA_INICIO", 7),
        hora_fin=_entero("HORA_FIN", 23),
        reaviso_minutos=_entero("REAVISO_MINUTOS", 10),
        minutos_para_aviso_fallo=_entero("MINUTOS_PARA_AVISO_FALLO", 30),
        comprobaciones_para_aviso_dudoso=_entero(
            "COMPROBACIONES_PARA_AVISO_DUDOSO", 3
        ),
    )
