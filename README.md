# El Hormiguero Ticket Watcher

Bot para monitorizar la disponibilidad de entradas de público de El Hormiguero y enviar alertas por Telegram cuando aparezcan plazas disponibles.

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
- La vigilancia automática está activa entre **07:00 y 23:00, hora de España**. Fuera de ese horario no se ejecuta el vigilante.

## Frecuencia

- GitHub Actions inicia una ejecución programada cada 5 minutos durante la ventana de vigilancia.
- Cada ejecución activa realiza comprobaciones aproximadamente cada 55 segundos durante unos 4 minutos.
- También existe ejecución manual para pruebas.

## Alertas de Telegram

Cuando se confirma disponibilidad, se envían 3 mensajes consecutivos con los datos del evento y el enlace directo.

## Estado persistente

Solo se guarda la hora del último aviso por evento en `datos/estado.json`. No se mantiene un histórico de comprobaciones.

## Pendiente

- [ ] Mejorar extracción de fecha, hora e invitado
- [ ] Añadir una segunda comprobación independiente antes de una alerta
- [ ] Probar el comportamiento real cuando aparezca una plaza
