# -*- coding: utf-8 -*-
from odoo import fields, models


class KdsOrderLine(models.Model):
    _name = 'kds.order.line'
    _description = 'Bitópolis KDS Order Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one(
        'kds.order', required=True, ondelete='cascade', index=True,
    )
    pos_line_id = fields.Many2one('pos.order.line', ondelete='set null')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    qty = fields.Float(string='Quantity', default=1.0)
    note = fields.Char(string='Note')
    attribute_value_names = fields.Char(string='Variant')
