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
        # Sincronizamos en cualquier write — _bitopolis_kds_sync ya deduplica
        # internamente, por lo que múltiples writes seguidos son inocuos.
        # Esto cubre el flujo de mesas donde "Nuevo" escribe state/table_id
        # sin incluir 'lines' en vals, pero las líneas ya existen en self.lines.
        skip_states = {'cancel', 'done', 'invoiced'}
        for order in self.filtered(lambda o: o.state not in skip_states and o.lines):
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
        # No crear tarjetas para estados verdaderamente terminales.
        # 'paid' se permite: una quick-sale llega a 'paid' sin pasar por estados
        # intermedios; la deduplicación de sent_qty evita entradas dobles.
        if self.state in ('cancel', 'done', 'invoiced'):
            return False
        if not self.lines:
            return False

        Kds = self.env['kds.order']

        # Cantidad ya enviada al KDS por cada pos.order.line
        # {pos_line_id: total_qty_enviada}
        sent_qty = {}
        for kds_line in Kds.search([('pos_order_id', '=', self.id)]).mapped('line_ids'):
            if kds_line.pos_line_id:
                sent_qty[kds_line.pos_line_id.id] = (
                    sent_qty.get(kds_line.pos_line_id.id, 0.0) + kds_line.qty
                )

        # Líneas completamente nuevas (nunca enviadas)
        new_lines = self.lines.filtered(
            lambda l: l.id not in sent_qty
                      and not (l.product_id.type == 'service' and l.qty == 0)
        )

        # Líneas ya enviadas pero con más cantidad ahora (cliente agregó más del mismo)
        delta_lines = []
        for line in self.lines:
            if line.id in sent_qty and line.qty > sent_qty[line.id]:
                delta_lines.append((line, line.qty - sent_qty[line.id]))

        if not new_lines and not delta_lines:
            return False   # Nada nuevo

        # Crear tarjeta con líneas nuevas + deltas
        return self._bitopolis_kds_create(lines=new_lines, delta_lines=delta_lines)

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
        """
        Extrae texto plano de la nota de linea.
        Odoo 19 guarda customer_note como JSON rico:
          [{"text": "sin azucar", "colorIndex": 0}, ...]
        """
        for fname in ('customer_note', 'note'):
            if fname not in line._fields:
                continue
            val = getattr(line, fname, False)
            if val:
                return self._parse_pos_note(val)
        return ''

    def _bitopolis_kds_line_variant(self, line):
        if 'attribute_value_ids' in line._fields and line.attribute_value_ids:
            return ', '.join(line.attribute_value_ids.mapped('name'))
        return ''

    @staticmethod
    def _parse_pos_note(val):
        """Convierte una nota JSON rica de Odoo 19 a texto plano."""
        import json
        if not val:
            return ''
        stripped = val.strip()
        if stripped.startswith('[') or stripped.startswith('{'):
            try:
                data = json.loads(stripped)
                if isinstance(data, list):
                    parts = [
                        seg.get('text', '')
                        for seg in data
                        if isinstance(seg, dict) and seg.get('text', '').strip()
                    ]
                    text = ' '.join(parts).strip()
                    # Si habia JSON valido pero sin texto legible, devolver vacio
                    return text
                elif isinstance(data, dict) and data.get('text'):
                    return data['text'].strip()
                return ''  # JSON valido pero sin texto extraible
            except (ValueError, TypeError):
                pass
        return val

    def _bitopolis_kds_general_note(self):
        for fname in ('general_note', 'note', 'internal_note'):
            if fname in self._fields:
                val = getattr(self, fname, False)
                if val:
                    return self._parse_pos_note(val)
        return ''

    # ------------------------------------------------------------------
    # Creación del kds.order
    # ------------------------------------------------------------------
    def _bitopolis_kds_create(self, lines=None, delta_lines=None):
        """
        Crea un kds.order nuevo.
        lines:       recordset de pos.order.line nuevas (nunca enviadas).
        delta_lines: lista de (line, delta_qty) para líneas que aumentaron qty.
        """
        self.ensure_one()
        if lines is None:
            lines = self.lines
        if delta_lines is None:
            delta_lines = []

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

        # Agregar deltas (misma línea, solo la cantidad adicional)
        for line, delta_qty in delta_lines:
            if delta_qty <= 0:
                continue
            line_vals.append((0, 0, {
                'pos_line_id':           line.id,
                'product_id':            line.product_id.id,
                'qty':                   delta_qty,
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


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Disparar sync en la pos.order padre cuando se crean líneas directamente
        # 'paid' excluido del skip: las quick-sales crean las líneas cuando
        # la pos.order ya está en 'paid'. Debemos dejar pasar ese estado.
        _skip = {'cancel', 'done', 'invoiced'}
        order_ids = lines.mapped('order_id').filtered(lambda o: o.state not in _skip)
        for order in order_ids:
            try:
                order._bitopolis_kds_sync()
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Bitópolis KDS: error en line.create para pos.order %s", order.id
                )
        return lines
