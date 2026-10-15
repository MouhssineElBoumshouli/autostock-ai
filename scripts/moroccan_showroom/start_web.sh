#!/usr/bin/env bash
set -euo pipefail

: "${ODOO_MASTER_PASSWORD:?ODOO_MASTER_PASSWORD is required}"

source_config="${ODOO_RC:-/etc/odoo/odoo.conf}"
runtime_config="$(mktemp /tmp/autostock-odoo-XXXXXX.conf)"
chmod 600 "$runtime_config"
cp "$source_config" "$runtime_config"

{
    printf '\nadmin_passwd = %s\n' "$ODOO_MASTER_PASSWORD"
    printf 'http_interface = 0.0.0.0\n'
} >> "$runtime_config"

# Re-enter the official Odoo Docker entrypoint so it still injects the
# PostgreSQL connection arguments and waits for PostgreSQL readiness.
exec /entrypoint.sh odoo -c "$runtime_config"
