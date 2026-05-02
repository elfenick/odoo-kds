# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # Hook CREATE — captura órdenes que ya llegan con líneas (flujo quick)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            try:
                order._bitopolis_kds_sync()
            except Exception:
                _logger.exception(
                    "Bitópolis KDS: error en create para pos.order %s", order.id
                )
        return orders

    # ------------------------------------------------------------------
    # Hook WRITE — solo actuar cuando cambien las líneas de la orden.
    # Evita ejecutar el search en cada write de estado, precio, etc.
    # ------------------------------------------------------------------
    def write(self, vals):
        result = super().write(vals)
        # 'lines' es el campo One2many de pos.order.line.
        # Solo sincronizamos si hubo cambios en las líneas.
        if 'lines' in vals:
            for order in self.filtered(lambda o: o.state != 'cancel'):
                try:
                    order._bitopolis_kds_sync()
                except Exception:
                    _logger.exception(
                        "Bitópolis KDS: error en write para pos.order %s", order.id
                    )
        return result

    # ------------------------------------------------------------------
    # Sincronización principal
    # ------------------------------------------------------------------
    def _bitopolis_kds_sync(self):
        """
        Regla: cada ronda de pedido genera una tarjeta NUEVA en el KDS,
        independientemente de si hay un ticket pendiente anterior.
        Así el cocinero sabe exactamente qué llegó en cada comanda.
        """
        self.ensure_one()
        if not self.lines:
            return False

        Kds = self.env['kds.order']

        # IDs de pos.order.line ya registradas en CUALQUIER kds.order de esta orden
        already_tracked_line_ids = set(
            Kds.search([('pos_order_id', '=', self.id)])
              .mapped('line_ids.pos_line_id')
              .ids
        )

        # Solo las líneas que todavía no tienen tarjeta
        new_lines = self.lines.filtered(
            lambda l: l.id not in already_tracked_line_ids
                      and not (l.product_id.type == 'service' and l.qty == 0)
        )

        if not new_lines:
            return False   # Nada nuevo — puede ser un write de precio, estado, etc.

        # Siempre crear tarjeta nueva con solo las líneas nuevas
        return self._bitopolis_kds_create(lines=new_lines)

    # ------------------------------------------------------------------
    # Helpers defensivos
    # ------------------------------------------------------------------
    def _bitopolis_kds_table_name(self):
        self.ensure_one()
        if 'table_id' in self._fields and self.table_id:
            tbl = self.table_id
            return (
                getattr(tbl, 'table_number', False)
                or getattr(tbl, 'name', False)
                or ''
            )
        return ''

    def _bitopolis_kds_tracking(self):
        self.ensure_one()
        return (
            getattr(self, 'tracking_number', False)
            or self.pos_reference
            or self.name
            or ''
        )

    def _bitopolis_kds_line_note(self, line):
        for fname in ('customer_note', 'note'):
            if fname in line._fields:
                val = getattr(line, fname, False)
                if val:
                    return val
        return ''

    def _bitopolis_kds_line_variant(self, line):
        if 'attribute_value_ids' in line._fields and line.attribute_value_ids:
            return ', '.join(line.attribute_value_ids.mapped('name'))
        return ''

    def _bitopolis_kds_general_note(self):
        for fname in ('general_note', 'note', 'internal_note'):
            if fname in self._fields:
                val = getattr(self, fname, False)
                if val:
                    return val
        return ''

    # ------------------------------------------------------------------
    # Creación del kds.order
    # ------------------------------------------------------------------
    def _bitopolis_kds_create(self, lines=None):
        """
        Crea un kds.order nuevo.
        lines: recordset de pos.order.line a incluir (default: todas).
        """
        self.ensure_one()
        if lines is None:
            lines = self.lines

        line_vals = []
        for line in lines:
            if line.product_id.type == 'service' and line.qty == 0:
                continue
            line_vals.append((0, 0, {
                'pos_line_id':           line.id,
                'product_id':            line.product_id.id,
                'qty':                   line.qty,
                'note':                  self._bitopolis_kds_line_note(line),
                'attribute_value_names': self._bitopolis_kds_line_variant(line),
            }))

        if not line_vals:
            return False

        return self.env['kds.order'].create({
            'name':            self.pos_reference or self.name,
            'pos_order_id':    self.id,
            'tracking_number': self._bitopolis_kds_tracking(),
            'table_name':      self._bitopolis_kds_table_name(),
            'config_id':       self.config_id.id if self.config_id else False,
            'note':            self._bitopolis_kds_general_note(),
            'line_ids':        line_vals,
        })
