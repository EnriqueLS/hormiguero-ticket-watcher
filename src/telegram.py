"""Envío de alertas de Telegram."""

from __future__ import annotations

import html
import json
import os
import sys
import threading
from pathlib import Path
from time import sleep

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402,F401  (carga .env)

REPETICIONES = config.entero("REPETICIONES_ALERTA", 3)


URL_API = "https://api.telegram.org/bot{token}/sendMessage"


def enviar_mensaje(mensaje: str, boton_url: str | None = None,
                   boton_texto: str = "🎟️ ABRIR FORMULARIO") -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram no configurado: faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en .env")
        return False

    try:
        datos = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        if boton_url:
            datos["reply_markup"] = json.dumps({"inline_keyboard": [
                [{"text": boton_texto, "url": boton_url}]
            ]})
        respuesta = requests.post(
            URL_API.format(token=token), data=datos, timeout=20,
        )
        respuesta.raise_for_status()
        return bool(respuesta.json().get("ok"))
    except (requests.RequestException, ValueError) as error:
        print(f"Error enviando Telegram: {error}")
        return False


def enviar_alerta(evento) -> bool:
    def limpio(valor, defecto):
        return html.escape(valor) if valor else defecto

    mensaje = (
        "🚨🚨🚨 <b>ENTRADAS DISPONIBLES — BOT EL HORMIGUERO</b> 🤖\n\n"
        f"📅 <b>Día:</b> {limpio(evento.fecha, 'No identificada')}\n"
        f"🕐 <b>Hora:</b> {limpio(evento.hora, 'No identificada')}\n"
        + (f"👤 <b>Invitado:</b> {limpio(evento.invitado, '')}\n" if evento.invitado else "")
        + "🎟️ <b>Estado:</b> DISPONIBLE\n\n"
        f"🔗 <b>ACCESO DIRECTO:</b>\n{evento.url}\n\n"
        "⚡ <b>¡SOLICITA LAS ENTRADAS AHORA!</b>"
    )

    # El primero sale al instante (con botón para tocar desde el iPhone);
    # las repeticiones van en segundo plano para no retrasar la vigilancia.
    resultado = enviar_mensaje(mensaje, boton_url=evento.url)

    def repetir():
        for _ in range(max(1, REPETICIONES) - 1):
            sleep(3)
            enviar_mensaje(mensaje, boton_url=evento.url)

    if REPETICIONES > 1:
        threading.Thread(target=repetir, daemon=True).start()
    return resultado


if __name__ == "__main__":
    ok = enviar_mensaje(
        "✅ Prueba correcta: tu PC puede enviar mensajes del vigilante de El Hormiguero."
    )
    print("Mensaje enviado ✅" if ok else "No se pudo enviar ❌ (revisa el token y el chat id en .env)")
    sys.exit(0 if ok else 1)
