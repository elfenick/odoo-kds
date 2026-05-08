# -*- coding: utf-8 -*-
"""
Agrega columnas de teclas numpad a kds_config si no existen.
Se ejecuta automáticamente al hacer Update del módulo.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE kds_config
            ADD COLUMN IF NOT EXISTS key_nav_up    VARCHAR DEFAULT 'Numpad8',
            ADD COLUMN IF NOT EXISTS key_nav_down  VARCHAR DEFAULT 'Numpad5',
            ADD COLUMN IF NOT EXISTS key_nav_left  VARCHAR DEFAULT 'Numpad4',
            ADD COLUMN IF NOT EXISTS key_nav_right VARCHAR DEFAULT 'Numpad6',
            ADD COLUMN IF NOT EXISTS key_complete  VARCHAR DEFAULT 'NumpadEnter',
            ADD COLUMN IF NOT EXISTS key_undo      VARCHAR DEFAULT 'NumpadSubtract'
    """)
