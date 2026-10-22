"""Configuración local: lee el archivo .env de la raíz del proyecto.

No necesita dependencias extra. Las variables de entorno reales tienen
prioridad sobre las del archivo .env (así GitHub Actions sigue funcionando).
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_ENV = RAIZ / ".env"


def cargar_env(ruta: Path = RUTA_ENV) -> None:
    if not ruta.exists():
        return
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def entero(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, "").strip() or defecto)
    except ValueError:
        return defecto


def booleano(nombre: str, defecto: bool) -> bool:
    valor = os.getenv(nombre, "").strip().lower()
    if not valor:
        return defecto
    return valor in ("1", "si", "sí", "true", "yes", "on")


cargar_env()
