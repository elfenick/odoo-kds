import secrets
def migrate(cr, version):
    cr.execute("ALTER TABLE kds_station ADD COLUMN IF NOT EXISTS access_token VARCHAR")
    cr.execute("SELECT id FROM kds_station WHERE access_token IS NULL OR access_token = ''")
    for (sid,) in cr.fetchall():
        cr.execute("UPDATE kds_station SET access_token = %s WHERE id = %s", (secrets.token_urlsafe(32), sid))
