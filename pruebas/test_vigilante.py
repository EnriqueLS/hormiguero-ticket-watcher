"""Pruebas de detección y de la lógica de avisos (sin red)."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import Config
from rascador import EstadoDisponibilidad as E, Evento, determinar_estado, extraer_eventos
from vigilante import Vigilante, en_horario, segundos_hasta_inicio


FORMULARIO = """
<form action="/solicitud" method="post">
  <input type="hidden" name="csrf" value="x">
  <input type="text" name="nombre"><input type="email" name="email">
  <input type="tel" name="telefono"><button type="submit">Solicitar entradas</button>
</form>"""

CONFIG = Config(
    telegram_token="t", telegram_chat_id="c", intervalo_segundos=120,
    hora_inicio=7, hora_fin=23, reaviso_minutos=10,
    minutos_para_aviso_fallo=30, comprobaciones_para_aviso_dudoso=3,
)


class PruebasDeteccion(unittest.TestCase):
    def test_formulario_real_es_disponible(self):
        self.assertEqual(determinar_estado(f"<h1>Martes 21</h1>{FORMULARIO}"), E.DISPONIBLE)

    def test_mensaje_sin_plazas_gana_al_formulario(self):
        html = f"<p>Lo sentimos, NO HAY PLAZAS disponibles ahora mismo</p>{FORMULARIO}"
        self.assertEqual(determinar_estado(html), E.AGOTADO)

    def test_mensaje_con_tildes(self):
        self.assertEqual(determinar_estado("<p>Este evento está agotado</p>"), E.AGOTADO)

    def test_boton_sin_formulario_no_es_disponible(self):
        html = '<a class="btn">Solicitar entradas</a>'
        self.assertEqual(determinar_estado(html), E.DESCONOCIDO)

    def test_formulario_de_newsletter_no_cuenta(self):
        html = '<form><input type="email" name="email"><button>Suscribirme</button></form>'
        self.assertEqual(determinar_estado(html), E.DESCONOCIDO)

    def test_texto_en_script_no_cuenta(self):
        html = f"<script>var m='no hay plazas';</script>{FORMULARIO}"
        self.assertEqual(determinar_estado(html), E.DISPONIBLE)

    def test_sin_html_es_desconocido(self):
        self.assertEqual(determinar_estado(None), E.DESCONOCIDO)

    def test_extraer_eventos_sin_duplicados(self):
        html = """
          <a href="/evento/123"><img src="x.jpg"></a>
          <a href="/evento/123">Martes 21 de octubre</a>
          <a href="https://entradas.7yaccion.com/evento/456/">Miércoles 22</a>
          <a href="/aviso-legal">Aviso legal</a>"""
        eventos = extraer_eventos(html)
        self.assertEqual([e.identificador for e in eventos], ["123", "456"])
        self.assertEqual(eventos[0].texto, "Martes 21 de octubre")


class Registro:
    def __init__(self, confirmacion=E.DISPONIBLE):
        self.alertas, self.avisos = [], []
        self.confirmacion = confirmacion

    def vigilante(self, estado=None):
        return Vigilante(
            CONFIG,
            estado or {"eventos": {}, "fallo_desde": None, "aviso_fallo_enviado": False},
            alertar=lambda ev: self.alertas.append(ev.identificador) or True,
            avisar=lambda texto: self.avisos.append(texto) or True,
            confirmar=lambda url: self.confirmacion,
        )


def evento(estado, identificador="1"):
    return Evento(identificador, "Martes", f"https://x/evento/{identificador}", estado)


T0 = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)


class PruebasVigilante(unittest.TestCase):
    def test_disponible_avisa_y_reavisa_a_los_10_minutos(self):
        r = Registro()
        v = r.vigilante()
        v.procesar([evento(E.DISPONIBLE)], True, T0)
        v.procesar([evento(E.DISPONIBLE)], True, T0 + timedelta(minutes=4))
        self.assertEqual(r.alertas, ["1"])
        v.procesar([evento(E.DISPONIBLE)], True, T0 + timedelta(minutes=10))
        self.assertEqual(r.alertas, ["1", "1"])

    def test_no_avisa_si_la_segunda_lectura_no_confirma(self):
        r = Registro(confirmacion=E.AGOTADO)
        r.vigilante().procesar([evento(E.DISPONIBLE)], True, T0)
        self.assertEqual(r.alertas, [])

    def test_agotado_y_reabierto_avisa_al_momento(self):
        r = Registro()
        v = r.vigilante()
        v.procesar([evento(E.DISPONIBLE)], True, T0)
        v.procesar([evento(E.AGOTADO)], True, T0 + timedelta(minutes=2))
        v.procesar([evento(E.DISPONIBLE)], True, T0 + timedelta(minutes=4))
        self.assertEqual(r.alertas, ["1", "1"])

    def test_agotado_no_avisa(self):
        r = Registro()
        r.vigilante().procesar([evento(E.AGOTADO)], True, T0)
        self.assertEqual((r.alertas, r.avisos), ([], []))

    def test_dudoso_avisa_una_sola_vez_tras_3_lecturas(self):
        r = Registro()
        v = r.vigilante()
        for minuto in range(0, 12, 2):
            v.procesar([evento(E.DESCONOCIDO)], True, T0 + timedelta(minutes=minuto))
        self.assertEqual(len(r.avisos), 1)
        self.assertEqual(r.alertas, [])

    def test_fallo_de_web_avisa_a_los_30_minutos_y_al_recuperarse(self):
        r = Registro()
        v = r.vigilante()
        for minuto in range(0, 40, 2):
            v.procesar([], False, T0 + timedelta(minutes=minuto))
        self.assertEqual(len(r.avisos), 1)
        self.assertIn("sin poder leer", r.avisos[0])
        v.procesar([], True, T0 + timedelta(minutes=42))
        self.assertEqual(len(r.avisos), 2)
        self.assertIn("vuelve a responder", r.avisos[1])

    def test_fallo_corto_no_avisa(self):
        r = Registro()
        v = r.vigilante()
        v.procesar([], False, T0)
        v.procesar([], False, T0 + timedelta(minutes=10))
        v.procesar([], True, T0 + timedelta(minutes=12))
        self.assertEqual(r.avisos, [])

    def test_fallo_de_web_conserva_estado_de_eventos(self):
        r = Registro()
        v = r.vigilante()
        v.procesar([evento(E.DISPONIBLE)], True, T0)
        v.procesar([], False, T0 + timedelta(minutes=2))
        v.procesar([evento(E.DISPONIBLE)], True, T0 + timedelta(minutes=4))
        self.assertEqual(r.alertas, ["1"])

    def test_evento_desaparecido_se_olvida(self):
        r = Registro()
        v = r.vigilante()
        v.procesar([evento(E.DISPONIBLE)], True, T0)
        v.procesar([], True, T0 + timedelta(minutes=2))
        self.assertEqual(v.estado["eventos"], {})


class PruebasHorario(unittest.TestCase):
    def test_horario_madrid(self):
        # 14 oct 2026: Madrid está en UTC+2.
        self.assertFalse(en_horario(datetime(2026, 10, 14, 4, 59, tzinfo=timezone.utc), CONFIG))
        self.assertTrue(en_horario(datetime(2026, 10, 14, 5, 0, tzinfo=timezone.utc), CONFIG))
        self.assertTrue(en_horario(datetime(2026, 10, 14, 20, 59, tzinfo=timezone.utc), CONFIG))
        self.assertFalse(en_horario(datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc), CONFIG))

    def test_espera_hasta_las_7(self):
        # 23:00 en Madrid → faltan 8 horas.
        ahora = datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc)
        self.assertEqual(segundos_hasta_inicio(ahora, CONFIG), 8 * 3600)

    def test_horario_24h(self):
        config = replace(CONFIG, hora_inicio=0, hora_fin=24)
        self.assertTrue(en_horario(datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc), config))


if __name__ == "__main__":
    unittest.main()
