"""Bucle principal de vigilancia.

Dos modos:
  python src/vigilante.py             -> ciclo corto (~4 min, para GitHub Actions)
  python src/vigilante.py --continuo  -> se queda funcionando en tu PC, revisa
                                         cada minuto y no termina nunca.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402  (carga .env antes que nada)
from estado import ahora_iso, cargar_estado, guardar_estado  # noqa: E402
from rascador import EstadoDisponibilidad, consultar  # noqa: E402
from telegram import enviar_alerta, enviar_mensaje  # noqa: E402


RAIZ = config.RAIZ
# Las plazas pueden durar < 2 min (visto en la práctica), por eso 15 s.
INTERVALO_COMPROBACION_SEGUNDOS = config.entero("INTERVALO_REVISION", 15)
DURACION_CICLO_SEGUNDOS = 4 * 60 + 40
INTERVALO_REAVISO_MINUTOS = 10
HORA_INICIO = config.entero("HORA_INICIO", 7)
HORA_FIN = config.entero("HORA_FIN", 23)
AVISO_FALLO_MINUTOS = config.entero("AVISO_FALLO_MINUTOS", 10)

log = logging.getLogger("vigilante")


def configurar_log(a_archivo: bool) -> None:
    formato = logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formato)
    # pythonw no tiene consola: sys.stdout puede ser None.
    if sys.stdout is not None:
        log.addHandler(consola)
    if a_archivo:
        ruta = RAIZ / "datos" / "vigilante.log"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        archivo = RotatingFileHandler(
            ruta, maxBytes=3_000_000, backupCount=5, encoding="utf-8"
        )
        archivo.setFormatter(formato)
        log.addHandler(archivo)


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


def hora_espana() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:  # Windows sin tzdata: usamos la hora local del PC.
        return datetime.now()


def dentro_de_horario() -> bool:
    if HORA_INICIO == HORA_FIN:  # p. ej. 0 y 0 -> 24 horas
        return True
    hora = hora_espana().hour
    if HORA_INICIO < HORA_FIN:
        return HORA_INICIO <= hora < HORA_FIN
    return hora >= HORA_INICIO or hora < HORA_FIN


def etiqueta_evento(evento) -> str:
    """'27 de octubre' a partir de 'martes, 27 de octubre de 2026'."""
    texto = (evento.fecha or evento.identificador).split(",")[-1].strip()
    return re.sub(r" de \d{4}$", "", texto)


def guardar_pagina_evento(evento) -> None:
    """Guarda el HTML del momento en que hay plazas: así se puede ver el
    formulario real y ajustar el rellenado automático."""
    if not evento.html:
        return
    try:
        carpeta = RAIZ / "datos" / "capturas"
        carpeta.mkdir(parents=True, exist_ok=True)
        marca = hora_espana().strftime("%Y%m%d-%H%M%S")
        (carpeta / f"{marca}-evento-{evento.identificador}-DISPONIBLE.html").write_text(
            evento.html, encoding="utf-8")
    except OSError as error:
        log.info(f"No pude guardar la página del evento: {error}")


def procesar_eventos(estado: dict):
    """Hace una comprobación. Devuelve el Resultado (con su diagnóstico)."""
    log.info("Comprobando la web...")

    resultado = consultar()
    eventos = resultado.eventos

    if not resultado.principal_ok:
        log.info(f"❌ NO SE PUEDE LEER LA WEB: {resultado.problema}")
        return resultado

    resumen = " | ".join(f"{etiqueta_evento(e)} {e.estado.value}" for e in eventos)
    if resultado.problema:
        log.info(f"⚠️ Lectura dudosa: {resultado.problema} || {resumen}")
    else:
        log.info(f"✅ Leída (entrando en cada evento): {resumen}")

    eventos_actuales = {evento.identificador for evento in eventos}

    for evento in eventos:
        if evento.estado == EstadoDisponibilidad.AGOTADO:
            estado["eventos"].pop(evento.identificador, None)
            continue

        registro = estado["eventos"].setdefault(evento.identificador, {})

        if evento.estado != EstadoDisponibilidad.DISPONIBLE:
            continue

        if debe_alertar(registro):
            log.info(f"🚨 ¡HAY PLAZAS! {evento.identificador} {evento.url}")
            guardar_pagina_evento(evento)
            if enviar_alerta(evento):
                registro["ultima_alerta"] = ahora_iso()
                log.info(f"📨 Alerta de Telegram enviada: {evento.identificador}")
            else:
                log.info("⚠️ No se pudo enviar el Telegram (se reintentará).")
        else:
            log.info(f"⏳ Ya avisado hace poco: {evento.identificador}")

    estado["eventos"] = {
        identificador: registro
        for identificador, registro in estado["eventos"].items()
        if identificador in eventos_actuales
    }
    return resultado


def ejecutar() -> None:
    """Ciclo corto para GitHub Actions."""
    estado = cargar_estado()
    inicio = time.monotonic()
    log.info(f"🚀 Vigilante (ciclo corto de {DURACION_CICLO_SEGUNDOS} s).")

    while time.monotonic() - inicio < DURACION_CICLO_SEGUNDOS:
        try:
            procesar_eventos(estado)
            guardar_estado(estado)
        except Exception as error:
            log.info(f"❌ Error durante la comprobación: {error}")

        restante = DURACION_CICLO_SEGUNDOS - (time.monotonic() - inicio)
        if restante <= 0:
            break
        time.sleep(min(INTERVALO_COMPROBACION_SEGUNDOS, restante))

    guardar_estado(estado)
    log.info("🏁 Ciclo terminado. Estado guardado.")


def poner_titulo(ultimo_ok_reloj, problema) -> None:
    """Título de la ventana: de un vistazo ves si va bien."""
    if os.name != "nt":
        return
    if problema:
        texto = f"Vigilante Hormiguero - ATENCION: {problema}"
    elif ultimo_ok_reloj:
        texto = f"Vigilante Hormiguero - OK, ultima comprobacion {ultimo_ok_reloj:%H:%M}"
    else:
        texto = "Vigilante Hormiguero - arrancando"
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(texto)
    except Exception:
        pass


def adquirir_bloqueo():
    """Evita que haya dos vigilantes a la vez (dobles avisos)."""
    ruta = RAIZ / "datos" / "vigilante.lock"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    archivo = open(ruta, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        archivo.close()
        return None
    return archivo


def ejecutar_continuo() -> None:
    """Modo PC: no termina nunca, revisa cada INTERVALO_COMPROBACION_SEGUNDOS."""
    bloqueo = adquirir_bloqueo()
    if bloqueo is None:
        log.info("Ya hay otro vigilante funcionando. Salgo.")
        return

    estado = cargar_estado()
    horario = (
        "24 h" if HORA_INICIO == HORA_FIN
        else f"de {HORA_INICIO:02d}:00 a {HORA_FIN:02d}:00"
    )
    log.info(
        f"🚀 Vigilante continuo iniciado. Cada {INTERVALO_COMPROBACION_SEGUNDOS} s, "
        f"{horario} (hora de España)."
    )
    enviar_mensaje(
        "🤖 Vigilante de El Hormiguero arrancado en tu PC.\n"
        f"Revisa cada {INTERVALO_COMPROBACION_SEGUNDOS} s, {horario}.\n"
        + f"Te aviso si llevo {AVISO_FALLO_MINUTOS} min sin poder leer la web."
    )

    ultimo_ok = time.monotonic()
    ultimo_ok_reloj = None
    fallo_avisado = False
    en_pausa = False
    comprobaciones = 0
    ultimo_problema = None
    ultimos_eventos = []
    espera_extra = 0

    while True:
        inicio = time.monotonic()

        if not dentro_de_horario():
            if not en_pausa:
                log.info("🌙 Fuera de horario: en pausa hasta la hora de inicio.")
                en_pausa = True
            time.sleep(60)
            ultimo_ok = time.monotonic()
            continue
        if en_pausa:
            log.info("☀️ Dentro de horario: reanudo la vigilancia.")
            en_pausa = False

        try:
            resultado = procesar_eventos(estado)
            comprobaciones += 1
            if resultado.eventos:
                ultimos_eventos = resultado.eventos
            ultimo_problema = resultado.problema
            if resultado.sano:
                ultimo_ok = time.monotonic()
                ultimo_ok_reloj = hora_espana()
                if fallo_avisado:
                    enviar_mensaje("✅ Vuelvo a leer bien la web de entradas.")
                    fallo_avisado = False
            guardar_estado(estado)
        except Exception as error:
            ultimo_problema = f"error interno: {error!r}"
            log.info(f"❌ Error durante la comprobación: {error!r}")

        poner_titulo(ultimo_ok_reloj, ultimo_problema)

        caida = time.monotonic() - ultimo_ok
        if not fallo_avisado and caida >= AVISO_FALLO_MINUTOS * 60:
            enviar_mensaje(
                f"⚠️ Llevo {AVISO_FALLO_MINUTOS} min sin poder leer bien la web "
                f"de entradas.\nMotivo: {ultimo_problema}\n"
                "Mientras dure esto NO te puedo avisar de plazas. Sigo intentándolo."
            )
            fallo_avisado = True


        if ultimo_problema and "BLOQUEO" in ultimo_problema:
            # Si nos bloquean, insistir más lo empeora: espaciamos y reintentamos.
            espera_extra = min(300, max(espera_extra * 2, 30))
            log.info(f"🛑 Posible bloqueo: espero {espera_extra} s antes de reintentar.")
        else:
            espera_extra = 0
        transcurrido = time.monotonic() - inicio
        time.sleep(max(5, INTERVALO_COMPROBACION_SEGUNDOS - transcurrido) + espera_extra)


def principal() -> None:
    parser = argparse.ArgumentParser(description="Vigilante de El Hormiguero")
    parser.add_argument("--continuo", action="store_true",
                        help="Se queda funcionando indefinidamente (modo PC).")
    parser.add_argument("--una-vez", action="store_true",
                        help="Hace una sola comprobación y sale (sin avisar).")
    args = parser.parse_args()

    configurar_log(a_archivo=args.continuo)

    if args.una_vez:
        resultado = consultar()
        eventos = resultado.eventos
        log.info("✅ Lectura correcta" if resultado.sano
                 else f"⚠️ Problema: {resultado.problema}")
        for evento in eventos:
            log.info(f"[{evento.estado.value}] {evento.fecha} {evento.hora or ''} "
                     f"{evento.url}")
        return
    if args.continuo:
        ejecutar_continuo()
    else:
        ejecutar()


if __name__ == "__main__":
    principal()
