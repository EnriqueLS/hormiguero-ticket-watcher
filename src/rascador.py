"""Rascador de eventos de El Hormiguero."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL_PRINCIPAL = "https://entradas.7yaccion.com/"
TIEMPO_ESPERA = 20


class EstadoDisponibilidad(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    AGOTADO = "AGOTADO"
    DESCONOCIDO = "DESCONOCIDO"


@dataclass
class Evento:
    identificador: str
    fecha: Optional[str]
    hora: Optional[str]
    url: str
    invitado: Optional[str] = None
    estado: EstadoDisponibilidad = EstadoDisponibilidad.DESCONOCIDO


def crear_sesion() -> requests.Session:
    sesion = requests.Session()
    sesion.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (compatible; ElHormigueroTicketWatcher/1.0; "
            "+https://github.com/EnriqueLS/hormiguero-ticket-watcher)"
        )
    })
    return sesion


def obtener_html(sesion: requests.Session, url: str) -> Optional[str]:
    try:
        respuesta = sesion.get(url, timeout=TIEMPO_ESPERA)
        respuesta.raise_for_status()
        return respuesta.text
    except requests.RequestException:
        return None


def normalizar_texto(texto: str) -> str:
    return " ".join(texto.split()).strip().lower()


def texto_visible(html: str) -> str:
    """Texto del cuerpo, sin <head>/<script>/<style> (evita falsos positivos
    con las metaetiquetas, que dicen "Solicita tus entradas" siempre)."""
    soup = BeautifulSoup(html, "html.parser")
    for etiqueta in soup(["head", "script", "style", "noscript", "title"]):
        etiqueta.decompose()
    return normalizar_texto(soup.get_text(" "))


PALABRAS_FORMULARIO = ("dni", "nie", "telefono", "teléfono", "movil", "móvil",
                       "email", "correo", "nombre", "apellido")


def tiene_formulario_solicitud(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for formulario in soup.find_all("form"):
        campos = formulario.find_all(["input", "select", "textarea"])
        for campo in campos:
            pista = " ".join(
                str(campo.get(atributo, ""))
                for atributo in ("name", "id", "placeholder", "type")
            ).lower()
            if any(palabra in pista for palabra in PALABRAS_FORMULARIO):
                return True
    return False


def determinar_estado(html: Optional[str]) -> EstadoDisponibilidad:
    """Determina el estado sin adivinar: si no hay señal clara, DESCONOCIDO."""
    if not html:
        return EstadoDisponibilidad.DESCONOCIDO

    texto = texto_visible(html)

    indicadores_agotado = (
        "no hay plazas disponibles ahora mismo",
        "entradas agotadas",
        "no quedan plazas disponibles para este evento",
        "no hay plazas disponibles",
    )
    if any(indicador in texto for indicador in indicadores_agotado):
        return EstadoDisponibilidad.AGOTADO

    indicadores_disponible = (
        "solicitar entradas",
        "solicita tus entradas",
        "solicitar las entradas",
    )
    if any(indicador in texto for indicador in indicadores_disponible):
        return EstadoDisponibilidad.DISPONIBLE

    if tiene_formulario_solicitud(html):
        return EstadoDisponibilidad.DISPONIBLE

    return EstadoDisponibilidad.DESCONOCIDO


PATRON_FECHA = re.compile(
    r"(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)"
    r",?\s+\d{1,2}\s+de\s+[a-záéíóú]+(?:\s+de\s+\d{4})?",
    re.IGNORECASE,
)
PATRON_HORA = re.compile(r"\b(\d{1,2}:\d{2})\s*h", re.IGNORECASE)


def extraer_fecha_hora(texto: str) -> tuple[Optional[str], Optional[str]]:
    fecha = PATRON_FECHA.search(texto)
    hora = PATRON_HORA.search(texto)
    return (
        fecha.group(0) if fecha else None,
        hora.group(1) if hora else None,
    )


def extraer_eventos(html: Optional[str]) -> list[Evento]:
    """Extrae los eventos publicados en la página principal."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    eventos: list[Evento] = []
    vistos: set[str] = set()

    for enlace in soup.find_all("a", href=True):
        url = urljoin(URL_PRINCIPAL, enlace["href"])
        if "/evento/" not in url or url in vistos:
            continue

        vistos.add(url)
        identificador = url.rstrip("/").split("/")[-1]
        texto = " ".join(enlace.get_text(" ").split()).strip()
        fecha, hora = extraer_fecha_hora(texto)

        eventos.append(Evento(
            identificador=identificador,
            fecha=fecha or texto or None,
            hora=hora,
            url=url,
        ))

    return eventos


def consultar_eventos() -> tuple[list[Evento], bool]:
    """Descubre eventos y consulta cada página individual.

    El segundo valor indica si la página principal se pudo consultar.
    """
    sesion = crear_sesion()
    html_principal = obtener_html(sesion, URL_PRINCIPAL)

    if html_principal is None:
        return [], False

    eventos = extraer_eventos(html_principal)

    for evento in eventos:
        html_evento = obtener_html(sesion, evento.url)
        evento.estado = determinar_estado(html_evento)
        if html_evento:
            fecha, hora = extraer_fecha_hora(texto_visible(html_evento))
            evento.fecha = fecha or evento.fecha
            evento.hora = hora or evento.hora

    return eventos, True


if __name__ == "__main__":
    eventos, _ = consultar_eventos()
    for evento in eventos:
        print(
            f"[{evento.estado.value}] "
            f"evento={evento.identificador} "
            f"fecha={evento.fecha!r} hora={evento.hora!r} "
            f"url={evento.url}"
        )
