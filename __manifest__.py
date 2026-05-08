{
    'name': 'Bitópolis Kitchen Display System',
    'version': '19.0.5.0.0',
    'category': 'Point of Sale',
    'summary': 'Kitchen Display System nativo para Odoo 19 POS — tiempo real, multi-estación y licencia por instalación',
    'description': """
Bitópolis KDS v5
================

Kitchen Display System nativo para Odoo 19 POS.
Las órdenes del POS aparecen en pantalla de cocina al instante.

Funcionalidades:
- Dashboard en el backend: gestión de estaciones y configuración global.
- Pantalla KDS standalone en /kds/ui — ideal para tablet o TV de cocina.
- Multi-estación con filtro por categoría POS.
- Cronómetro con colores (verde / amarillo / rojo) configurables.
- Resaltado visual de modificadores y notas de preparación.
- Marcar orden como lista por touch o teclado numérico USB.
- Bandeja de deshacer para recuperar órdenes marcadas por error.
- Sonido configurable en nueva orden (Web Audio API).
- Tiempo real via WebSocket + polling de respaldo configurable.
- Detección automática de desconexión con banner de alerta.
- Recuperación automática de órdenes offline al reconectarse.
- Sistema de licencia por instalación — pago único, sin mensualidades.

Versión demo incluida: 1 estación General gratuita.
Licencia completa: bitopolis.cc
    """,
    'author': 'Bitópolis',
    'website': 'https://bitopolis.cc',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'bus', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/kds_menu_views.xml',
        'views/kds_license_views.xml',
        'views/kds_templates.xml',
    ],
    'assets': {
        # Bundle KDS standalone (/kds/ui)
        # Solo nuestro CSS plano + nuestro JS.
        # web.assets_web (que tiene OWL+servicios) se carga desde la
        # plantilla con t-css=false para evitar compilar SCSS en Windows.
        'bitopolis_kds.assets_kds': [
            'bitopolis_kds/static/src/app/kds_app.css',
            'bitopolis_kds/static/src/app/kds_main.js',
            'bitopolis_kds/static/src/app/kds_app.js',
            'bitopolis_kds/static/src/app/kds_app.xml',
            'bitopolis_kds/static/src/app/order_card.js',
            'bitopolis_kds/static/src/app/order_card.xml',
        ],
        # Dashboard en el backend de Odoo
        'web.assets_backend': [
            'bitopolis_kds/static/src/dashboard/kds_dashboard.css',
            'bitopolis_kds/static/src/dashboard/kds_dashboard.js',
            'bitopolis_kds/static/src/dashboard/kds_dashboard.xml',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
}
