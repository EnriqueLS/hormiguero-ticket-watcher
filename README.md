# El Hormiguero Ticket Watcher

Bot para monitorizar la disponibilidad de entradas de público de El Hormiguero y enviar alertas por Telegram cuando aparezcan plazas disponibles.

## Modo PC (Windows) — recomendado

El vigilante se queda funcionando en segundo plano en tu PC, revisa
`https://entradas.7yaccion.com/` **cada minuto** y, cuando un evento tiene plazas:

1. Te manda 3 mensajes de Telegram con día, hora y enlace directo.
2. Abre la página del evento en tu navegador para que rellenes el formulario.

### Instalación (una sola vez)

1. Descarga o clona este repositorio en una carpeta (p. ej. `Documentos\hormiguero-ticket-watcher`).
2. Doble clic en **`windows\instalar.bat`**. Hace todo:
   - instala Python si no lo tienes (con winget) y las dependencias,
   - te pide el **token del bot** y tu **chat id** de Telegram y los guarda en `.env`,
   - envía un Telegram de prueba,
   - lo añade al **arranque de Windows** y lo lanza ya.

### Uso diario

| Archivo | Para qué |
|---|---|
| `windows\ver_log.bat` | Ver en directo lo que va comprobando |
| `windows\detener.bat` | Pararlo |
| `windows\arrancar.bat` | Volver a lanzarlo sin reiniciar |
| `windows\probar_telegram.bat` | Enviar un mensaje de prueba |
| `windows\desinstalar.bat` | Pararlo y quitarlo del arranque |

Ajustes en `.env` (horario, intervalo, abrir navegador…): ver `configuracion_ejemplo.txt`.
Tras cambiar `.env`, ejecuta `detener.bat` y luego `arrancar.bat`.

> El PC tiene que estar encendido, con sesión iniciada y **sin suspensión**
> (Configuración → Sistema → Inicio/apagado → Suspender: Nunca, al menos enchufado).

## Reglas de vigilancia

- Se comprueban todos los eventos que aparezcan en la web principal; no se descartan por fecha.
- Un evento agotado se sigue vigilando, porque pueden liberarse plazas posteriormente.
- La web principal sirve para descubrir eventos; la página individual sirve para confirmar la disponibilidad.
- Un resultado DESCONOCIDO no genera una alerta y conserva el último aviso conocido.
- La primera disponibilidad confirmada genera una alerta.
- Tras una alerta, se vuelve a avisar si el evento continúa disponible cuando hayan pasado **10 minutos** desde la última alerta.
- El intervalo de 10 minutos es independiente para cada evento.
- Si un evento pasa a agotado, se elimina su último aviso; si vuelve a estar disponible, puede generar una alerta inmediatamente.
- Si un evento desaparece de la web principal, deja de formar parte del estado activo.
- Si la web principal falla temporalmente, el estado anterior se conserva para evitar falsas re-alertas.
- La vigilancia automática está activa entre **07:00 y 23:00, hora de España** (configurable en `.env`; `HORA_INICIO=0` y `HORA_FIN=0` = 24 h).
- Si la web no responde durante 30 minutos seguidos, avisa por Telegram (y otra vez cuando vuelve).
- Solo puede haber un vigilante funcionando a la vez (evita avisos dobles).

## Frecuencia

- Modo PC: cada 60 segundos (configurable con `INTERVALO_SEGUNDOS`).
- GitHub Actions: la ejecución programada está desactivada para no duplicar avisos; queda la ejecución manual.

## Alertas de Telegram

Cuando se confirma disponibilidad, se envían 3 mensajes consecutivos con los datos del evento y el enlace directo.

## Estado persistente

Solo se guarda la hora del último aviso por evento en `datos/estado.json`. No se mantiene un histórico de comprobaciones.

## Pendiente

- [x] Extracción de fecha y hora (la web no publica el invitado)
- [x] Modo PC continuo con arranque automático en Windows
- [ ] Añadir una segunda comprobación independiente antes de una alerta
- [ ] Probar el comportamiento real cuando aparezca una plaza
