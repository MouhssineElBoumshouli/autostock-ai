"""Validate evidence from an actual isolated Moroccan backup restore."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .safety import (
    LEGACY_PROJECTS,
    LEGACY_VOLUMES,
    SafetyError,
    TARGET_DATABASE,
    TARGET_FILESTORE_VOLUME,
    TARGET_POSTGRES_VOLUME,
    TARGET_PROJECT,
    validate_backup_manifest_signature,
    validate_uuid,
)

RESTORE_PROJECT_PREFIX = "autostock-restore-proof-"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SafetyError(message)


def _sha256(value, label: str) -> str:
    _require(
        isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None,
        f"{label} must be a SHA-256 digest.",
    )
    return value


def validate_restore_evidence(
    evidence: dict,
    *,
    backup_manifest: dict,
    backup_signing_key: bytes,
    expected_uuid: str,
) -> None:
    """Require a real restore result isolated from both showroom environments."""
    expected_uuid = validate_uuid(expected_uuid, "Expected target UUID")
    validate_backup_manifest_signature(backup_manifest, backup_signing_key)

    _require(
        backup_manifest.get("database_name") == TARGET_DATABASE,
        "Backup database is not the Moroccan target.",
    )
    _require(
        backup_manifest.get("target_uuid") == expected_uuid,
        "Backup target UUID does not match.",
    )
    database_hash = _sha256(
        backup_manifest.get("database_sha256"), "Backup database hash"
    )
    filestore_hash = _sha256(
        backup_manifest.get("filestore_sha256"), "Backup filestore hash"
    )

    project = evidence.get("restore_project")
    _require(
        isinstance(project, str) and project.startswith(RESTORE_PROJECT_PREFIX),
        "Restore project name is not a disposable restore-proof project.",
    )
    _require(
        project not in LEGACY_PROJECTS and project != TARGET_PROJECT,
        "Restore project overlaps a showroom project.",
    )
    _require(
        evidence.get("published_ports") == [],
        "Restore proof must not publish host ports.",
    )

    postgres_volume = evidence.get("restore_postgres_volume")
    filestore_volume = evidence.get("restore_filestore_volume")
    forbidden_volumes = set(LEGACY_VOLUMES) | {
        TARGET_POSTGRES_VOLUME,
        TARGET_FILESTORE_VOLUME,
    }
    _require(
        postgres_volume not in forbidden_volumes,
        "Restore PostgreSQL volume overlaps a showroom volume.",
    )
    _require(
        filestore_volume not in forbidden_volumes,
        "Restore filestore volume overlaps a showroom volume.",
    )
    _require(
        isinstance(postgres_volume, str) and postgres_volume.startswith(project),
        "Restore PostgreSQL volume is not owned by the restore project.",
    )
    _require(
        isinstance(filestore_volume, str) and filestore_volume.startswith(project),
        "Restore filestore volume is not owned by the restore project.",
    )

    _require(
        evidence.get("restore_database") == TARGET_DATABASE,
        "Restore database name changed unexpectedly.",
    )
    _require(
        evidence.get("backup_database_sha256") == database_hash,
        "Restored run used a different database backup.",
    )
    _require(
        evidence.get("backup_filestore_sha256") == filestore_hash,
        "Restored run used a different filestore backup.",
    )
    _require(
        evidence.get("pg_restore_succeeded") is True,
        "PostgreSQL restore did not succeed.",
    )
    _require(
        evidence.get("module_state") == "installed",
        "Restored AutoStock module is not installed.",
    )
    _require(
        evidence.get("marker_uuid") == expected_uuid,
        "Restored target marker UUID does not match.",
    )
    _require(
        evidence.get("fixture_table_exists") is True,
        "Restored AutoStock fixture table is missing.",
    )

    source_attachment = _sha256(
        evidence.get("source_attachment_sha256"),
        "Source proof attachment hash",
    )
    restored_attachment = _sha256(
        evidence.get("restored_attachment_sha256"),
        "Restored proof attachment hash",
    )
    _require(
        source_attachment == restored_attachment,
        "Restored proof attachment bytes differ from the source.",
    )

    source_tree = _sha256(
        evidence.get("source_filestore_tree_sha256"),
        "Source filestore tree hash",
    )
    restored_tree = _sha256(
        evidence.get("restored_filestore_tree_sha256"),
        "Restored filestore tree hash",
    )
    _require(
        source_tree == restored_tree,
        "Restored filestore tree differs from the backup source.",
    )

    source_count = evidence.get("source_attachment_count")
    restored_count = evidence.get("restored_attachment_count")
    _require(
        isinstance(source_count, int)
        and source_count > 0
        and restored_count == source_count,
        "Restored attachment count does not match the source.",
    )
    _require(
        evidence.get("proof_attachment_present") is True,
        "Restore proof attachment is missing.",
    )

    _require(
        evidence.get("cleanup_scope") == project,
        "Cleanup scope does not match the disposable restore project.",
    )
    _require(
        evidence.get("restore_resources_removed") is True,
        "Disposable restore resources were not removed.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--backup-manifest-json", type=Path, required=True)
    parser.add_argument("--signing-key-file", type=Path, required=True)
    parser.add_argument("--expected-target-uuid", required=True)
    args = parser.parse_args(argv)

    try:
        evidence = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        manifest = json.loads(
            args.backup_manifest_json.read_text(encoding="utf-8")
        )
        signing_key = args.signing_key_file.read_bytes()
        validate_restore_evidence(
            evidence,
            backup_manifest=manifest,
            backup_signing_key=signing_key,
            expected_uuid=args.expected_target_uuid,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Restore evidence refused: {error}")
        return 2

    print("Independent Moroccan backup restore evidence passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
