# El Hormiguero Ticket Watcher

Vigila la web de entradas de público de El Hormiguero (`entradas.7yaccion.com`) y te avisa por Telegram cuando de verdad se puede solicitar una entrada.

Está pensado para dejarlo funcionando en un PC con Windows. Se ejecuta en segundo plano y arranca solo al iniciar sesión.

## Cómo decide si hay entradas

1. Lee la web principal y recoge todos los enlaces `/evento/...`.
2. Entra en cada evento y lo clasifica:
   - **AGOTADO** si aparece un mensaje como «no hay plazas», «entradas agotadas», «aforo completo»… (aunque la fecha salga abierta en la portada).
   - **DISPONIBLE** solo si no hay ese mensaje **y** hay un formulario real con al menos dos campos para rellenar.
   - **DESCONOCIDO** en cualquier otro caso. Nunca genera alerta.
3. Antes de avisar, vuelve a leer la página a los 5 segundos. Solo avisa si la segunda lectura también dice DISPONIBLE.

## Avisos de Telegram

| Situación | Mensaje |
|---|---|
| Entradas disponibles confirmadas | 3 mensajes seguidos con el enlace; se repite cada 10 min mientras siga abierto |
| El evento se agota y vuelve a abrirse | Aviso inmediato |
| La web principal no responde durante 30 min | Un aviso de fallo y otro cuando se recupera |
| Un evento está en DESCONOCIDO 3 comprobaciones seguidas | Un aviso para que lo revises (posible cambio de la web) |
| El vigilante arranca | «Vigilante Hormiguero arrancado» |

## Frecuencia

Comprueba cada 2 minutos entre las 07:00 y las 23:00 (hora de Madrid). Fuera de ese horario duerme. Todo esto se puede cambiar en `.env`.

## Instalación en Windows

1. Instala [Python 3.10 o superior](https://www.python.org/downloads/) y marca **«Add python.exe to PATH»**.
2. Descarga este repositorio (`git clone` o «Code → Download ZIP») en una carpeta fija, por ejemplo `C:\hormiguero-ticket-watcher`.
3. Haz doble clic en **`windows\instalar.bat`**. El script:
   - crea el entorno `.venv` e instala las dependencias;
   - abre el Bloc de notas con `.env` para que pongas `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`;
   - pasa las pruebas, te manda un Telegram de prueba y hace una comprobación de la web;
   - registra la tarea programada **VigilanteHormiguero**, que arranca al iniciar sesión, se reinicia sola si se cae y no tiene límite de tiempo.
4. Configura Windows para que el PC **no entre en suspensión**: *Configuración → Sistema → Inicio/apagado y suspensión → Suspender: Nunca*. Bloquear la pantalla no importa; apagar o suspender el equipo, sí.

### Obtener el token y el chat ID

- **Token:** habla con [@BotFather](https://t.me/BotFather) y usa `/newbot`. Si ya tenías el bot, es el mismo token que usabas en los secretos de GitHub.
- **Chat ID:** mándale cualquier mensaje a tu bot y abre `https://api.telegram.org/bot<TOKEN>/getUpdates`. El número que aparece en `"chat":{"id": ...}` es tu chat ID.

### Uso diario

- `windows\ver-log.bat`: muestra en directo lo que está haciendo.
- `windows\desinstalar.bat`: para y elimina la tarea programada.
- Para reiniciarlo tras actualizar el código: Programador de tareas → VigilanteHormiguero → Finalizar → Ejecutar, o vuelve a lanzar `instalar.bat`.

### Comandos manuales

```powershell
.venv\Scripts\python src\vigilante.py --una-vez          # una comprobación, sin enviar avisos
.venv\Scripts\python src\vigilante.py --probar-telegram  # mensaje de prueba
.venv\Scripts\python src\vigilante.py --diagnosticar     # analiza la web y guarda el HTML en logs\
.venv\Scripts\python src\vigilante.py --diagnosticar https://entradas.7yaccion.com/evento/XXX
.venv\Scripts\python -m unittest discover -s pruebas -p "test_*.py"
```

`--diagnosticar` indica, para cada evento, qué frases de «sin plazas» ha encontrado y cuántos campos tiene cada formulario. Si alguna vez llega un aviso falso, o uno de «no sé si este evento tiene plazas», ejecútalo y revisa el HTML guardado en `logs\`. Normalmente basta con añadir la frase nueva a `FRASES_AGOTADO` en `src/rascador.py`.

## Estructura

```
src/vigilante.py   bucle principal, decisiones de aviso y comandos
src/rascador.py    descarga y clasificación de la web
src/telegram.py    envío de mensajes
src/estado.py      estado persistente (datos/estado.json)
src/config.py      lectura de .env
windows/           instalación como tarea programada
pruebas/           pruebas automáticas (sin red)
```
