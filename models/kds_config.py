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
        help='Tiempo en minutos antes de que la tarjeta pase a color amarillo.',
    )
    danger_minutes = fields.Integer(
        'Minutos hasta Rojo', default=15,
        help='Tiempo en minutos antes de que la tarjeta pase a color rojo con pulso.',
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

    # ------------------------------------------------------------------
    # API para OWL — usa sudo() para evitar problemas de ACL cuando el
    # registro de seguridad no se propagó correctamente en la BD.
    # ------------------------------------------------------------------
    @api.model
    def kds_get_config(self):
        config = self.sudo()._get_or_create()
        return {
            'id':             config.id,
            'warn_minutes':   config.warn_minutes,
            'danger_minutes': config.danger_minutes,
            'sound_enabled':  config.sound_enabled,
            'poll_interval':  config.poll_interval,
            'undo_count':     config.undo_count,
        }

    @api.model
    def kds_save_config(self, vals):
        allowed = {
            'warn_minutes', 'danger_minutes',
            'sound_enabled', 'poll_interval', 'undo_count',
        }
        safe_vals = {k: v for k, v in vals.items() if k in allowed}
        if not safe_vals:
            return False

        # Coerción de tipos: los sliders HTML devuelven float, Odoo espera int
        for f in ('warn_minutes', 'danger_minutes', 'poll_interval', 'undo_count'):
            if f in safe_vals:
                safe_vals[f] = max(1, int(safe_vals[f]))
        if 'sound_enabled' in safe_vals:
            safe_vals['sound_enabled'] = bool(safe_vals['sound_enabled'])

        # danger_minutes debe ser mayor que warn_minutes
        config = self.sudo()._get_or_create()
        wm = safe_vals.get('warn_minutes',  config.warn_minutes)
        dm = safe_vals.get('danger_minutes', config.danger_minutes)
        if dm <= wm:
            safe_vals['danger_minutes'] = wm + 1

        config.write(safe_vals)
        return True

    def _get_or_create(self):
        """Devuelve (o crea) la config de la compañía actual. Llamar con sudo()."""
        config = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.create({'company_id': self.env.company.id})
        return config
