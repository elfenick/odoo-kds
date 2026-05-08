# -*- coding: utf-8 -*-
import json
from markupsafe import Markup
from odoo import http
from odoo.http import request

_KEY_DEFAULTS = {
    'key_nav_up':    'Numpad8',
    'key_nav_down':  'Numpad5',
    'key_nav_left':  'Numpad4',
    'key_nav_right': 'Numpad6',
    'key_complete':  'NumpadEnter',
    'key_undo':      'NumpadSubtract',
}


def _ensure_key_columns(cr):
    """
    Agrega columnas de teclas y font_size a kds_config si no existen.
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS es idempotente y transaccional en PostgreSQL.
    """
    cr.execute("""
        ALTER TABLE kds_config
            ADD COLUMN IF NOT EXISTS key_nav_up    VARCHAR DEFAULT 'Numpad8',
            ADD COLUMN IF NOT EXISTS key_nav_down  VARCHAR DEFAULT 'Numpad5',
            ADD COLUMN IF NOT EXISTS key_nav_left  VARCHAR DEFAULT 'Numpad4',
            ADD COLUMN IF NOT EXISTS key_nav_right VARCHAR DEFAULT 'Numpad6',
            ADD COLUMN IF NOT EXISTS key_complete  VARCHAR DEFAULT 'NumpadEnter',
            ADD COLUMN IF NOT EXISTS key_undo      VARCHAR DEFAULT 'NumpadSubtract',
            ADD COLUMN IF NOT EXISTS font_size     VARCHAR DEFAULT '17',
            ADD COLUMN IF NOT EXISTS sound_volume  FLOAT   DEFAULT 1.0
    """)


def _parse_font_size(raw):
    """Convierte el valor guardado (string numérico o legacy 'sm/md/lg/xl') a entero."""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return {'sm': 14, 'md': 17, 'lg': 21, 'xl': 27}.get(str(raw), 17)


def _cfg_to_dict(cfg):
    return {
        'id':             cfg.id,
        'warn_minutes':   cfg.warn_minutes,
        'danger_minutes': cfg.danger_minutes,
        'sound_enabled':  cfg.sound_enabled,
        'poll_interval':  cfg.poll_interval,
        'undo_count':     cfg.undo_count,
        'key_nav_up':     cfg.key_nav_up    or _KEY_DEFAULTS['key_nav_up'],
        'key_nav_down':   cfg.key_nav_down  or _KEY_DEFAULTS['key_nav_down'],
        'key_nav_left':   cfg.key_nav_left  or _KEY_DEFAULTS['key_nav_left'],
        'key_nav_right':  cfg.key_nav_right or _KEY_DEFAULTS['key_nav_right'],
        'key_complete':   cfg.key_complete  or _KEY_DEFAULTS['key_complete'],
        'key_undo':       cfg.key_undo      or _KEY_DEFAULTS['key_undo'],
        'font_size':      _parse_font_size(cfg.font_size),
        'sound_volume':   float(cfg.sound_volume or 1.0),
    }


def _get_license_info(env):
    try:
        return env['kds.license'].sudo().get_license_status().get('valid', False)
    except Exception:
        return False


