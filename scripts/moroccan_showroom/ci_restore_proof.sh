#!/usr/bin/env bash
set -euo pipefail

run_id="${GITHUB_RUN_ID:-local}"
attempt="${GITHUB_RUN_ATTEMPT:-1}"
source_project="autostock-backup-proof-${run_id}-${attempt}"
restore_project="autostock-restore-proof-${run_id}-${attempt}"
database="autostock_atlas_morocco_demo"
postgres_user="autostock_restore_proof"
postgres_password="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
target_uuid="$(python3 -c 'import uuid; print(uuid.uuid4())')"
artifact_dir="$(mktemp -d)"
dump_path="$artifact_dir/database.dump"
filestore_path="$artifact_dir/filestore.tar"
manifest_path="$artifact_dir/backup-manifest.json"
signing_key_path="$artifact_dir/backup-manifest.key"
evidence_path="$artifact_dir/restore-evidence.json"
restore_network="${restore_project}-private"
restore_db_container="${restore_project}-db"
restore_postgres_volume="${restore_project}-postgres"
restore_filestore_volume="${restore_project}-filestore"
image="autostock-ai-odoo:19.0"

export POSTGRES_USER="$postgres_user"
export POSTGRES_PASSWORD="$postgres_password"
export POSTGRES_DB=postgres
export ODOO_PORT=18069
echo "::add-mask::$postgres_password"

cleanup_restore() {
    docker rm -f "$restore_db_container" >/dev/null 2>&1 || true
    docker volume rm "$restore_postgres_volume" >/dev/null 2>&1 || true
    docker volume rm "$restore_filestore_volume" >/dev/null 2>&1 || true
    docker network rm "$restore_network" >/dev/null 2>&1 || true
}

cleanup_all() {
    cleanup_restore
    docker compose --project-name "$source_project" down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$artifact_dir"
}
trap cleanup_all EXIT

tree_hash() {
    local volume="$1"
    docker run --rm --entrypoint python3 \
        --volume "${volume}:/data:ro" \
        "$image" \
        -c 'import hashlib,pathlib,sys
root=pathlib.Path(sys.argv[1])
h=hashlib.sha256()
for path in sorted(p for p in root.rglob("*") if p.is_file()):
    h.update(path.relative_to(root).as_posix().encode()+b"\\0")
    h.update(hashlib.sha256(path.read_bytes()).digest())
print(h.hexdigest())' \
        "/data/filestore/$database"
}

file_hash_in_volume() {
    local volume="$1"
    local relative_path="$2"
    docker run --rm --entrypoint sha256sum \
        --volume "${volume}:/data:ro" \
        "$image" \
        "/data/filestore/$database/$relative_path" \
        | awk '{print $1}'
}

echo "Creating disposable Odoo/PostgreSQL source environment."
docker compose --project-name "$source_project" build odoo
docker compose --project-name "$source_project" up --detach --wait db
docker compose --project-name "$source_project" run --rm --no-deps \
    --env "AUTOSTOCK_DEMO_TARGET_UUID=$target_uuid" \
    odoo odoo \
    --database="$database" \
    --init=autostock_ai \
    --stop-after-init \
    --without-demo=true \
    --log-level=warn

docker compose --project-name "$source_project" run --rm --no-deps -T \
    --env "AUTOSTOCK_DEMO_TARGET_UUID=$target_uuid" \
    odoo odoo shell --database="$database" --no-http <<'PY'
import base64
import os

company = env.ref("base.main_company")
company.write({
    "autostock_demo_environment": True,
    "autostock_demo_target_uuid": os.environ["AUTOSTOCK_DEMO_TARGET_UUID"],
    "autostock_demo_dataset_version": "restore-proof-ci",
})
env["ir.attachment"].create({
    "name": "AutoStock restore proof",
    "type": "binary",
    "datas": base64.b64encode(b"autostock-independent-restore-proof-v1"),
    "mimetype": "text/plain",
})
env.cr.commit()
PY

source_odoo_volume="$(
    docker volume ls \
        --filter "label=com.docker.compose.project=$source_project" \
        --filter "label=com.docker.compose.volume=odoo_data" \
        --format '{{.Name}}'
)"
test -n "$source_odoo_volume"

