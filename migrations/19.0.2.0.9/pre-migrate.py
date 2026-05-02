# -*- coding: utf-8 -*-
"""
Migración 19.0.2.0.9 — Bitópolis KDS
- Crea tablas kds_config y kds_station si no existen.
- Limpia __pycache__ del módulo para evitar código Python obsoleto.
"""
import logging
import os
import shutil

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Bitópolis KDS: iniciando migración...")

    # ------------------------------------------------------------------ #
    # Limpiar __pycache__ para forzar recompilación de Python             #
    # ------------------------------------------------------------------ #
    addon_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for root, dirs, files in os.walk(addon_path):
        for d in dirs:
            if d == '__pycache__':
                try:
                    shutil.rmtree(os.path.join(root, d))
                    _logger.info("KDS: limpiado pycache en %s", root)
                except Exception as e:
                    _logger.warning("KDS: no se pudo limpiar pycache: %s", e)

    # ------------------------------------------------------------------ #
    # kds_config                                                           #
    # ------------------------------------------------------------------ #
    cr.execute("""
        CREATE TABLE IF NOT EXISTS kds_config (
            id              SERIAL PRIMARY KEY,
            company_id      INTEGER REFERENCES res_company(id) ON DELETE SET NULL,
            warn_minutes    INTEGER DEFAULT 5,
            danger_minutes  INTEGER DEFAULT 15,
            sound_enabled   BOOLEAN DEFAULT TRUE,
            poll_interval   INTEGER DEFAULT 5,
            undo_count      INTEGER DEFAULT 5,
            create_uid      INTEGER REFERENCES res_users(id) ON DELETE SET NULL,
            write_uid       INTEGER REFERENCES res_users(id) ON DELETE SET NULL,
            create_date     TIMESTAMP WITHOUT TIME ZONE,
            write_date      TIMESTAMP WITHOUT TIME ZONE
        )
    """)

    # ------------------------------------------------------------------ #
    # kds_station                                                          #
    # ------------------------------------------------------------------ #
    cr.execute("""
        CREATE TABLE IF NOT EXISTS kds_station (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR NOT NULL DEFAULT '',
            sequence    INTEGER DEFAULT 10,
            company_id  INTEGER REFERENCES res_company(id) ON DELETE SET NULL,
            show_all    BOOLEAN DEFAULT FALSE,
            active      BOOLEAN DEFAULT TRUE,
            color       INTEGER DEFAULT 0,
            create_uid  INTEGER REFERENCES res_users(id) ON DELETE SET NULL,
            write_uid   INTEGER REFERENCES res_users(id) ON DELETE SET NULL,
            create_date TIMESTAMP WITHOUT TIME ZONE,
            write_date  TIMESTAMP WITHOUT TIME ZONE
        )
    """)

    cr.execute("""
        CREATE TABLE IF NOT EXISTS kds_station_pos_category_rel (
            station_id  INTEGER NOT NULL
                REFERENCES kds_station(id)  ON DELETE CASCADE,
            category_id INTEGER NOT NULL
                REFERENCES pos_category(id) ON DELETE CASCADE,
            PRIMARY KEY (station_id, category_id)
        )
    """)

    _logger.info("Bitópolis KDS: migración completada.")
