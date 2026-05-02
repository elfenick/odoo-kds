# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KdsOrder(models.Model):
    _name = 'kds.order'
    _description = 'Bitópolis KDS Order'
    _order = 'sent_at desc, id desc'

    name = fields.Char(string='Order Reference', required=True, index=True)
    pos_order_id = fields.Many2one(
        'pos.order', string='POS Order',
        ondelete='cascade', index=True,
    )
    tracking_number = fields.Char(
        string='Tracking #', index=True,
        help='Número corto mostrado en grande. Se usa en el numpad para completar.',
    )
    table_name = fields.Char(string='Table')
    config_id = fields.Many2one('pos.config', string='POS Config')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='pending', index=True, required=True)
    sent_at = fields.Datetime(string='Sent at', default=fields.Datetime.now, required=True)
    done_at = fields.Datetime(string='Completed at')
    note = fields.Text(string='General Note')
    line_ids = fields.One2many('kds.order.line', 'order_id', string='Lines')

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._notify_kds('new_order')
        return records

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_done(self):
        self.sudo().env['kds.order.done'].search([('order_id', 'in', self.ids)]).unlink()
        self.write({'state': 'done', 'done_at': fields.Datetime.now()})
        for rec in self:
            rec._notify_kds('order_done')
        return True

    def action_reopen(self):
        self.sudo().env['kds.order.done'].search([('order_id', 'in', self.ids)]).unlink()
        self.write({'state': 'pending', 'done_at': False})
        for rec in self:
            rec._notify_kds('order_reopened')
        return True

    def _kds_done_model(self):
        return self.env['kds.order.done'].sudo()

    def _kds_station_is_specific(self, station):
        return bool(station and not station.show_all and station.pos_category_ids)

    def _kds_is_done_for_station(self, station):
        self.ensure_one()
        if not self._kds_station_is_specific(station):
            return self.state == 'done'
        return bool(self._kds_done_model().search_count([
            ('order_id', '=', self.id),
            ('station_id', '=', station.id),
        ]))

    def _kds_relevant_stations(self):
        stations = self.env['kds.station'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('show_all', '=', False),
        ])
        return stations.filtered(lambda s: bool(s.pos_category_ids) and any(s.line_matches(l) for l in self.line_ids))

    def _kds_recompute_global_state(self):
        self.ensure_one()
        relevant = self._kds_relevant_stations()
        if not relevant:
            return False
        done_station_ids = set(self._kds_done_model().search([('order_id', '=', self.id)]).mapped('station_id').ids)
        all_done = all(station.id in done_station_ids for station in relevant)
        if all_done and self.state != 'done':
            self.write({'state': 'done', 'done_at': fields.Datetime.now()})
            return True
        if not all_done and self.state == 'done':
            self.write({'state': 'pending', 'done_at': False})
        return False

    # ------------------------------------------------------------------
    # Bus / realtime
    # ------------------------------------------------------------------
    # Bus / realtime
    # ------------------------------------------------------------------
    def _kds_channel(self):
        return f'bitopolis_kds#{self.env.company.id}'

    def _notify_kds(self, event):
        self.ensure_one()
        self.env['bus.bus']._sendone(
            self._kds_channel(),
            'kds.update',
            {'event': event, 'order_id': self.id},
        )

    # ------------------------------------------------------------------
    # Serialización (con filtro de estación opcional)
    # ------------------------------------------------------------------
    def _serialize(self, station=None):
        """
        Serializa la orden para el frontend.
        Si se pasa una estación específica, devuelve solo las líneas que le
        corresponden y oculta la orden cuando ya fue completada en esa estación.
        Retorna None si la orden no tiene líneas relevantes para la estación.
        """
        self.ensure_one()
        lines = self.line_ids

        if self._kds_station_is_specific(station):
            if self._kds_is_done_for_station(station):
                return None
            lines = lines.filtered(lambda l: station.line_matches(l))
            if not lines:
                return None

        return {
            'id': self.id,
            'name': self.name,
            'tracking_number': self.tracking_number or '',
            'table_name': self.table_name or '',
            'state': self.state,
            'sent_at': self.sent_at.isoformat() if self.sent_at else False,
            'note': self.note or '',
            'lines': [{
                'id': l.id,
                'product_name': l.product_id.display_name,
                'qty': l.qty,
                'note': l.note or '',
                'attribute_names': l.attribute_value_names or '',
            } for l in lines],
        }

    # ------------------------------------------------------------------
    # API pública — consumida por OWL
    # ------------------------------------------------------------------
    @api.model
    def kds_get_active_orders(self, station_id=None):
        """Devuelve órdenes pendientes, opcionalmente filtradas por estación."""
        orders = self.search([('state', '=', 'pending')], order='sent_at asc, id asc')
        station = None
        if station_id:
            station = self.env['kds.station'].browse(int(station_id)).exists()
        result = []
        for o in orders:
            s = o._serialize(station=station)
            if s is not None:
                result.append(s)
        return result

    @api.model
    def kds_get_recently_done(self, limit=10, station_id=None):
        """Órdenes recién completadas para la bandeja de deshacer."""
        limit = int(limit)
        station = None
        if station_id:
            station = self.env['kds.station'].browse(int(station_id)).exists()

        if self._kds_station_is_specific(station):
            entries = self._kds_done_model().search([('station_id', '=', station.id)], order='done_at desc, id desc', limit=limit)
            result = []
            for entry in entries:
                data = entry.order_id._serialize()
                if data is None:
                    continue
                data['done_id'] = entry.id
                data['done_at'] = entry.done_at.isoformat() if entry.done_at else False
                result.append(data)
            return result

        orders = self.search([('state', '=', 'done')], order='done_at desc', limit=limit)
        result = []
        for order in orders:
            data = order._serialize()
            data['done_id'] = order.id
            result.append(data)
        return result

    @api.model
    def kds_complete(self, order_id, station_id=None):
        order = self.browse(int(order_id)).exists()
        if not order:
            return False

        station = None
        if station_id:
            station = self.env['kds.station'].browse(int(station_id)).exists()

        if not self._kds_station_is_specific(station):
            if order.state == 'pending':
                order.action_done()
                return True
            return False

        if order.state == 'done':
            return False

        done_model = self._kds_done_model()
        exists = done_model.search_count([('order_id', '=', order.id), ('station_id', '=', station.id)])
        if not exists:
            done_model.create({'order_id': order.id, 'station_id': station.id})
            order._notify_kds('order_done')
        order._kds_recompute_global_state()
        return True

    @api.model
    def kds_complete_by_tracking(self, tracking, station_id=None):
        if not tracking:
            return False
        station = None
        if station_id:
            station = self.env['kds.station'].browse(int(station_id)).exists()
        orders = self.search([('state', '=', 'pending'), ('tracking_number', '=', str(tracking))], order='sent_at asc, id asc')
        for order in orders:
            if order.kds_complete(order.id, station.id if station else False):
                return order.id
        return False

    @api.model
    def kds_reopen(self, done_id, station_id=None):
        """Regresa una orden completada a estado pendiente (deshacer)."""
        station = None
        if station_id:
            station = self.env['kds.station'].browse(int(station_id)).exists()

        if not self._kds_station_is_specific(station):
            order = self.browse(int(done_id)).exists()
            if order and order.state == 'done':
                order.action_reopen()
                return order._serialize()
            return False

        done = self._kds_done_model().browse(int(done_id)).exists()
        if not done or done.station_id.id != station.id:
            return False
        order = done.order_id
        done.unlink()
        order._kds_recompute_global_state()
        order._notify_kds('order_reopened')
        return order._serialize(station=station)

