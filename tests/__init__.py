"""Las pruebas corren siempre en modo local, sobre una base SQLite temporal."""

import atexit
import os
import tempfile

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
atexit.register(lambda: os.path.exists(_db.name) and os.remove(_db.name))

os.environ["TASKMETRICS_DB_PATH"] = _db.name
# Vacías (no ausentes) para que un .env real no conecte las pruebas a Supabase
for _name in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ[_name] = ""
os.environ["LOCAL_ADMIN_EMAIL"] = "admin@taskmetrics.com"
os.environ["LOCAL_ADMIN_PASSWORD"] = "admin123"
os.environ.pop("AREAS", None)
