# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KdsConfig(models.Model):
    _name = 'kds.config'
    _description = 'Bitópolis KDS Configuration'

    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    warn_minutes = fields.Integer(
        'Minutos hasta Amarillo', default=5,
    )
    danger_minutes = fields.Integer(
        'Minutos hasta Rojo', default=15,
    )
    sound_enabled = fields.Boolean(
        'Sonido en nueva orden', default=True,
    )
    poll_interval = fields.Integer(
        'Intervalo de polling (seg)', default=5,
    )
    undo_count = fields.Integer(
        'Órdenes en bandeja de deshacer', default=5,
    )
    font_size = fields.Char('Tamaño de fuente (px)', default='17')
    sound_volume = fields.Float('Volumen de notificación', default=1.0)

    # ── Teclas Numpad (ev.code) ──────────────────────────────────────────────
    key_nav_up    = fields.Char('Tecla Arriba',     default='Numpad8')
    key_nav_down  = fields.Char('Tecla Abajo',      default='Numpad5')
    key_nav_left  = fields.Char('Tecla Izquierda',  default='Numpad4')
    key_nav_right = fields.Char('Tecla Derecha',    default='Numpad6')
    key_complete  = fields.Char('Tecla Completar',  default='NumpadEnter')
    key_undo      = fields.Char('Tecla Deshacer',   default='NumpadSubtract')

    # ------------------------------------------------------------------
    @api.model
    def kds_get_config(self):
        config = self.sudo()._get_or_create()
        return self._config_dict(config)

    @api.model
    def kds_save_config(self, vals):
        allowed = {
            'warn_minutes', 'danger_minutes',
            'sound_enabled', 'poll_interval', 'undo_count',
            'key_nav_up', 'key_nav_down', 'key_nav_left', 'key_nav_right',
            'key_complete', 'key_undo',
        }
        safe_vals = {k: v for k, v in vals.items() if k in allowed}
        if not safe_vals:
            return False

        for f in ('warn_minutes', 'danger_minutes', 'poll_interval', 'undo_count'):
            if f in safe_vals:
                safe_vals[f] = max(1, int(safe_vals[f]))
        if 'sound_enabled' in safe_vals:
            safe_vals['sound_enabled'] = bool(safe_vals['sound_enabled'])

        config = self.sudo()._get_or_create()
        wm = safe_vals.get('warn_minutes',  config.warn_minutes)
        dm = safe_vals.get('danger_minutes', config.danger_minutes)
        if dm <= wm:
            safe_vals['danger_minutes'] = wm + 1

        config.write(safe_vals)
        return True

    def _get_or_create(self):
        config = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.create({'company_id': self.env.company.id})
        return config

    @staticmethod
    def _config_dict(cfg):
        return {
            'id':             cfg.id,
            'warn_minutes':   cfg.warn_minutes,
            'danger_minutes': cfg.danger_minutes,
            'sound_enabled':  cfg.sound_enabled,
            'poll_interval':  cfg.poll_interval,
            'undo_count':     cfg.undo_count,
            'key_nav_up':     cfg.key_nav_up    or 'Numpad8',
            'key_nav_down':   cfg.key_nav_down  or 'Numpad5',
            'key_nav_left':   cfg.key_nav_left  or 'Numpad4',
            'key_nav_right':  cfg.key_nav_right or 'Numpad6',
            'key_complete':   cfg.key_complete  or 'NumpadEnter',
            'key_undo':       cfg.key_undo      or 'NumpadSubtract',
        }
