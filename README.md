# El Hormiguero Ticket Watcher

Bot para monitorizar la disponibilidad de entradas de público de El Hormiguero y enviar alertas por Telegram cuando aparezcan plazas disponibles.

## Modo PC (Windows) — recomendado

Lo lanzas tú cuando quieras y se queda funcionando en una ventana, revisa
`https://entradas.7yaccion.com/` **cada 15 segundos** y, cuando un evento tiene plazas:

1. Te manda 3 mensajes de Telegram con día, hora y enlace directo.
2. Abre la página del evento en tu navegador para que rellenes el formulario.

### Cómo lanzarlo (a mano)

Doble clic en **`INICIAR VIGILANTE.bat`** (en la raíz del proyecto).

- La primera vez instala lo necesario (Python si falta, dependencias), te pide el
  **token del bot** y tu **chat id** de Telegram, los guarda en `.env` y envía un
  Telegram de prueba.
- Después se queda funcionando en esa ventana, mostrando cada comprobación.
- **Para pararlo, cierra la ventana.** No arranca solo con Windows.

Otros: `windows\probar_telegram.bat` (mensaje de prueba), `windows\ver_log.bat` (historial).

### Avisos en el iPhone

Cada alerta de Telegram lleva el enlace y un botón **🎟️ ABRIR FORMULARIO**: tocándolo
se abre la página directamente en el iPhone. Para que el aviso no pase desapercibido,
en el iPhone: Ajustes → Notificaciones → Telegram → *Sonidos* y *Avisos urgentes*, y en
tu modo Concentración (No molestar/Sueño) permite las notificaciones de Telegram.

### Rellenado automático del formulario (en el PC)

Las plazas pueden aparecer solo 1–2 minutos, así que el PC puede hacerlo por ti:

1. Doble clic en **`CONFIGURAR FORMULARIO.bat`** → te pregunta tus datos (se guardan solo en `.env`)
   si quieres que rellene solo, si marca la casilla de condiciones, y qué días ignorar
   (la web no publica el invitado: si ya sabes qué días no te interesan, no te avisará de ellos).
2. Al detectar plazas abre Edge/Chrome, espera en la sala de espera si hace falta,
   rellena el formulario y te manda a Telegram una **captura** del resultado.
3. **No envía nunca**: lo deja rellenado y el botón *Enviar* lo pulsas tú, si te gusta el invitado.
   Si hay captcha o un campo que no reconoce, te avisa con la captura.
4. Cada intento guarda captura y HTML en `datos\capturas\` para poder ajustarlo.

> La solicitud solo vale si luego recibes la llamada de confirmación.

### ¿Cómo sé que está comprobando y no le bloquean?

- **En la ventana**: cada minuto escribe `✅ Web leída correctamente` y el estado de
  cada evento. Si algo falla escribe `❌ NO SE PUEDE LEER LA WEB` o `⚠️ Lectura dudosa`
  con el motivo (HTTP 403/429, página antibots, sin internet, web cambiada…).
- **En el título de la ventana** (barra de tareas): `OK, ultima comprobacion HH:MM`
  o `ATENCION: <motivo>`.
- **Por Telegram**: un resumen cada 3 h ("🟢 Sigo vigilando…") y un aviso si lleva
  10 min sin poder leer bien la web ("⚠️ … NO te puedo avisar de plazas").

Ajustes en `.env` (horario, intervalo, abrir navegador…): ver `configuracion_ejemplo.txt`.
Tras cambiar `.env`, cierra la ventana y vuelve a lanzarlo.

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
- [x] Modo PC continuo, lanzado a mano en Windows
- [ ] Añadir una segunda comprobación independiente antes de una alerta
- [ ] Probar el comportamiento real cuando aparezca una plaza
