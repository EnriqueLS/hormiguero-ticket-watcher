"""Abre la página de un evento y rellena el formulario con TUS datos (.env).
NUNCA lo envía: el botón "Enviar" lo pulsas tú, cuando decidas.

Uso:  python src/reservar.py https://entradas.7yaccion.com/evento/418/

Seguridad:
- Si hay captcha o queda algún campo obligatorio sin rellenar, te avisa.
- Siempre guarda una captura y el HTML en datos/capturas/ para poder revisar
  (y ajustar el rellenado) después de cada intento.
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from telegram import enviar_foto, enviar_mensaje  # noqa: E402

RAIZ = config.RAIZ
CAPTURAS = RAIZ / "datos" / "capturas"

DATOS = {
    "nombre": os.getenv("DATOS_NOMBRE", "").strip(),
    "apellidos": os.getenv("DATOS_APELLIDOS", "").strip(),
    "dni": os.getenv("DATOS_DNI", "").strip(),
    "telefono": os.getenv("DATOS_TELEFONO", "").strip(),
    "email": os.getenv("DATOS_EMAIL", "").strip(),
    "personas": os.getenv("DATOS_PERSONAS", "1").strip() or "1",
}
ACEPTAR_CONDICIONES = config.booleano("ACEPTAR_CONDICIONES", False)
HEADLESS = config.booleano("NAVEGADOR_OCULTO", False)
ESPERA_FORMULARIO = config.entero("ESPERA_FORMULARIO_SEGUNDOS", 150)

# Qué campo es cada uno, según el texto de name/id/placeholder/etiqueta.
# El orden importa (apellidos antes que nombre).
REGLAS = [
    ("email", r"e-?mail|correo"),
    ("telefono", r"tel[eé]fono|\btel\b|m[oó]vil|movil|phone|celular"),
    ("dni", r"\bdni\b|\bnie\b|\bnif\b|documento|pasaporte|identidad"),
    ("apellidos", r"apellido|surname|last.?name"),
    ("nombre", r"nombre|first.?name|\bname\b"),
    ("personas", r"personas|acompa|asistentes|entradas|plazas|invitados|n[ºo°]\s*de"),
]
TEXTO_CONDICIONES = re.compile(
    r"acepto|condiciones|privacidad|pol[ií]tica|protecci[oó]n de datos|"
    r"aviso legal|consentimiento|he le[ií]do", re.I)

JS_CONTROLES = """
() => {
  const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const lista = [];
  document.querySelectorAll('input, select, textarea').forEach((e, i) => {
    const tipo = (e.type || e.tagName).toLowerCase();
    if (['hidden','submit','button','image','reset'].includes(tipo)) return;
    if (!visible(e)) return;
    e.setAttribute('data-hw', String(i));
    let etiqueta = '';
    if (e.id) { const l = document.querySelector('label[for="'+CSS.escape(e.id)+'"]'); if (l) etiqueta = l.innerText; }
    if (!etiqueta) { const l = e.closest('label'); if (l) etiqueta = l.innerText; }
    lista.push({
      i, tag: e.tagName.toLowerCase(), tipo, nombre: e.name || '', id: e.id || '',
      placeholder: e.placeholder || '', aria: e.getAttribute('aria-label') || '',
      auto: e.autocomplete || '', etiqueta, obligatorio: e.required || e.getAttribute('aria-required') === 'true',
      marcado: !!e.checked, valor: e.value || '',
      opciones: e.tagName === 'SELECT' ? Array.from(e.options).map(o => ({v: o.value, t: o.text})) : []
    });
  });
  return lista;
}
"""


def log(texto: str) -> None:
    print(f"{datetime.now():%H:%M:%S}  {texto}", flush=True)


def clasificar(control: dict) -> str | None:
    pista = " ".join(str(control[k]) for k in
                     ("nombre", "id", "placeholder", "aria", "auto", "etiqueta")).lower()
    if control["tipo"] == "email":
        return "email"
    if control["tipo"] == "tel":
        return "telefono"
    for clave, patron in REGLAS:
        if re.search(patron, pista):
            return clave
    return None


def abrir_navegador(playwright):
    ruta = os.getenv("NAVEGADOR_RUTA", "").strip()
    if ruta:
        return playwright.chromium.launch(executable_path=ruta, headless=HEADLESS)
    errores = []
    # Edge y Chrome ya están en Windows: no hace falta descargar nada.
    for canal in ("msedge", "chrome"):
        try:
            return playwright.chromium.launch(channel=canal, headless=HEADLESS)
        except Exception as error:  # noqa: BLE001
            errores.append(f"{canal}: {error}")
    try:
        return playwright.chromium.launch(headless=HEADLESS)
    except Exception as error:  # noqa: BLE001
        raise RuntimeError("No encuentro Edge ni Chrome: " + " | ".join(errores)) from error


def guardar_captura(pagina, nombre: str) -> Path:
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    base = CAPTURAS / f"{datetime.now():%Y%m%d-%H%M%S}-{nombre}"
    try:
        pagina.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    except Exception:  # noqa: BLE001
        pass
    try:
        base.with_suffix(".html").write_text(pagina.content(), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    for viejo in sorted(CAPTURAS.glob("*"))[:-60]:  # no acumular sin fin
        viejo.unlink(missing_ok=True)
    return base.with_suffix(".png")


def hay_captcha(pagina) -> bool:
    return pagina.locator(
        "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='turnstile'], "
        ".g-recaptcha, .h-captcha, .cf-turnstile"
    ).count() > 0


def rechazar_cookies(pagina) -> None:
    try:
        boton = pagina.get_by_role("button", name=re.compile(r"^\s*rechazar", re.I))
        if boton.count():
            boton.first.click(timeout=1500)
    except Exception:  # noqa: BLE001
        pass


def esperar_formulario(pagina, url: str) -> list[dict] | None:
    """Recarga hasta que aparezca un formulario (la sala de espera libera
    plazas en cualquier momento)."""
    limite = time.monotonic() + ESPERA_FORMULARIO
    intento = 0
    while time.monotonic() < limite:
        intento += 1
        pagina.goto(url, wait_until="domcontentloaded", timeout=30000)
        rechazar_cookies(pagina)
        controles = pagina.evaluate(JS_CONTROLES)
        utiles = [c for c in controles if c["tipo"] not in ("checkbox", "radio")]
        if utiles:
            return controles
        texto = pagina.inner_text("body")[:200].replace("\n", " ")
        log(f"Intento {intento}: sin formulario ({texto[:70]}…). Reintento.")
        time.sleep(2)
    return None


def rellenar(pagina, controles: list[dict]) -> list[str]:
    """Rellena lo que reconoce. Devuelve lista de problemas (vacía = todo bien)."""
    problemas: list[str] = []
    for c in controles:
        sel = pagina.locator(f'[data-hw="{c["i"]}"]')
        descripcion = c["etiqueta"].strip() or c["nombre"] or c["id"] or c["placeholder"] or c["tipo"]
        descripcion = " ".join(descripcion.split())[:50]

        if c["tipo"] == "checkbox":
            texto = f'{c["etiqueta"]} {c["nombre"]} {c["id"]}'
            if TEXTO_CONDICIONES.search(texto):
                if ACEPTAR_CONDICIONES:
                    sel.check(force=True)
                    log(f"☑ Condiciones marcadas: {descripcion}")
                elif c["obligatorio"] and not c["marcado"]:
                    problemas.append(f"casilla de condiciones sin marcar ({descripcion})")
            elif c["obligatorio"] and not c["marcado"]:
                problemas.append(f"casilla obligatoria no reconocida ({descripcion})")
            continue
        if c["tipo"] == "radio":
            continue

        clave = clasificar(c)
        valor = DATOS.get(clave, "") if clave else ""
        if not clave:
            if c["obligatorio"] and not c["valor"]:
                problemas.append(f"campo obligatorio no reconocido ({descripcion})")
            else:
                log(f"· Campo sin reconocer, lo dejo vacío: {descripcion}")
            continue
        if not valor:
            problemas.append(f"falta en .env el dato para «{clave}» ({descripcion})")
            continue

        if c["tag"] == "select":
            elegido = next((o["v"] for o in c["opciones"]
                            if o["t"].strip() == valor or o["v"] == valor), None)
            if elegido is None:
                elegido = next((o["v"] for o in c["opciones"]
                                if re.search(rf"\b{re.escape(valor)}\b", o["t"])), None)
            if elegido is None:
                problemas.append(f"no encuentro la opción «{valor}» en «{descripcion}»")
                continue
            sel.select_option(elegido)
        else:
            sel.fill(valor)
        log(f"✍ {clave}: {descripcion}")
    return problemas


def principal(url: str) -> int:
    from playwright.sync_api import sync_playwright

    faltan = [k for k in ("nombre", "dni", "telefono", "email") if not DATOS[k]]
    if faltan:
        log(f"⚠ Faltan datos en .env: {', '.join(faltan)}. Solo abriré la página.")

    with sync_playwright() as p:
        navegador = abrir_navegador(p)
        pagina = navegador.new_page(viewport={"width": 1100, "height": 900})
        log(f"Abriendo {url}")
        controles = esperar_formulario(pagina, url)

        if controles is None:
            guardar_captura(pagina, "sin-formulario")
            enviar_mensaje("⌛ Abrí la página pero la plaza ya no estaba "
                           "(sigue la sala de espera). Sigo vigilando.")
            navegador.close()
            return 1

        log(f"Formulario detectado con {len(controles)} controles: " + "; ".join(
            f'{c["tag"]}:{c["tipo"]}:{c["nombre"] or c["id"]}' for c in controles))
        problemas = rellenar(pagina, controles) if not faltan else ["faltan datos en .env"]
        captcha = hay_captcha(pagina)
        foto = guardar_captura(pagina, "formulario-rellenado")

        if captcha:
            problemas.append("hay captcha: lo tienes que resolver tú")

        if problemas:
            msg = ("⚠️ Formulario abierto, pero NO lo envío:\n• " + "\n• ".join(problemas)
                   + f"\n\n🔗 {url}")
            enviar_foto(str(foto), msg)
            log("No envío: " + "; ".join(problemas))
            if not HEADLESS:
                log("Dejo la ventana abierta para que lo completes tú.")
                try:
                    pagina.wait_for_event("close", timeout=15 * 60 * 1000)
                except Exception:  # noqa: BLE001
                    pass
            navegador.close()
            return 2

        enviar_foto(str(foto), f"✍️ Formulario RELLENADO. Falta que tú pulses Enviar.\n🔗 {url}")
        log("Rellenado. Pulsa Enviar tú cuando quieras (cierra la ventana al terminar).")
        if not HEADLESS:
            try:
                pagina.wait_for_event("close", timeout=15 * 60 * 1000)
            except Exception:  # noqa: BLE001
                pass
        navegador.close()
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/reservar.py <url del evento>")
        sys.exit(64)
    sys.exit(principal(sys.argv[1]))
