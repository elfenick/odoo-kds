# Bitópolis KDS — Kitchen Display System para Odoo 19

Plug & play. Cero configuración.

## Instalación

1. Copia la carpeta `bitopolis_kds/` a tu directorio de addons de Odoo.
2. Reinicia el servicio de Odoo.
3. En Odoo: **Aplicaciones → Actualizar lista de aplicaciones**.
4. Busca **"Bitópolis Kitchen Display System"** e instala.

## Uso

1. En el menú principal verás una nueva app: **Cocina**.
2. Click en **Abrir KDS** → se abre `/kds/ui` en una pestaña nueva (igual que el POS).
3. Las órdenes pagadas/enviadas desde el POS aparecen automáticamente.
4. Para marcar como lista:
   - **Touch:** botón verde "Listo" en la tarjeta.
   - **Numpad USB:** teclea el número de la orden y presiona `Enter` o `+`.

## Lógica de colores (cronómetro)

| Tiempo en cocina | Color |
|---|---|
| < 5 min | 🟢 Verde |
| 5–15 min | 🟡 Amarillo |
| > 15 min | 🔴 Rojo (parpadea) |

## Requisitos

- Odoo 19
- Módulos: `base`, `web`, `bus`, `point_of_sale`
- Opcional: `pos_restaurant` (detección automática de mesa)

## Notas técnicas

- **Tiempo real:** `bus.bus` con canal por compañía + polling de respaldo cada 15s.
- **Hook de creación:** se sobrescribe `pos.order.create()` para crear `kds.order` automáticamente sin tocar el POS frontend.
- **Compatibilidad:** los nombres de campos de POS (tracking_number, customer_note, table_id) varían entre minor versions; el código usa `_fields` para fallback defensivo.

## Personalización

- **Umbrales de color:** edita `WARN_AT_SECONDS` y `DANGER_AT_SECONDS` en `static/src/app/order_card.js`.
- **Estilos:** todo en `static/src/app/kds_app.scss` (variables al inicio).
- **Polling:** `POLL_INTERVAL_MS` en `static/src/app/kds_app.js`.

## Soporte

[bitopolis.cc](https://bitopolis.cc)

## Licencia

LGPL-3
