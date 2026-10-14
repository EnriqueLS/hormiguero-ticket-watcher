"""Envío de mensajes de Telegram."""

from __future__ import annotations

import logging
import time
from html import escape

import requests

from config import Config


URL_API = "https://api.telegram.org/bot{token}/sendMessage"
log = logging.getLogger(__name__)


def enviar_mensaje(config: Config, mensaje: str) -> bool:
    if not config.telegram_token or not config.telegram_chat_id:
        log.error("Telegram no configurado: revisa TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env")
        return False

    for intento in range(3):
        try:
            respuesta = requests.post(
                URL_API.format(token=config.telegram_token),
                data={
                    "chat_id": config.telegram_chat_id,
                    "text": mensaje,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
                timeout=20,
            )
            if respuesta.ok and respuesta.json().get("ok"):
                return True
            log.error("Telegram respondió %s: %s", respuesta.status_code, respuesta.text[:300])
        except (requests.RequestException, ValueError) as error:
            log.error("Error enviando Telegram: %s", error)
        time.sleep(3 * (intento + 1))

    return False


def enviar_alerta(config: Config, evento) -> bool:
    mensaje = (
        "🚨🚨🚨 <b>ENTRADAS DISPONIBLES — EL HORMIGUERO</b>\n\n"
        f"📅 {escape(evento.texto or 'Fecha no identificada')}\n"
        "🎟️ Formulario abierto y sin mensaje de «sin plazas»\n\n"
        f"🔗 {escape(evento.url)}\n\n"
        "⚡ <b>¡SOLICITA LAS ENTRADAS AHORA!</b>"
    )

    resultado = True
    for numero in range(3):
        if numero:
            time.sleep(3)
        resultado = enviar_mensaje(config, mensaje) and resultado
    return resultado


def enviar_aviso(config: Config, texto: str) -> bool:
    """Mensaje informativo (fallos, recuperación, arranque). Admite HTML."""
    return enviar_mensaje(config, texto)
