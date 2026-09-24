"""Bucle principal de vigilancia."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "src")

from estado import ahora_iso, cargar_estado, guardar_estado, registrar_historico
from rascador import EstadoDisponibilidad, consultar_eventos
from telegram import enviar_alerta


INTERVALO_COMPROBACION_SEGUNDOS = 55
DURACION_CICLO_SEGUNDOS = 4 * 60
INTERVALO_REAVISO_MINUTOS = 15


def fecha_desde_iso(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def debe_alertar(registro: dict, estado_actual: EstadoDisponibilidad) -> bool:
    if estado_actual != EstadoDisponibilidad.DISPONIBLE:
        return False

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
        registro = estado["eventos"].setdefault(
            evento.identificador,
            {
                "estado_confirmado": None,
                "ultima_alerta": None,
                "ultima_comprobacion": None,
                "activo": True,
            },
        )

        estado_anterior = registro.get("estado_confirmado")
        estado_actual = evento.estado

        registro.update({
            "fecha": evento.fecha,
            "hora": evento.hora,
            "invitado": evento.invitado,
            "url": evento.url,
            "ultima_comprobacion": ahora_iso(),
            "activo": True,
        })

        if estado_actual == EstadoDisponibilidad.DESCONOCIDO:
            registrar_historico({
                "timestamp": ahora_iso(),
                "identificador": evento.identificador,
                "fecha": evento.fecha,
                "hora": evento.hora,
                "invitado": evento.invitado,
                "estado": estado_actual.value,
                "motivo": "No modifica el estado confirmado",
            })
            continue

        if debe_alertar(registro, estado_actual):
            print(f"Disponibilidad confirmada: {evento.identificador}")
            if enviar_alerta(evento):
                registro["ultima_alerta"] = ahora_iso()

        registro["estado_confirmado"] = estado_actual.value

        registrar_historico({
            "timestamp": ahora_iso(),
            "identificador": evento.identificador,
            "fecha": evento.fecha,
            "hora": evento.hora,
            "invitado": evento.invitado,
            "estado": estado_actual.value,
            "motivo": (
                "Cambio de estado"
                if estado_anterior != estado_actual.value
                else "Comprobación"
            ),
        })

    for identificador, registro in estado["eventos"].items():
        if identificador not in eventos_actuales:
            registro["activo"] = False


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
