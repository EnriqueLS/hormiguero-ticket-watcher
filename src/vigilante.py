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
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402  (carga .env antes que nada)
from estado import ahora_iso, cargar_estado, guardar_estado  # noqa: E402
from rascador import EstadoDisponibilidad, consultar_eventos  # noqa: E402
from telegram import enviar_alerta, enviar_mensaje  # noqa: E402


RAIZ = config.RAIZ
INTERVALO_COMPROBACION_SEGUNDOS = config.entero("INTERVALO_SEGUNDOS", 60)
DURACION_CICLO_SEGUNDOS = 4 * 60 + 40
INTERVALO_REAVISO_MINUTOS = 10
HORA_INICIO = config.entero("HORA_INICIO", 7)
HORA_FIN = config.entero("HORA_FIN", 23)
ABRIR_NAVEGADOR = config.booleano("ABRIR_NAVEGADOR", True)
AVISO_FALLO_MINUTOS = config.entero("AVISO_FALLO_MINUTOS", 30)

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
            ruta, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
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


def procesar_eventos(estado: dict, abrir_navegador: bool = False) -> bool:
    """Hace una comprobación. Devuelve True si la web principal respondió."""
    log.info("Comprobando la web...")

    eventos, pagina_principal_ok = consultar_eventos()

    if not pagina_principal_ok:
        log.info("❌ No se pudo consultar la web principal; se conserva el estado.")
        return False

    log.info(f"✅ Web OK. Eventos encontrados: {len(eventos)}")

    eventos_actuales = {evento.identificador for evento in eventos}

    for evento in eventos:
        log.info(
            f"   → {evento.identificador} | {evento.fecha or '?'} "
            f"{evento.hora or ''} | {evento.estado.value}"
        )

        if evento.estado == EstadoDisponibilidad.AGOTADO:
            estado["eventos"].pop(evento.identificador, None)
            continue

        registro = estado["eventos"].setdefault(evento.identificador, {})

        if evento.estado != EstadoDisponibilidad.DISPONIBLE:
            continue

        if debe_alertar(registro):
            primera_vez = not registro.get("ultima_alerta")
            log.info(f"🚨 ¡HAY PLAZAS! {evento.identificador} {evento.url}")
            if abrir_navegador and primera_vez:
                try:
                    webbrowser.open(evento.url, new=2)
                except Exception as error:
                    log.info(f"No se pudo abrir el navegador: {error}")
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
    return True


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
        f"Revisa cada {INTERVALO_COMPROBACION_SEGUNDOS} s, {horario}."
    )

    ultimo_ok = time.monotonic()
    fallo_avisado = False
    en_pausa = False

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
            if procesar_eventos(estado, abrir_navegador=ABRIR_NAVEGADOR):
                ultimo_ok = time.monotonic()
                if fallo_avisado:
                    enviar_mensaje("✅ La web de entradas vuelve a responder.")
                    fallo_avisado = False
            guardar_estado(estado)
        except Exception as error:
            log.info(f"❌ Error durante la comprobación: {error!r}")

        caida = time.monotonic() - ultimo_ok
        if not fallo_avisado and caida >= AVISO_FALLO_MINUTOS * 60:
            enviar_mensaje(
                f"⚠️ Llevo {AVISO_FALLO_MINUTOS} min sin poder leer la web de "
                "entradas (¿sin internet o web caída?). Sigo intentándolo."
            )
            fallo_avisado = True

        transcurrido = time.monotonic() - inicio
        time.sleep(max(5, INTERVALO_COMPROBACION_SEGUNDOS - transcurrido))


def principal() -> None:
    parser = argparse.ArgumentParser(description="Vigilante de El Hormiguero")
    parser.add_argument("--continuo", action="store_true",
                        help="Se queda funcionando indefinidamente (modo PC).")
    parser.add_argument("--una-vez", action="store_true",
                        help="Hace una sola comprobación y sale (sin avisar).")
    args = parser.parse_args()

    configurar_log(a_archivo=args.continuo)

    if args.una_vez:
        eventos, ok = consultar_eventos()
        log.info(f"Web principal OK: {ok}")
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
