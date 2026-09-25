"""Pruebas de la lógica mínima de alertas."""

from datetime import datetime, timedelta, timezone
import unittest

import sys
sys.path.insert(0, "src")

from vigilante import debe_alertar, INTERVALO_REAVISO_MINUTOS


def iso_hace(minutos: int) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(minutes=minutos)
    ).isoformat()


class PruebasAlertas(unittest.TestCase):
    def test_sin_aviso_previo_debe_alertar(self):
        self.assertTrue(debe_alertar({}))

    def test_aviso_hace_5_minutos_no_debe_alertar(self):
        self.assertFalse(debe_alertar({"ultima_alerta": iso_hace(5)}))

    def test_aviso_hace_10_minutos_debe_alertar(self):
        self.assertTrue(debe_alertar({"ultima_alerta": iso_hace(10)}))

    def test_aviso_hace_20_minutos_debe_alertar(self):
        self.assertTrue(debe_alertar({"ultima_alerta": iso_hace(20)}))

    def test_intervalo_es_10_minutos(self):
        self.assertEqual(INTERVALO_REAVISO_MINUTOS, 10)


if __name__ == "__main__":
    unittest.main()
