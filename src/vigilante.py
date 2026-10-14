"""Vigilante de entradas de El Hormiguero.

Uso:
    python src/vigilante.py                   # vigila sin parar (modo normal)
    python src/vigilante.py --una-vez         # una sola comprobación, sin avisos
    python src/vigilante.py --probar-telegram # envía un mensaje de prueba
    python src/vigilante.py --diagnosticar [URL]
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from html import escape
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rascador
import telegram
from config import RAIZ, Config, leer_config
from estado import cargar_estado, guardar_estado
from rascador import EstadoDisponibilidad, Evento


ZONA = ZoneInfo("Europe/Madrid")
RUTA_LOGS = RAIZ / "logs"
SEGUNDOS_ANTES_DE_CONFIRMAR = 5

log = logging.getLogger("vigilante")


# --------------------------------------------------------------------------
# Lógica de decisión (sin red, fácil de probar)
# --------------------------------------------------------------------------

def fecha_desde_iso(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(valor)
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def debe_alertar(registro: dict, ahora: datetime, reaviso_minutos: int) -> bool:
    ultima = fecha_desde_iso(registro.get("ultima_alerta"))
    return ultima is None or ahora - ultima >= timedelta(minutes=reaviso_minutos)


def en_horario(ahora: datetime, config: Config) -> bool:
    hora = ahora.astimezone(ZONA).hour
    return config.hora_inicio <= hora < config.hora_fin


def segundos_hasta_inicio(ahora: datetime, config: Config) -> float:
    local = ahora.astimezone(ZONA)
    inicio = local.replace(hour=config.hora_inicio, minute=0, second=0, microsecond=0)
    if inicio <= local:
        inicio += timedelta(days=1)
    return (inicio - local).total_seconds()


class Vigilante:
    def __init__(
        self,
        config: Config,
        estado: dict,
        alertar: Callable[[Evento], bool],
        avisar: Callable[[str], bool],
        confirmar: Callable[[str], EstadoDisponibilidad],
    ) -> None:
        self.config = config
        self.estado = estado
        self.alertar = alertar
        self.avisar = avisar
        self.confirmar = confirmar

    def procesar(self, eventos: list[Evento], pagina_ok: bool, ahora: datetime) -> None:
        if not pagina_ok:
            self._registrar_fallo(ahora)
            return
        self._registrar_recuperacion()

        log.info("Web principal OK. Eventos: %d", len(eventos))
        for evento in eventos:
            log.info("  %-11s %s | %s", evento.estado.value, evento.texto or "-", evento.url)
            registro = self.estado["eventos"].setdefault(evento.identificador, {})

            if evento.estado == EstadoDisponibilidad.DESCONOCIDO:
                self._registrar_dudoso(evento, registro)
                continue

            registro.pop("dudoso_seguidas", None)
            registro.pop("aviso_dudoso_enviado", None)

            if evento.estado == EstadoDisponibilidad.AGOTADO:
                # Si vuelve a abrirse, se avisará al momento.
                registro.pop("ultima_alerta", None)
            else:
                self._gestionar_disponible(evento, registro, ahora)

        presentes = {evento.identificador for evento in eventos}
        self.estado["eventos"] = {
            k: v for k, v in self.estado["eventos"].items() if k in presentes and v
        }

    def _gestionar_disponible(self, evento: Evento, registro: dict, ahora: datetime) -> None:
        if not debe_alertar(registro, ahora, self.config.reaviso_minutos):
            log.info("  Reaviso en espera: %s", evento.identificador)
            return

        # Segunda comprobación independiente para evitar falsos positivos.
        confirmacion = self.confirmar(evento.url)
        if confirmacion != EstadoDisponibilidad.DISPONIBLE:
            log.warning("  No confirmado en segunda lectura (%s): %s",
                        confirmacion.value, evento.identificador)
            return

        log.warning("🚨 DISPONIBLE confirmado: %s", evento.url)
        if self.alertar(evento):
            registro["ultima_alerta"] = ahora.isoformat()

    def _registrar_dudoso(self, evento: Evento, registro: dict) -> None:
        registro["dudoso_seguidas"] = registro.get("dudoso_seguidas", 0) + 1
        if (
            registro["dudoso_seguidas"] >= self.config.comprobaciones_para_aviso_dudoso
            and not registro.get("aviso_dudoso_enviado")
        ):
            enviado = self.avisar(
                "⚠️ <b>Vigilante Hormiguero</b>\n"
                "No sé si este evento tiene plazas: no veo mensaje de «sin plazas» "
                "ni formulario. Puede que la web haya cambiado. Échale un ojo:\n"
                f"{escape(evento.url)}"
            )
            registro["aviso_dudoso_enviado"] = enviado

    def _registrar_fallo(self, ahora: datetime) -> None:
        log.error("No se pudo leer la web principal.")
        desde = fecha_desde_iso(self.estado.get("fallo_desde"))
        if desde is None:
            self.estado["fallo_desde"] = ahora.isoformat()
            return
        minutos = (ahora - desde).total_seconds() / 60
        if minutos >= self.config.minutos_para_aviso_fallo and not self.estado.get("aviso_fallo_enviado"):
            self.estado["aviso_fallo_enviado"] = self.avisar(
                "❌ <b>Vigilante Hormiguero</b>\n"
                f"Llevo {int(minutos)} minutos sin poder leer {rascador.URL_PRINCIPAL}\n"
                "Sigo intentándolo; te aviso cuando vuelva."
            )

    def _registrar_recuperacion(self) -> None:
        if self.estado.get("aviso_fallo_enviado"):
            self.avisar("✅ <b>Vigilante Hormiguero</b>\nLa web vuelve a responder.")
        self.estado["fallo_desde"] = None
        self.estado["aviso_fallo_enviado"] = False


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------

def configurar_logs() -> None:
    RUTA_LOGS.mkdir(exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)

    fichero = RotatingFileHandler(
        RUTA_LOGS / "vigilante.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    fichero.setFormatter(formato)
    raiz.addHandler(fichero)

    # Con pythonw.exe no hay consola.
    if sys.stdout is not None:
        consola = logging.StreamHandler(sys.stdout)
        consola.setFormatter(formato)
        raiz.addHandler(consola)


def crear_vigilante(config: Config, sesion, con_avisos: bool = True) -> Vigilante:
    def confirmar(url: str) -> EstadoDisponibilidad:
        time.sleep(SEGUNDOS_ANTES_DE_CONFIRMAR)
        return rascador.consultar_estado(sesion, url)

    if con_avisos:
        alertar = lambda evento: telegram.enviar_alerta(config, evento)
        avisar = lambda texto: telegram.enviar_aviso(config, texto)
    else:
        alertar = lambda evento: log.info("(sin avisos) alertaría: %s", evento.url) or True
        avisar = lambda texto: log.info("(sin avisos) avisaría: %s", texto) or True

    return Vigilante(config, cargar_estado(), alertar, avisar, confirmar)


def comprobar(vigilante: Vigilante, sesion) -> None:
    eventos, pagina_ok = rascador.consultar_eventos(sesion)
    vigilante.procesar(eventos, pagina_ok, datetime.now(timezone.utc))


def vigilar(config: Config) -> None:
    sesion = rascador.crear_sesion()
    vigilante = crear_vigilante(config, sesion)

    log.info(
        "Vigilante iniciado: cada %d s, de %02d:00 a %02d:00 (Madrid).",
        config.intervalo_segundos, config.hora_inicio, config.hora_fin,
    )
    telegram.enviar_aviso(
        config,
        "🟢 <b>Vigilante Hormiguero arrancado</b>\n"
        f"Compruebo cada {config.intervalo_segundos // 60 or 1} min, "
        f"de {config.hora_inicio:02d}:00 a {config.hora_fin:02d}:00.",
    )

    while True:
        ahora = datetime.now(timezone.utc)
        if not en_horario(ahora, config):
            espera = segundos_hasta_inicio(ahora, config)
            log.info("Fuera de horario. Durmiendo %.0f min.", espera / 60)
            # Por tramos, por si el PC se suspende y cambia la hora.
            time.sleep(min(espera, 300))
            continue

        try:
            comprobar(vigilante, sesion)
        except Exception:
            log.exception("Error inesperado durante la comprobación")
        try:
            guardar_estado(vigilante.estado)
        except OSError:
            log.exception("No se pudo guardar el estado")

        # Pequeña variación para no ir siempre al segundo exacto.
        time.sleep(config.intervalo_segundos + random.uniform(-10, 10))


def diagnosticar(url: str | None) -> None:
    sesion = rascador.crear_sesion()
    urls = [url] if url else []
    if not url:
        html = rascador.obtener_html(sesion, rascador.URL_PRINCIPAL)
        if html is None:
            print(f"❌ No se pudo descargar {rascador.URL_PRINCIPAL}")
            return
        (RUTA_LOGS / "diagnostico_principal.html").write_text(html, encoding="utf-8")
        eventos = rascador.extraer_eventos(html)
        print(f"Web principal: {len(eventos)} eventos encontrados")
        urls = [e.url for e in eventos]

    for numero, url_evento in enumerate(urls, 1):
        html = rascador.obtener_html(sesion, url_evento)
        print(f"\n== {url_evento}")
        if html is None:
            print("   ❌ No se pudo descargar")
            continue
        destino = RUTA_LOGS / f"diagnostico_evento_{numero}.html"
        destino.write_text(html, encoding="utf-8")
        soup = rascador.BeautifulSoup(html, "html.parser")
        texto = rascador.normalizar_texto(soup.get_text(" "))
        frases = [f for f in rascador.FRASES_AGOTADO if f in texto]
        campos = [rascador.contar_campos(f) for f in soup.find_all("form")]
        print(f"   Estado:               {rascador.determinar_estado(html).value}")
        print(f"   Frases de 'sin plazas': {frases or 'ninguna'}")
        print(f"   Formularios (campos):  {campos or 'ninguno'}")
        print(f"   HTML guardado en:      {destino}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vigilante de entradas de El Hormiguero")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--una-vez", action="store_true", help="una comprobación sin enviar avisos")
    grupo.add_argument("--probar-telegram", action="store_true", help="envía un mensaje de prueba")
    grupo.add_argument("--diagnosticar", nargs="?", const="", metavar="URL",
                       help="analiza la web (o una URL de evento) y guarda el HTML")
    args = parser.parse_args()

    configurar_logs()
    config = leer_config()

    if args.probar_telegram:
        ok = telegram.enviar_aviso(config, "✅ Prueba correcta: el vigilante puede enviarte mensajes.")
        print("Mensaje enviado ✅" if ok else "No se pudo enviar ❌ (mira logs/vigilante.log)")
        sys.exit(0 if ok else 1)
    if args.diagnosticar is not None:
        diagnosticar(args.diagnosticar or None)
        return
    if args.una_vez:
        sesion = rascador.crear_sesion()
        comprobar(crear_vigilante(config, sesion, con_avisos=False), sesion)
        return

    if not config.telegram_token or not config.telegram_chat_id:
        log.error("Faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en el fichero .env")
        sys.exit(1)
    vigilar(config)


if __name__ == "__main__":
    main()
