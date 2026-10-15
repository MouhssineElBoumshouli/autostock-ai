"""Start the Moroccan Odoo web process without shell line-ending assumptions."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

master_password = os.environ.get("ODOO_MASTER_PASSWORD")
if not master_password:
    raise SystemExit("ODOO_MASTER_PASSWORD is required")

source_config = Path(os.environ.get("ODOO_RC", "/etc/odoo/odoo.conf"))
fd, runtime_name = tempfile.mkstemp(prefix="autostock-odoo-", suffix=".conf")
os.close(fd)
runtime_config = Path(runtime_name)
os.chmod(runtime_config, 0o600)
shutil.copyfile(source_config, runtime_config)

with runtime_config.open("a", encoding="utf-8", newline="\n") as stream:
    stream.write(f"\nadmin_passwd = {master_password}\n")
    stream.write("http_interface = 0.0.0.0\n")

# Re-enter the official Odoo Docker entrypoint so it still injects the
# PostgreSQL connection arguments and waits for PostgreSQL readiness.
os.execv("/entrypoint.sh", ["/entrypoint.sh", "odoo", "-c", str(runtime_config)])