source_store_fname="$(
    docker compose --project-name "$source_project" exec -T db \
        psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT store_fname FROM ir_attachment WHERE name='AutoStock restore proof' ORDER BY id DESC LIMIT 1"
)"
test -n "$source_store_fname"

source_attachment_count="$(
    docker compose --project-name "$source_project" exec -T db \
        psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT count(*) FROM ir_attachment"
)"
source_attachment_sha256="$(file_hash_in_volume "$source_odoo_volume" "$source_store_fname")"
source_filestore_tree_sha256="$(tree_hash "$source_odoo_volume")"

echo "Creating database and filestore backup artifacts."
docker compose --project-name "$source_project" exec -T db \
    pg_dump -U "$postgres_user" -Fc "$database" > "$dump_path"

docker run --rm --user root --entrypoint sh \
    --volume "${source_odoo_volume}:/data:ro" \
    --volume "${artifact_dir}:/backup" \
    "$image" \
    -c 'cd /data && tar -cf /backup/filestore.tar .'

database_sha256="$(sha256sum "$dump_path" | awk '{print $1}')"
filestore_sha256="$(sha256sum "$filestore_path" | awk '{print $1}')"

# The artifacts used for restore must still be the exact bytes we just hashed.
test "$(sha256sum "$dump_path" | awk '{print $1}')" = "$database_sha256"
test "$(sha256sum "$filestore_path" | awk '{print $1}')" = "$filestore_sha256"

python3 - "$manifest_path" "$signing_key_path" "$database" "$target_uuid" "$database_sha256" "$filestore_sha256" <<'PY'
import json
import os
import sys

from scripts.moroccan_showroom.safety import backup_manifest_signature

path, key_path, database, target_uuid, database_hash, filestore_hash = sys.argv[1:]
key = os.urandom(32)
with open(key_path, "wb") as stream:
    stream.write(key)
manifest = {
    "database_name": database,
    "target_uuid": target_uuid,
    "database_sha256": database_hash,
    "filestore_sha256": filestore_hash,
    "proof_scope": "disposable-ci-restore-mechanism",
}
manifest["signature_hmac_sha256"] = backup_manifest_signature(manifest, key)
if backup_manifest_signature(manifest, key) != manifest["signature_hmac_sha256"]:
    raise SystemExit("Manifest signature self-check failed.")
with open(path, "w", encoding="utf-8") as stream:
    json.dump(manifest, stream, sort_keys=True)
PY

echo "Restoring into a fresh project with no published ports."
docker network create "$restore_network" >/dev/null
docker volume create "$restore_postgres_volume" >/dev/null
docker volume create "$restore_filestore_volume" >/dev/null
docker run --detach \
    --name "$restore_db_container" \
    --network "$restore_network" \
    --env "POSTGRES_USER=$postgres_user" \
    --env "POSTGRES_PASSWORD=$postgres_password" \
    --env "POSTGRES_DB=postgres" \
    --volume "${restore_postgres_volume}:/var/lib/postgresql/data" \
    postgres:16 >/dev/null

for _ in $(seq 1 30); do
    if docker exec "$restore_db_container" pg_isready -U "$postgres_user" -d postgres >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
docker exec "$restore_db_container" pg_isready -U "$postgres_user" -d postgres >/dev/null

restore_port_bindings="$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$restore_db_container")"
test "$restore_port_bindings" = "null" -o "$restore_port_bindings" = "{}"

docker exec "$restore_db_container" createdb -U "$postgres_user" "$database"
docker exec -i "$restore_db_container" \
    pg_restore -U "$postgres_user" -d "$database" --no-owner --no-privileges < "$dump_path"

docker run --rm --user root --entrypoint sh \
    --volume "${restore_filestore_volume}:/data" \
    --volume "${artifact_dir}:/backup:ro" \
    "$image" \
    -c 'cd /data && tar -xf /backup/filestore.tar'

