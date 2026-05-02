# 🍳 Bitópolis KDS — Kitchen Display System para Odoo 19

> **Addon de demostración.** Esta versión está limitada a 1 estación y 2 categorías POS.  
> Desarrollado y usado en producción por [Bitópolis](https://bitopolis.cc).

🌐 [Read in English](README.md)

---

## ¿Qué hace?

Un Kitchen Display System (KDS) reactivo para Odoo 19 POS, estilo Loyverse. Las órdenes del POS aparecen automáticamente en pantalla de cocina, con cronómetro de colores y marcado por toque o teclado numérico USB.

### Funcionalidades

- **Dashboard en el backend de Odoo** — estación + configuración global de tiempos
- **Ventana KDS standalone** — se abre en `/kds/ui`, pensada para correr en tablet/TV de cocina
- **Tiempo real** via `bus.bus` + polling de respaldo configurable
- **Cronómetro con colores** — verde / amarillo / rojo configurable desde el dashboard
- **Marcar orden como lista** — por touch en pantalla o teclado numérico USB (`número` + `Enter`)
- **Bandeja de deshacer** — recupera órdenes marcadas por error
- **Sonido en nueva orden** — via Web Audio API (configurable)
- **Filtro por categoría POS** — la estación solo muestra los productos que le corresponden

---

## Limitaciones de esta versión (demo)

| Funcionalidad | Esta versión |
|---|---|
| Estaciones por empresa | **Máximo 1** |
| Categorías POS por estación | **Máximo 2** |
| Crear nuevas estaciones desde el dashboard | ❌ Deshabilitado |

---

## Requisitos

- **Odoo 19**
- Módulos: `base`, `web`, `bus`, `point_of_sale`
- Opcional: `pos_restaurant` (detección automática de mesa/número de orden)

---

## Instalación

```bash
# 1. Clona o copia la carpeta en tu directorio de addons de Odoo
git clone https://github.com/elfenick/odoo-kds /path/to/odoo/addons/bitopolis_kds

# 2. Reinicia Odoo
sudo systemctl restart odoo

# 3. En Odoo: Configuración → Actualizar lista de aplicaciones
# 4. Busca "Bitópolis Kitchen Display System" e instala
```

---

## Uso básico

1. En el menú principal aparece la app **Cocina (KDS)**
2. Abre el dashboard → verás la estación y la configuración global
3. Click en **▶ Abrir KDS** → se abre `/kds/ui` en una pestaña nueva (úsala en la tablet de cocina)
4. Las órdenes del POS aparecen automáticamente al pagar

### Marcar orden como lista

| Método | Acción |
|---|---|
| Touch | Botón verde **"Listo"** en la tarjeta |
| Teclado numérico USB | Número de orden → `Enter` o `+` |
| Deshacer orden completada | Número → `-` o `Backspace` |

### Colores del cronómetro (configurables)

| Tiempo en cocina | Color |
|---|---|
| Menos del umbral amarillo | 🟢 Verde |
| Entre amarillo y rojo | 🟡 Amarillo |
| Más del umbral rojo | 🔴 Rojo (parpadea) |

---

## Configuración

Desde el **Dashboard → Editar**:

| Parámetro | Descripción |
|---|---|
| Minutos hasta Amarillo | Tiempo para que la tarjeta cambie a amarillo |
| Minutos hasta Rojo | Tiempo para que la tarjeta cambie a rojo |
| Polling de respaldo | Segundos entre polls (mínimo 5s) |
| Órdenes en bandeja deshacer | Cuántas órdenes recientes se pueden recuperar |
| Sonido en nueva orden | Activa/desactiva el beep al llegar una orden |

---

## Estructura del proyecto

```
bitopolis_kds/
├── controllers/
│   └── main.py              # Rutas HTTP: /kds/ui, /kds/dashboard, /kds/config/save, etc.
├── models/
│   ├── kds_config.py        # Modelo de configuración global
│   ├── kds_station.py       # Modelo de estación KDS
│   ├── kds_order.py         # Modelo de orden KDS
│   ├── kds_order_line.py    # Líneas de orden
│   ├── kds_order_done.py    # Órdenes completadas (historial)
│   └── pos_order.py         # Hook en pos.order para crear kds.order automáticamente
├── static/src/
│   ├── app/                 # OWL app standalone del KDS (/kds/ui)
│   └── dashboard/           # OWL dashboard del backend de Odoo
├── views/
│   ├── kds_menu_views.xml   # Menús, vistas lista/form de estaciones e historial
│   └── kds_templates.xml    # Plantilla QWeb para /kds/ui
└── security/
    └── ir.model.access.csv
```

---

## Notas técnicas

- Las rutas HTTP usan `sudo()` para evitar problemas de ACL — diseñado para red local
- El hook de creación está en `pos_order.py` sobreescribiendo `create()` de `pos.order`
- La detección de campos de mesa/tracking usa `_fields` para ser compatible con distintas versiones de POS
- El bundle KDS standalone (`bitopolis_kds.assets_kds`) carga `web.assets_web` sin compilar SCSS, compatible con Windows Server

---

## Licencia

[LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html)

---

*Hecho con ☕ por [Bitópolis](https://bitopolis.cc) — Tijuana, BC, México*
