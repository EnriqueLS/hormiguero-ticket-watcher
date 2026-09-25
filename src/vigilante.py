"""Bucle principal de vigilancia."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "src")

from estado import ahora_iso, cargar_estado, guardar_estado
from rascador import EstadoDisponibilidad, consultar_eventos
from telegram import enviar_alerta


INTERVALO_COMPROBACION_SEGUNDOS = 55
DURACION_CICLO_SEGUNDOS = 4 * 60
INTERVALO_REAVISO_MINUTOS = 10


def fecha_desde_iso(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(valor)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha
    except ValueError:
        return None


def debe_alertar(registro: dict) -> bool:
    ultima_alerta = fecha_desde_iso(registro.get("ultima_alerta"))
    if ultima_alerta is None:
        return True

    return datetime.now(timezone.utc) - ultima_alerta >= timedelta(
        minutes=INTERVALO_REAVISO_MINUTOS
    )


def procesar_eventos(estado: dict) -> None:
    eventos = consultar_eventos()
    eventos_actuales = {evento.identificador for evento in eventos}

    for evento in eventos:
        registro = estado["eventos"].setdefault(evento.identificador, {})

        if evento.estado != EstadoDisponibilidad.DISPONIBLE:
            continue

        if debe_alertar(registro):
            print(f"Disponibilidad confirmada: {evento.identificador}")
            if enviar_alerta(evento):
                registro["ultima_alerta"] = ahora_iso()

    # Solo conservamos el último aviso de los eventos que siguen
    # publicados actualmente en la web principal.
    estado["eventos"] = {
        identificador: registro
        for identificador, registro in estado["eventos"].items()
        if identificador in eventos_actuales
    }


def ejecutar() -> None:
    estado = cargar_estado()
    inicio = time.monotonic()

    while time.monotonic() - inicio < DURACION_CICLO_SEGUNDOS:
        try:
            procesar_eventos(estado)
            guardar_estado(estado)
        except Exception as error:
            print(f"Error durante la comprobación: {error}")

        restante = DURACION_CICLO_SEGUNDOS - (time.monotonic() - inicio)
        if restante <= 0:
            break
        time.sleep(min(INTERVALO_COMPROBACION_SEGUNDOS, restante))

    guardar_estado(estado)


if __name__ == "__main__":
    ejecutar()
