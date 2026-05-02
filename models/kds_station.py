# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KdsStation(models.Model):
    _name = 'kds.station'
    _description = 'Bitópolis KDS Station'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre de Estación', required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        required=True, index=True,
    )
    pos_category_ids = fields.Many2many(
        'pos.category',
        'kds_station_pos_category_rel',
        'station_id', 'category_id',
        string='Categorías POS',
        help='Solo se muestran productos de estas categorías. '
             'Deja vacío para mostrar todas las órdenes.',
    )
    show_all = fields.Boolean(
        'Mostrar todas las categorías', default=False,
        help='Ignora el filtro y muestra todas las órdenes.',
    )
    active = fields.Boolean(default=True)
    color = fields.Integer(default=0)

    # ------------------------------------------------------------------
    # Constraints — máximo 1 estación por empresa, máx 2 categorías
    # ------------------------------------------------------------------
    @api.constrains('pos_category_ids')
    def _check_max_categories(self):
        for rec in self:
            if len(rec.pos_category_ids) > 2:
                raise ValidationError(
                    'Solo se pueden asignar máximo 2 categorías por estación.'
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get('company_id', self.env.company.id)
            existing = self.sudo().search_count([
                ('company_id', '=', company_id),
                ('active', 'in', [True, False]),
            ])
            if existing >= 1:
                raise ValidationError(
                    'Solo se puede configurar 1 estación KDS por empresa.'
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # API para OWL — sudo() para evitar problemas de ACL en la BD
    # ------------------------------------------------------------------
    @api.model
    def kds_get_stations(self):
        stations = self.sudo().search([
            ('company_id', '=', self.env.company.id),
        ])
        return [{
            'id': s.id,
            'name': s.name,
            'show_all': s.show_all,
            'has_categories': bool(s.pos_category_ids),
        } for s in stations]

    # ------------------------------------------------------------------
    # Helper de filtrado de líneas
    # ------------------------------------------------------------------
    def line_matches(self, line):
        """True si la línea de KDS debe mostrarse en esta estación."""
        self.ensure_one()
        if self.show_all or not self.pos_category_ids:
            return True

        tmpl = line.product_id.product_tmpl_id
        station_cats = self.pos_category_ids

        if 'pos_categ_ids' in tmpl._fields:
            prod_cats = tmpl.pos_categ_ids
            if not prod_cats:
                return True
            return bool(prod_cats & station_cats)

        if 'pos_categ_id' in tmpl._fields:
            prod_cat = tmpl.pos_categ_id
            if not prod_cat:
                return True
            return prod_cat in station_cats

        return True
