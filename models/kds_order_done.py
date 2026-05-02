# -*- coding: utf-8 -*-
from odoo import fields, models


class KdsOrderDone(models.Model):
    _name = 'kds.order.done'
    _description = 'Bitópolis KDS Order Completion'
    _order = 'done_at desc, id desc'

    order_id = fields.Many2one('kds.order', required=True, ondelete='cascade', index=True)
    station_id = fields.Many2one('kds.station', required=True, ondelete='cascade', index=True)
    done_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
