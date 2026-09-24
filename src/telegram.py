"""Envío de alertas de Telegram."""

from __future__ import annotations

import os
from time import sleep

import requests


URL_API = "https://api.telegram.org/bot{token}/sendMessage"


def enviar_mensaje(mensaje: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram no configurado: faltan los secretos.")
        return False

    try:
        respuesta = requests.post(
            URL_API.format(token=token),
            data={
                "chat_id": chat_id,
                "text": mensaje,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
        return bool(datos.get("ok"))
    except (requests.RequestException, ValueError) as error:
        print(f"Error enviando Telegram: {error}")
        return False


def enviar_alerta(evento) -> bool:
    mensaje = (
        "🚨🚨🚨 <b>ENTRADAS DISPONIBLES — BOT EL HORMIGUERO</b> 🤖\n\n"
        f"📅 <b>Día:</b> {evento.fecha or 'No identificada'}\n"
        f"🕐 <b>Hora:</b> {evento.hora or 'No identificada'}\n"
        f"👤 <b>Invitado:</b> {evento.invitado or 'No identificado'}\n"
        "🎟️ <b>Estado:</b> DISPONIBLE\n\n"
        f"🔗 <b>ACCESO DIRECTO:</b>\n{evento.url}\n\n"
        "⚡ <b>¡SOLICITA LAS ENTRADAS AHORA!</b>"
    )

    resultado = True
    for numero in range(3):
        if numero:
            sleep(3)
        if not enviar_mensaje(mensaje):
            resultado = False

    return resultado
