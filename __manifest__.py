{
    'name': 'Bitópolis Kitchen Display System',
    'version': '19.0.4.0.2',
    'category': 'Point of Sale',
    'summary': 'KDS reactivo plug-and-play para Odoo POS — estilo Loyverse',
    'description': """
Bitópolis KDS v3
================
- Dashboard en el backend de Odoo (como POS): estaciones + configuración.
- Ventana KDS simplificada: solo órdenes y completado.
- Multi-estación: filtro por categoría POS configurado desde el backend.
- Cronómetro con colores configurables desde el dashboard.
- Bandeja de deshacer + teclado numérico USB.
- Sonido en nueva orden (Web Audio API).
- Tiempo real: bus.bus + polling de respaldo.
    """,
    'author': 'Bitópolis',
    'website': 'https://bitopolis.cc',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'bus', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/kds_menu_views.xml',
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
