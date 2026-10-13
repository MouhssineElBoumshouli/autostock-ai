import pytest

from scripts.moroccan_showroom.restore_contract import validate_restore_evidence
from scripts.moroccan_showroom.safety import SafetyError, backup_manifest_signature


TARGET_UUID = "0f7d8360-4aa6-48dc-9337-6438f704db12"
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
SIGNING_KEY = b"restore-contract-test-key-32-bytes!!"


def backup_manifest():
    manifest = {
        "database_name": "autostock_atlas_morocco_demo",
        "target_uuid": TARGET_UUID,
        "database_sha256": DIGEST_A,
        "filestore_sha256": DIGEST_B,
    }
    manifest["signature_hmac_sha256"] = backup_manifest_signature(manifest, SIGNING_KEY)
    return manifest


def restore_evidence():
    project = "autostock-restore-proof-ci-123"
    return {
        "restore_project": project,
        "published_ports": [],
        "restore_postgres_volume": f"{project}-postgres",
        "restore_filestore_volume": f"{project}-filestore",
        "restore_database": "autostock_atlas_morocco_demo",
        "backup_database_sha256": DIGEST_A,
        "backup_filestore_sha256": DIGEST_B,
        "pg_restore_succeeded": True,
        "module_state": "installed",
        "marker_uuid": TARGET_UUID,
        "fixture_table_exists": True,
        "source_attachment_sha256": DIGEST_C,
        "restored_attachment_sha256": DIGEST_C,
        "source_filestore_tree_sha256": DIGEST_A,
        "restored_filestore_tree_sha256": DIGEST_A,
        "source_attachment_count": 4,
        "restored_attachment_count": 4,
        "proof_attachment_present": True,
        "cleanup_scope": project,
        "restore_resources_removed": True,
    }


def test_restore_evidence_accepts_isolated_matching_restore():
    validate_restore_evidence(
        restore_evidence(),
        backup_manifest=backup_manifest(),
        backup_signing_key=SIGNING_KEY,
        expected_uuid=TARGET_UUID,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("restore_project", "autostock-atlas-morocco"),
        ("restore_project", "autostock-showroom-demo"),
        ("published_ports", [{"published": "9999"}]),
        ("restore_postgres_volume", "autostock_atlas_morocco_postgres"),
        ("restore_filestore_volume", "autostock_ai_showroom_filestore"),
        ("restore_database", "wrong_database"),
        ("backup_database_sha256", "d" * 64),
        ("backup_filestore_sha256", "e" * 64),
        ("pg_restore_succeeded", False),
        ("module_state", "uninstalled"),
        ("marker_uuid", "11111111-1111-1111-1111-111111111111"),
        ("fixture_table_exists", False),
        ("restored_attachment_sha256", "d" * 64),
        ("restored_filestore_tree_sha256", "d" * 64),
        ("restored_attachment_count", 3),
        ("proof_attachment_present", False),
        ("cleanup_scope", "another-project"),
        ("restore_resources_removed", False),
    ],
)
def test_restore_evidence_fails_closed(field, value):
    evidence = restore_evidence()
    evidence[field] = value
    with pytest.raises(SafetyError):
        validate_restore_evidence(
            evidence,
            backup_manifest=backup_manifest(),
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_restore_evidence_rejects_wrong_or_malformed_backup_binding():
    manifest = backup_manifest()
    manifest["target_uuid"] = "11111111-1111-1111-1111-111111111111"
    with pytest.raises(SafetyError):
        validate_restore_evidence(
            restore_evidence(),
            backup_manifest=manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )

    manifest = backup_manifest()
    manifest["database_sha256"] = "not-a-digest"
    with pytest.raises(SafetyError):
        validate_restore_evidence(
            restore_evidence(),
            backup_manifest=manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_restore_evidence_rejects_manifest_tampered_after_signing():
    manifest = backup_manifest()
    manifest["database_sha256"] = "d" * 64
    evidence = restore_evidence()
    evidence["backup_database_sha256"] = manifest["database_sha256"]

    with pytest.raises(SafetyError, match="signature"):
        validate_restore_evidence(
            evidence,
            backup_manifest=manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )
