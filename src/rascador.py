"""Rascador de eventos de El Hormiguero.

Este módulo obtiene los eventos publicados en la web oficial y determina
su estado de disponibilidad.

Estados posibles:
- DISPONIBLE: la página del evento confirma que se pueden solicitar entradas.
- AGOTADO: el evento existe, pero actualmente no hay plazas disponibles.
- DESCONOCIDO: no hemos podido determinar el estado con suficiente confianza.

IMPORTANTE:
AGOTADO no significa que dejemos de vigilar el evento. Las plazas pueden
liberarse posteriormente.
DESCONOCIDO tampoco debe provocar una alerta.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL_PRINCIPAL = "https://entradas.7yaccion.com/"
NOMBRE_EVENTO = "El Hormiguero"

TIEMPO_ESPERA = 20


class EstadoDisponibilidad(str, Enum):
    """Estados que puede tener un evento."""

    DISPONIBLE = "DISPONIBLE"
    AGOTADO = "AGOTADO"
    DESCONOCIDO = "DESCONOCIDO"


@dataclass
class Evento:
    """Información básica de un evento."""

    identificador: str
    fecha: Optional[str]
    hora: Optional[str]
    url: str
    estado: EstadoDisponibilidad = EstadoDisponibilidad.DESCONOCIDO


def crear_sesion() -> requests.Session:
    """Crea una sesión HTTP reutilizable."""

    sesion = requests.Session()
    sesion.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; "
                "ElHormigueroTicketWatcher/1.0; +https://github.com/EnriqueLS/"
                "hormiguero-ticket-watcher)"
            )
        }
    )
    return sesion


def obtener_html(sesion: requests.Session, url: str) -> Optional[str]:
    """Descarga una página y devuelve su HTML.

    Si hay un error de red, HTTP o tiempo de espera, devuelve None.
    El resto del programa lo interpreta como DESCONOCIDO.
    """

    try:
        respuesta = sesion.get(url, timeout=TIEMPO_ESPERA)
        respuesta.raise_for_status()
        return respuesta.text
    except requests.RequestException:
        return None


def normalizar_texto(texto: str) -> str:
    """Normaliza espacios para facilitar las comprobaciones."""

    return " ".join(texto.split()).strip().lower()


def determinar_estado(html: Optional[str]) -> EstadoDisponibilidad:
    """Determina el estado de disponibilidad de una página de evento.

    No intentamos adivinar. Si no encontramos una señal clara de disponible
    o agotado, devolvemos DESCONOCIDO para evitar falsas alertas.
    """

    if not html:
        return EstadoDisponibilidad.DESCONOCIDO

    texto = normalizar_texto(BeautifulSoup(html, "html.parser").get_text(" "))

    # Textos que indican que actualmente no hay plazas.
    indicadores_agotado = (
        "no hay plazas disponibles ahora mismo",
        "entradas agotadas",
        "no hay plazas disponibles",
    )

    if any(indicador in texto for indicador in indicadores_agotado):
        return EstadoDisponibilidad.AGOTADO

    # Textos que indican que el usuario puede iniciar la solicitud.
    indicadores_disponible = (
        "solicitar entradas",
        "solicita tus entradas",
        "solicitar las entradas",
    )

    if any(indicador in texto for indicador in indicadores_disponible):
        return EstadoDisponibilidad.DISPONIBLE

    return EstadoDisponibilidad.DESCONOCIDO


def extraer_eventos(html: Optional[str]) -> list[Evento]:
    """Extrae enlaces que parecen corresponder a eventos de El Hormiguero.

    Esta primera versión es deliberadamente conservadora. Si la estructura
    exacta de la web cambia, preferimos detectar menos eventos antes que
    inventar URLs o estados.
    """

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    eventos: list[Evento] = []
    vistos: set[str] = set()

    for enlace in soup.find_all("a", href=True):
        url = urljoin(URL_PRINCIPAL, enlace["href"])
        texto = normalizar_texto(enlace.get_text(" "))

        # Los eventos actuales utilizan URLs bajo /evento/.
        if "/evento/" not in url:
            continue

        if url in vistos:
            continue

        vistos.add(url)

        identificador = url.rstrip("/").split("/")[-1]

        eventos.append(
            Evento(
                identificador=identificador,
                fecha=texto or None,
                hora=None,
                url=url,
            )
        )

    return eventos


def consultar_eventos() -> list[Evento]:
    """Obtiene los eventos y consulta su disponibilidad individual."""

    sesion = crear_sesion()

    html_principal = obtener_html(sesion, URL_PRINCIPAL)
    eventos = extraer_eventos(html_principal)

    for evento in eventos:
        html_evento = obtener_html(sesion, evento.url)
        evento.estado = determinar_estado(html_evento)

    return eventos


if __name__ == "__main__":
    eventos = consultar_eventos()

    if not eventos:
        print("No se han encontrado eventos.")

    for evento in eventos:
        print(
            f"[{evento.estado.value}] "
            f"evento={evento.identificador} "
            f"texto={evento.fecha!r} "
            f"url={evento.url}"
        )
