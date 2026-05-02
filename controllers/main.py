# -*- coding: utf-8 -*-
import json
from markupsafe import Markup
from odoo import http
from odoo.http import request


class BitopolisKdsController(http.Controller):

    # ------------------------------------------------------------------
    # SPA principal
    # ------------------------------------------------------------------
    @http.route('/kds/ui', type='http', auth='user')
    def kds_ui(self, station_id=None, **kwargs):
        if not request.session.uid:
            return request.redirect('/web/login?redirect=/kds/ui')
        session_info = request.env['ir.http'].session_info()
        csrf_token   = request.csrf_token()
        response = request.render('bitopolis_kds.index', {
            'session_info':       Markup(json.dumps(session_info)),
            'csrf_token':         Markup(json.dumps(csrf_token)),
            'initial_station_id': Markup(json.dumps(int(station_id) if station_id else None)),
        })
        # Evitar que el browser cachee el HTML con assets viejos
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma']        = 'no-cache'
        response.headers['Expires']       = '0'
        return response

    # ------------------------------------------------------------------
    # Config — rutas JSON que bypasean ORM ACL (igual que POS)
    # ------------------------------------------------------------------
    @http.route('/kds/config/get', type='json', auth='user')
    def kds_config_get(self):
        """Lee la configuración KDS. Devuelve defaults si la tabla no está lista."""
        defaults = {
            'id': None,
            'warn_minutes': 5,
            'danger_minutes': 15,
            'sound_enabled': True,
            'poll_interval': 5,
            'undo_count': 5,
        }
        try:
            cfg = request.env['kds.config'].sudo()
            # Buscar sin _get_or_create para no depender del método si hay cache viejo
            existing = cfg.search(
                [('company_id', '=', request.env.company.id)], limit=1
            )
            if not existing:
                existing = cfg.create({'company_id': request.env.company.id})
            return {
                'id':             existing.id,
                'warn_minutes':   existing.warn_minutes,
                'danger_minutes': existing.danger_minutes,
                'sound_enabled':  existing.sound_enabled,
                'poll_interval':  existing.poll_interval,
                'undo_count':     existing.undo_count,
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "KDS config get failed, using defaults: %s", e
            )
            return defaults

    @http.route('/kds/config/save', type='json', auth='user')
    def kds_config_save(self, vals):
        """Guarda la configuración KDS."""
        allowed   = {'warn_minutes', 'danger_minutes', 'sound_enabled',
                     'poll_interval', 'undo_count'}
        safe_vals = {k: v for k, v in vals.items() if k in allowed}
        if not safe_vals:
            return {'ok': False, 'error': 'No valid fields'}
        try:
            # Coerción de tipos (sliders devuelven float)
            for f in ('warn_minutes', 'danger_minutes', 'poll_interval', 'undo_count'):
                if f in safe_vals:
                    safe_vals[f] = max(1, int(safe_vals[f]))
            if 'sound_enabled' in safe_vals:
                safe_vals['sound_enabled'] = bool(safe_vals['sound_enabled'])

            cfg_obj = request.env['kds.config'].sudo()
            cfg = cfg_obj.search(
                [('company_id', '=', request.env.company.id)], limit=1
            )
            if not cfg:
                cfg = cfg_obj.create({'company_id': request.env.company.id})

            # danger debe ser > warn
            wm = safe_vals.get('warn_minutes',  cfg.warn_minutes)
            dm = safe_vals.get('danger_minutes', cfg.danger_minutes)
            if dm <= wm:
                safe_vals['danger_minutes'] = wm + 1

            cfg.write(safe_vals)
            return {
                'ok':            True,
                'warn_minutes':  cfg.warn_minutes,
                'danger_minutes': cfg.danger_minutes,
                'sound_enabled': cfg.sound_enabled,
                'poll_interval': cfg.poll_interval,
                'undo_count':    cfg.undo_count,
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("KDS config save failed: %s", e)
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Estaciones — ruta JSON que bypasea ORM ACL
    # ------------------------------------------------------------------
    @http.route('/kds/stations', type='json', auth='user')
    def kds_stations(self):
        """Lista las estaciones KDS de la compañía actual."""
        try:
            stations = request.env['kds.station'].sudo().search([
                ('company_id', '=', request.env.company.id),
            ])
            return [{
                'id':             s.id,
                'name':           s.name,
                'show_all':       s.show_all,
                'has_categories': bool(s.pos_category_ids),
            } for s in stations]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("KDS stations failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Dashboard — un solo call devuelve todo lo necesario
    # ------------------------------------------------------------------
    @http.route('/kds/dashboard', type='json', auth='user')
    def kds_dashboard(self):
        env = request.env
        defaults = {
            'config': {
                'warn_minutes': 5, 'danger_minutes': 15,
                'sound_enabled': True, 'poll_interval': 5, 'undo_count': 5,
            },
            'stations': [],
            'total_pending': 0,
        }
        try:
            # Config
            cfg_obj = env['kds.config'].sudo()
            cfg = cfg_obj.search(
                [('company_id', '=', env.company.id)], limit=1
            )
            if not cfg:
                cfg = cfg_obj.create({'company_id': env.company.id})
            config = {
                'warn_minutes':   cfg.warn_minutes,
                'danger_minutes': cfg.danger_minutes,
                'sound_enabled':  cfg.sound_enabled,
                'poll_interval':  cfg.poll_interval,
                'undo_count':     cfg.undo_count,
            }

            # Pending orders
            pending_orders = env['kds.order'].search([('state', '=', 'pending')], order='sent_at asc, id asc')
            total_pending  = len(pending_orders)

            # Estaciones
            stations_obj = env['kds.station'].sudo().search([
                ('company_id', '=', env.company.id),
            ])
            stations = []
            done_model = env['kds.order.done'].sudo()
            for s in stations_obj:
                if s.show_all or not s.pos_category_ids:
                    pending = total_pending
                else:
                    pending = 0
                    for o in pending_orders:
                        if any(s.line_matches(l) for l in o.line_ids):
                            if not done_model.search_count([('order_id', '=', o.id), ('station_id', '=', s.id)]):
                                pending += 1
                stations.append({
                    'id':             s.id,
                    'name':           s.name,
                    'show_all':       s.show_all,
                    'category_names': s.pos_category_ids.mapped('name'),
                    'pending':        pending,
                })

            return {
                'config':        config,
                'stations':      stations,
                'total_pending': total_pending,
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("KDS dashboard failed: %s", e)
            return defaults
