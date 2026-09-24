# El Hormiguero Ticket Watcher

Bot para monitorizar la disponibilidad de entradas de público de El Hormiguero y enviar alertas por Telegram cuando aparezcan plazas disponibles.

## Estado del proyecto

🚧 En desarrollo.

## Objetivo

Comprobar periódicamente las páginas oficiales de los eventos y detectar cambios reales de disponibilidad.

La página individual del evento será la fuente de verdad para determinar si hay plazas disponibles.

## Reglas de vigilancia

- Se comprueban todos los eventos que aparezcan en la web principal; no se descartan por fecha.
- Un evento agotado se sigue vigilando, porque pueden liberarse plazas posteriormente.
- La web principal sirve para descubrir eventos; la página individual sirve para confirmar la disponibilidad.
- Un resultado DESCONOCIDO no sustituye al último estado confirmado y nunca genera una alerta.
- La primera disponibilidad confirmada genera una alerta.
- Tras una alerta, se vuelve a avisar si el evento continúa disponible cuando hayan pasado 15 minutos desde la última alerta.
- El intervalo de 15 minutos es independiente para cada evento.
- Si un evento pasa a agotado, dejan de enviarse alertas hasta que vuelva a estar disponible.
- Si un evento desaparece de la web principal, deja de formar parte de la vigilancia activa, aunque su historial se conserva.

## Próximos pasos

- [ ] Investigar y documentar la estructura actual de la web
- [ ] Implementar detección de eventos
- [ ] Implementar detección de disponibilidad
- [ ] Implementar persistencia de estado
- [ ] Integrar alertas de Telegram
- [ ] Configurar GitHub Actions
- [ ] Añadir histórico de cambios
- [ ] Añadir pruebas
