from pathlib import Path

import pytest

from scripts.moroccan_showroom.local_backup import (
    create_backup_manifest,
    validate_manifest_files,
)
from scripts.moroccan_showroom.safety import SafetyError


TARGET_UUID = "0f7d8360-4aa6-48dc-9337-6438f704db12"
SYSTEM_IDENTIFIER = "7654321098765432101"
CONTAINERS = (
    "autostock-atlas-morocco-db-1",
    "autostock-atlas-morocco-web-1",
)


def create_bundle(tmp_path: Path):
    database = tmp_path / "database.dump"
    filestore = tmp_path / "filestore.tar"
    manifest = tmp_path / "backup-manifest.json"
    key = tmp_path / "backup-manifest.key"
    database.write_bytes(b"postgres backup bytes")
    filestore.write_bytes(b"odoo filestore archive bytes")

    result = create_backup_manifest(
        database_path=database,
        filestore_path=filestore,
        manifest_path=manifest,
        signing_key_path=key,
        target_uuid=TARGET_UUID,
        postgres_system_identifier=SYSTEM_IDENTIFIER,
        container_names=CONTAINERS,
    )
    return database, filestore, manifest, key, result


def test_local_backup_manifest_round_trip(tmp_path):
    _, _, manifest, key, created = create_bundle(tmp_path)

    checked = validate_manifest_files(
        manifest_path=manifest,
        signing_key_path=key,
        target_uuid=TARGET_UUID,
        postgres_system_identifier=SYSTEM_IDENTIFIER,
        container_names=CONTAINERS,
    )

    assert checked["database_sha256"] == created["database_sha256"]
    assert checked["filestore_sha256"] == created["filestore_sha256"]
    assert key.stat().st_size == 32


def test_local_backup_manifest_detects_artifact_tamper(tmp_path):
    _, filestore, manifest, key, _ = create_bundle(tmp_path)
    filestore.write_bytes(b"changed after signing")

    with pytest.raises(SafetyError, match="does not match"):
        validate_manifest_files(
            manifest_path=manifest,
            signing_key_path=key,
            target_uuid=TARGET_UUID,
            postgres_system_identifier=SYSTEM_IDENTIFIER,
            container_names=CONTAINERS,
        )


def test_local_backup_manifest_refuses_overwrite(tmp_path):
    database, filestore, manifest, key, _ = create_bundle(tmp_path)

    with pytest.raises(ValueError, match="overwrite"):
        create_backup_manifest(
            database_path=database,
            filestore_path=filestore,
            manifest_path=manifest,
            signing_key_path=key,
            target_uuid=TARGET_UUID,
            postgres_system_identifier=SYSTEM_IDENTIFIER,
            container_names=CONTAINERS,
        )
