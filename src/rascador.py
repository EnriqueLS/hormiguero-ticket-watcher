"""Rascador de eventos de El Hormiguero."""

from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL_PRINCIPAL = "https://entradas.7yaccion.com/"
TIEMPO_ESPERA = 20
REINTENTOS = 2

# Textos que indican que, aunque la fecha salga abierta, no hay plazas.
# Se comparan en minúsculas y sin tildes.
FRASES_AGOTADO = (
    "no hay plazas",
    "no quedan plazas",
    "sin plazas disponibles",
    "plazas agotadas",
    "entradas agotadas",
    "evento agotado",
    "esta agotado",
    "estan agotadas",
    "aforo completo",
)

# Tipos de <input> que cuentan como campos que rellena una persona.
TIPOS_CAMPO = {"", "text", "email", "tel", "number", "date"}
MINIMO_CAMPOS_FORMULARIO = 2


class EstadoDisponibilidad(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    AGOTADO = "AGOTADO"
    DESCONOCIDO = "DESCONOCIDO"


@dataclass
class Evento:
    identificador: str
    texto: Optional[str]
    url: str
    estado: EstadoDisponibilidad = EstadoDisponibilidad.DESCONOCIDO


def crear_sesion() -> requests.Session:
    sesion = requests.Session()
    sesion.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9",
    })
    return sesion


def obtener_html(sesion: requests.Session, url: str) -> Optional[str]:
    for intento in range(REINTENTOS + 1):
        try:
            respuesta = sesion.get(url, timeout=TIEMPO_ESPERA)
            respuesta.raise_for_status()
            return respuesta.text
        except requests.RequestException:
            if intento < REINTENTOS:
                time.sleep(3)
    return None


def normalizar_texto(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.split()).lower()


def contar_campos(formulario) -> int:
    campos = 0
    for campo in formulario.find_all(["input", "select", "textarea"]):
        if campo.name == "input":
            if campo.get("type", "").lower() not in TIPOS_CAMPO:
                continue
        campos += 1
    return campos


def hay_formulario_solicitud(soup: BeautifulSoup) -> bool:
    """Hay un formulario con varios campos para rellenar (nombre, email...)."""
    return any(
        contar_campos(formulario) >= MINIMO_CAMPOS_FORMULARIO
        for formulario in soup.find_all("form")
    )


def determinar_estado(html: Optional[str]) -> EstadoDisponibilidad:
    """Clasifica la página de un evento sin adivinar.

    - Si aparece un mensaje de "sin plazas" → AGOTADO, aunque haya formulario.
    - Si hay un formulario real para rellenar → DISPONIBLE.
    - En cualquier otro caso → DESCONOCIDO.
    """
    if not html:
        return EstadoDisponibilidad.DESCONOCIDO

    soup = BeautifulSoup(html, "html.parser")
    for oculto in soup(["script", "style", "noscript", "template"]):
        oculto.decompose()

    texto = normalizar_texto(soup.get_text(" "))
    if any(frase in texto for frase in FRASES_AGOTADO):
        return EstadoDisponibilidad.AGOTADO

    if hay_formulario_solicitud(soup):
        return EstadoDisponibilidad.DISPONIBLE

    return EstadoDisponibilidad.DESCONOCIDO


def extraer_eventos(html: Optional[str]) -> list[Evento]:
    """Extrae los eventos enlazados desde la página principal."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    eventos: dict[str, Evento] = {}

    for enlace in soup.find_all("a", href=True):
        url = urljoin(URL_PRINCIPAL, enlace["href"]).split("#")[0]
        if "/evento/" not in url:
            continue

        texto = " ".join(enlace.get_text(" ").split()) or None
        if url in eventos:
            # Puede haber varios enlaces al mismo evento (imagen y título).
            if texto and not eventos[url].texto:
                eventos[url].texto = texto
            continue

        eventos[url] = Evento(
            identificador=url.rstrip("/").split("/")[-1],
            texto=texto,
            url=url,
        )

    return list(eventos.values())


def consultar_estado(sesion: requests.Session, url: str) -> EstadoDisponibilidad:
    return determinar_estado(obtener_html(sesion, url))


def consultar_eventos(
    sesion: requests.Session,
) -> tuple[list[Evento], bool]:
    """Descubre eventos y consulta cada página individual.

    El segundo valor indica si la página principal se pudo consultar.
    """
    html_principal = obtener_html(sesion, URL_PRINCIPAL)
    if html_principal is None:
        return [], False

    eventos = extraer_eventos(html_principal)
    for evento in eventos:
        evento.estado = consultar_estado(sesion, evento.url)

    return eventos, True
