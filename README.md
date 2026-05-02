# 🍳 Bitópolis KDS — Kitchen Display System for Odoo 19

> **Demo addon.** This version is limited to 1 station and 2 POS categories.  
> Developed and used in production by [Bitópolis](https://bitopolis.cc).

🌐 [Leer en Español](README.es.md)

---
<img width="1065" height="431" alt="{30C7FA08-9126-4B2A-99E1-176256DE8004}" src="https://github.com/user-attachments/assets/55f84e5b-e989-4314-80aa-a89134b8bcdf" />

## What does it do?

A reactive Kitchen Display System (KDS) for Odoo 19 POS, Loyverse-style. POS orders appear automatically on the kitchen screen, with a color-coded timer and order completion via touch or USB numpad.

### Features

- **Backend dashboard** — station management + global timer configuration
- **Standalone KDS window** — opens at `/kds/ui`, designed to run on a kitchen tablet/TV
- **Real-time** via `bus.bus` + configurable fallback polling
- **Color-coded timer** — green / yellow / red, configurable from the dashboard
- **Mark order as done** — by touch or USB numpad (`number` + `Enter`)
- **Undo tray** — recover accidentally completed orders
- **Sound on new order** — via Web Audio API (configurable)
- **POS category filter** — station only shows products assigned to it

---

## Limitations (demo version)

| Feature | This version |
|---|---|
| Stations per company | **Maximum 1** |
| POS categories per station | **Maximum 2** |
| Create new stations from dashboard | ❌ Disabled |

---

## Requirements

- **Odoo 19**
- Modules: `base`, `web`, `bus`, `point_of_sale`
- Optional: `pos_restaurant` (auto-detection of table/order number)

---

## Installation

```bash
# 1. Clone or copy the folder into your Odoo addons directory
git clone https://github.com/elfenick/odoo-kds /path/to/odoo/addons/bitopolis_kds

# 2. Restart Odoo
sudo systemctl restart odoo

# 3. In Odoo: Settings → Update Apps List
# 4. Search for "Bitópolis Kitchen Display System" and install
```

---

## Basic usage

1. A new **Kitchen (KDS)** app appears in the main menu
2. Open the dashboard → you'll see the station and global config
3. Click **▶ Open KDS** → opens `/kds/ui` in a new tab (use this on the kitchen tablet)
4. POS orders appear automatically after payment

### Completing an order

| Method | Action |
|---|---|
| Touch | Green **"Done"** button on the card |
| USB numpad | Order number → `Enter` or `+` |
| Undo completed order | Number → `-` or `Backspace` |

### Timer colors (configurable)

| Time in kitchen | Color |
|---|---|
| Below yellow threshold | 🟢 Green |
| Between yellow and red | 🟡 Yellow |
| Above red threshold | 🔴 Red (blinking) |

---

## Configuration

From the **Dashboard → Edit**:

| Setting | Description |
|---|---|
| Minutes to Yellow | Time before card turns yellow |
| Minutes to Red | Time before card turns red |
| Fallback polling | Seconds between polls (minimum 5s) |
| Undo tray size | How many recent orders can be recovered |
| Sound on new order | Enable/disable beep when an order arrives |

---

## Project structure

```
bitopolis_kds/
├── controllers/
│   └── main.py              # HTTP routes: /kds/ui, /kds/dashboard, /kds/config/save, etc.
├── models/
│   ├── kds_config.py        # Global config model
│   ├── kds_station.py       # KDS station model
│   ├── kds_order.py         # KDS order model
│   ├── kds_order_line.py    # Order lines
│   ├── kds_order_done.py    # Completed orders (history)
│   └── pos_order.py         # Hook on pos.order to auto-create kds.order
├── static/src/
│   ├── app/                 # Standalone KDS OWL app (/kds/ui)
│   └── dashboard/           # Odoo backend OWL dashboard
├── views/
│   ├── kds_menu_views.xml   # Menus, station list/form and order history views
│   └── kds_templates.xml    # QWeb template for /kds/ui
└── security/
    └── ir.model.access.csv
```

---

## Technical notes

- HTTP routes use `sudo()` to bypass ACL — designed for local network use
- The creation hook is in `pos_order.py` overriding `pos.order.create()`
- Table/tracking field detection uses `_fields` for compatibility across POS versions
- The standalone KDS bundle (`bitopolis_kds.assets_kds`) loads `web.assets_web` without compiling SCSS — compatible with Windows Server

---

## License

[LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html)

---

*Made with ☕ by [Bitópolis](https://bitopolis.cc) — Tijuana, BC, México*