module_state="$(
    docker exec "$restore_db_container" psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT state FROM ir_module_module WHERE name='autostock_ai' LIMIT 1"
)"
restored_marker="$(
    docker exec "$restore_db_container" psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT autostock_demo_target_uuid FROM res_company WHERE autostock_demo_environment IS TRUE LIMIT 1"
)"
fixture_table="$(
    docker exec "$restore_db_container" psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT CASE WHEN to_regclass('public.autostock_morocco_fixture') IS NULL THEN 'false' ELSE 'true' END"
)"
restored_attachment_count="$(
    docker exec "$restore_db_container" psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT count(*) FROM ir_attachment"
)"
restored_store_fname="$(
    docker exec "$restore_db_container" psql -U "$postgres_user" -d "$database" -Atc \
        "SELECT store_fname FROM ir_attachment WHERE name='AutoStock restore proof' ORDER BY id DESC LIMIT 1"
)"
test "$source_store_fname" = "$restored_store_fname"

restored_attachment_sha256="$(file_hash_in_volume "$restore_filestore_volume" "$restored_store_fname")"
restored_filestore_tree_sha256="$(tree_hash "$restore_filestore_volume")"

test "$module_state" = "installed"
test "$restored_marker" = "$target_uuid"
test "$fixture_table" = "true"
test "$source_attachment_count" = "$restored_attachment_count"
test "$source_attachment_sha256" = "$restored_attachment_sha256"
test "$source_filestore_tree_sha256" = "$restored_filestore_tree_sha256"

echo "Removing only disposable restore verifier resources."
cleanup_restore
test -z "$(docker ps -aq --filter "name=^/${restore_db_container}$")"
test -z "$(docker volume ls -q --filter "name=^${restore_postgres_volume}$")"
test -z "$(docker volume ls -q --filter "name=^${restore_filestore_volume}$")"
test -z "$(docker network ls -q --filter "name=^${restore_network}$")"

python3 - "$evidence_path" "$restore_project" "$database" "$database_sha256" "$filestore_sha256" \
    "$target_uuid" "$source_attachment_sha256" "$restored_attachment_sha256" \
    "$source_filestore_tree_sha256" "$restored_filestore_tree_sha256" \
    "$source_attachment_count" "$restored_attachment_count" \
    "$restore_postgres_volume" "$restore_filestore_volume" "$module_state" "$fixture_table" <<'PY'
import json
import sys

(
    path,
    restore_project,
    database,
    database_hash,
    filestore_hash,
    target_uuid,
    source_attachment_hash,
    restored_attachment_hash,
    source_tree_hash,
    restored_tree_hash,
    source_count,
    restored_count,
    postgres_volume,
    filestore_volume,
    module_state,
    fixture_table,
) = sys.argv[1:]

with open(path, "w", encoding="utf-8") as stream:
    json.dump({
        "restore_project": restore_project,
        "published_ports": [],
        "restore_postgres_volume": postgres_volume,
        "restore_filestore_volume": filestore_volume,
        "restore_database": database,
        "backup_database_sha256": database_hash,
        "backup_filestore_sha256": filestore_hash,
        "pg_restore_succeeded": True,
        "module_state": module_state,
        "marker_uuid": target_uuid,
        "fixture_table_exists": fixture_table == "true",
        "source_attachment_sha256": source_attachment_hash,
        "restored_attachment_sha256": restored_attachment_hash,
        "source_filestore_tree_sha256": source_tree_hash,
        "restored_filestore_tree_sha256": restored_tree_hash,
        "source_attachment_count": int(source_count),
        "restored_attachment_count": int(restored_count),
        "proof_attachment_present": True,
        "cleanup_scope": restore_project,
        "restore_resources_removed": True,
    }, stream, sort_keys=True)
PY

python3 -m scripts.moroccan_showroom.restore_contract \
    --evidence-json "$evidence_path" \
    --backup-manifest-json "$manifest_path" \
    --signing-key-file "$signing_key_path" \
    --expected-target-uuid "$target_uuid"

echo "PASS: disposable PostgreSQL + Odoo filestore backup restored and verified."
echo "No showroom database, volume, container, credentials, or app connection was used."
