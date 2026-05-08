# -*- coding: utf-8 -*-
import json, base64
from odoo import api, fields, models

PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAMH2ZKKQYKaSjqzoPQt0lQehVnzCAghZzRiFBGKY62EY=
-----END PUBLIC KEY-----"""

ADDON_MAJOR_VERSION = "5"

def _verificar_codigo(codigo, uuid_bd, db_name):
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature
        licencia = json.loads(base64.b64decode(codigo))
        payload  = base64.b64decode(licencia["payload"])
        firma    = base64.b64decode(licencia["firma"])
        datos    = json.loads(payload)
        load_pem_public_key(PUBLIC_KEY_PEM).verify(firma, payload)
        if datos.get("uuid") != uuid_bd:
            return False, "❌ Licencia no válida para esta base de datos."
        if datos.get("db") and datos.get("db") != db_name:
            return False, "❌ Licencia no válida para esta instalación."
        max_version = str(datos.get("max_version", "5"))
        if int(ADDON_MAJOR_VERSION) > int(max_version):
            return False, f"❌ Tu licencia es para la versión {max_version}.x. Actualiza en bitopolis.cc"
        return True, f"✅ Licencia válida — Cliente: {datos.get('cliente', '?')} (v{max_version}.x)"
    except InvalidSignature:
        return False, "❌ Licencia inválida o modificada."
    except Exception as e:
        return False, f"❌ Error: {e}"


class KdsLicense(models.Model):
    _name        = 'kds.license'
    _description = 'Bitópolis KDS — Licencia'

    license_key = fields.Text(string='Código de Licencia', required=True)
    status      = fields.Char(string='Estado', readonly=True)
    valid       = fields.Boolean(string='Válida', readonly=True, default=False)

    @api.model
    def get_license_status(self):
        uuid_bd = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        db_name = self.env.cr.dbname
        lic = self.sudo().search([], limit=1, order='id asc')
        if not lic:
            return {'valid': False, 'message': 'Sin licencia — contacta bitopolis.cc'}
        ok, msg = _verificar_codigo(lic.license_key, uuid_bd, db_name)
        return {'valid': ok, 'message': msg}

    @api.model
    def action_open_license(self):
        lic = self.sudo().search([], limit=1, order='id asc')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Licencia KDS',
            'res_model': 'kds.license',
            'view_mode': 'form',
            'res_id': lic.id if lic else False,
            'target': 'current',
            'context': {'create': not bool(lic)},
        }

    def action_validate(self):
        uuid_bd = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        db_name = self.env.cr.dbname
        ok, msg = _verificar_codigo(self.license_key, uuid_bd, db_name)
        self.write({'valid': ok, 'status': msg})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Licencia KDS', 'message': msg,
                       'type': 'success' if ok else 'danger', 'sticky': False}
        }