class BitopolisKdsController(http.Controller):

    @http.route('/kds/license/check', type='jsonrpc', auth='user')
    def kds_license_check(self):
        try:
            return request.env['kds.license'].sudo().get_license_status()
        except Exception:
            return {'valid': False, 'message': 'Sin licencia'}


    # ------------------------------------------------------------------
    # SPA principal
    # ------------------------------------------------------------------
    @http.route('/kds/ui', type='http', auth='user')
    def kds_ui(self, token=None, station_id=None, **kwargs):
        if not request.session.uid:
            return request.redirect('/web/login?redirect=/kds/ui')

        # Resolver station_id desde token
        resolved_station_id = None
        if token:
            station = request.env['kds.station'].sudo().search(
                [('access_token', '=', token), ('active', '=', True)], limit=1
            )
            if station:
                resolved_station_id = station.id
            else:
                # Token inválido o estación eliminada
                resolved_station_id = -1  # señal de "no válido"
        elif station_id:
            resolved_station_id = int(station_id)

        session_info = request.env['ir.http'].session_info()
        csrf_token   = request.csrf_token()
        response = request.render('bitopolis_kds.index', {
            'session_info':       Markup(json.dumps(session_info)),
            'csrf_token':         Markup(json.dumps(csrf_token)),
            'initial_station_id': Markup(json.dumps(resolved_station_id)),
            'station_token':      Markup(json.dumps(token)),
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma']        = 'no-cache'
        response.headers['Expires']       = '0'
        return response


    @http.route('/kds/station/validate', type='jsonrpc', auth='user')
    def kds_station_validate(self, token=None):
        """Valida que el token siga activo. El KDS lo llama en cada poll."""
        if not token:
            return {'valid': False}
        station = request.env['kds.station'].sudo().search(
            [('access_token', '=', token), ('active', '=', True)], limit=1
        )
        return {'valid': bool(station), 'station_id': station.id if station else None}

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    @http.route('/kds/config/get', type='jsonrpc', auth='user')
    def kds_config_get(self):
        defaults = {
            'id': None, 'warn_minutes': 5, 'danger_minutes': 15,
            'sound_enabled': True, 'poll_interval': 5, 'undo_count': 5,
            **_KEY_DEFAULTS,
        }
        try:
            _ensure_key_columns(request.env.cr)
            cfg_obj  = request.env['kds.config'].sudo()
            existing = cfg_obj.search([('company_id', '=', request.env.company.id)], limit=1)
            if not existing:
                existing = cfg_obj.create({'company_id': request.env.company.id})
            return _cfg_to_dict(existing)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("KDS config get failed: %s", e)
            return defaults

    @http.route('/kds/config/save', type='jsonrpc', auth='user')
    def kds_config_save(self, vals):
        allowed = {
            'warn_minutes', 'danger_minutes', 'sound_enabled',
            'poll_interval', 'undo_count',
            'key_nav_up', 'key_nav_down', 'key_nav_left', 'key_nav_right',
            'key_complete', 'key_undo', 'font_size', 'sound_volume',
        }
        safe_vals = {k: v for k, v in vals.items() if k in allowed}
        if not safe_vals:
            return {'ok': False, 'error': 'No valid fields'}
        try:
            _ensure_key_columns(request.env.cr)
            for f in ('warn_minutes', 'danger_minutes', 'poll_interval', 'undo_count'):
                if f in safe_vals:
                    safe_vals[f] = max(1, int(safe_vals[f]))
            if 'sound_enabled' in safe_vals:
                safe_vals['sound_enabled'] = bool(safe_vals['sound_enabled'])

            cfg_obj = request.env['kds.config'].sudo()
            cfg = cfg_obj.search([('company_id', '=', request.env.company.id)], limit=1)
            if not cfg:
                cfg = cfg_obj.create({'company_id': request.env.company.id})

            wm = safe_vals.get('warn_minutes',  cfg.warn_minutes)
            dm = safe_vals.get('danger_minutes', cfg.danger_minutes)
            if dm <= wm:
                safe_vals['danger_minutes'] = wm + 1

            cfg.write(safe_vals)
            return {'ok': True, **_cfg_to_dict(cfg)}
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("KDS config save failed: %s", e)
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Estaciones
    # ------------------------------------------------------------------
    @http.route('/kds/stations', type='jsonrpc', auth='user')
    def kds_stations(self):
        try:
            stations = request.env['kds.station'].sudo().search([
                ('company_id', '=', request.env.company.id),
            ])
            return [{'id': s.id, 'name': s.name, 'show_all': s.show_all,
                     'has_categories': bool(s.pos_category_ids)} for s in stations]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("KDS stations failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @http.route('/kds/dashboard', type='jsonrpc', auth='user')
    def kds_dashboard(self):
        env = request.env
        defaults = {
            'config': {'warn_minutes': 5, 'danger_minutes': 15,
                       'sound_enabled': True, 'poll_interval': 5, 'undo_count': 5,
                       **_KEY_DEFAULTS},
            'stations': [],
            'total_pending': 0,
        }
        try:
            _ensure_key_columns(env.cr)

            cfg_obj = env['kds.config'].sudo()
            cfg = cfg_obj.search([('company_id', '=', env.company.id)], limit=1)
            if not cfg:
                cfg = cfg_obj.create({'company_id': env.company.id})

            pending_orders = env['kds.order'].search(
                [('state', '=', 'pending')], order='sent_at asc, id asc'
            )
            total_pending = len(pending_orders)

            stations_obj = env['kds.station'].sudo().search([
                ('company_id', '=', env.company.id),
            ])
            done_model = env['kds.order.done'].sudo()
            stations = []
            for s in stations_obj:
                if s.show_all or not s.pos_category_ids:
                    pending = total_pending
                else:
                    pending = 0
                    for o in pending_orders:
                        if any(s.line_matches(l) for l in o.line_ids):
                            if not done_model.search_count([
                                ('order_id', '=', o.id), ('station_id', '=', s.id)
                            ]):
                                pending += 1
                stations.append({
                    'id': s.id, 'name': s.name, 'show_all': s.show_all,
                    'category_names': s.pos_category_ids.mapped('name'),
                    'pending': pending,
                    'access_token': s.access_token,
                })

            license_valid = _get_license_info(request.env)
            if not license_valid and len(stations) > 1:
                stations = stations[:1]
            if not license_valid and not stations:
                stations = [{
                    'id': None, 'name': 'General', 'show_all': True,
                    'category_names': [], 'pending': total_pending,
                    'access_token': None, 'is_demo': True,
                }]
            return {
                'config':        _cfg_to_dict(cfg),
                'stations':      stations,
                'total_pending': total_pending,
                'license_valid': license_valid,
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("KDS dashboard failed: %s", e)
            return defaults
