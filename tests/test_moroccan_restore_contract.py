import hashlib
import hmac
import json

import pytest

from scripts.moroccan_showroom.restore_contract import (
    main as restore_contract_main,
    sign_restore_evidence,
    validate_restore_evidence,
)
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


def signed_restore_evidence(manifest=None, evidence=None):
    manifest = manifest or backup_manifest()
    return sign_restore_evidence(
        evidence or restore_evidence(),
        backup_manifest=manifest,
        backup_signing_key=SIGNING_KEY,
    )


def test_backup_manifest_hmac_format_remains_compatible():
    manifest = backup_manifest()
    unsigned = {
        key: value
        for key, value in manifest.items()
        if key != "signature_hmac_sha256"
    }
    payload = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert backup_manifest_signature(unsigned, SIGNING_KEY) == hmac.new(
        SIGNING_KEY,
        payload,
        hashlib.sha256,
    ).hexdigest()


def test_restore_evidence_accepts_isolated_matching_restore():
    validate_restore_evidence(
        signed_restore_evidence(),
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
    evidence = signed_restore_evidence()
    evidence[field] = value
    with pytest.raises(SafetyError, match="Restore evidence signature is invalid"):
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
            signed_restore_evidence(),
            backup_manifest=manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )

    manifest = backup_manifest()
    manifest["database_sha256"] = "not-a-digest"
    with pytest.raises(SafetyError):
        validate_restore_evidence(
            signed_restore_evidence(),
            backup_manifest=manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_restore_evidence_rejects_manifest_tampered_after_signing():
    manifest = backup_manifest()
    evidence = signed_restore_evidence(manifest)
    manifest["database_sha256"] = "d" * 64

    with pytest.raises(SafetyError, match="signature"):
        validate_restore_evidence(
            evidence,
            backup_manifest=manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_restore_evidence_cannot_be_replayed_against_another_signed_backup():
    first_manifest = backup_manifest()
    evidence = signed_restore_evidence(first_manifest)
    second_manifest = backup_manifest()
    second_manifest["database_sha256"] = "d" * 64
    second_manifest["signature_hmac_sha256"] = backup_manifest_signature(
        second_manifest,
        SIGNING_KEY,
    )

    with pytest.raises(SafetyError, match="different signed backup manifest"):
        validate_restore_evidence(
            evidence,
            backup_manifest=second_manifest,
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_unsigned_restore_evidence_is_rejected_before_field_validation():
    evidence = restore_evidence()
    evidence["pg_restore_succeeded"] = False

    with pytest.raises(SafetyError, match="Restore evidence signature is invalid"):
        validate_restore_evidence(
            evidence,
            backup_manifest=backup_manifest(),
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_non_hex_restore_signature_is_a_specific_authentication_failure():
    evidence = signed_restore_evidence()
    evidence["restore_evidence_hmac_sha256"] = "ñ" * 64

    with pytest.raises(SafetyError, match="Restore evidence signature is invalid"):
        validate_restore_evidence(
            evidence,
            backup_manifest=backup_manifest(),
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_authentic_but_failed_restore_is_rejected_by_the_restore_contract():
    evidence = restore_evidence()
    evidence["pg_restore_succeeded"] = False
    signed = signed_restore_evidence(evidence=evidence)

    with pytest.raises(SafetyError, match="PostgreSQL restore did not succeed"):
        validate_restore_evidence(
            signed,
            backup_manifest=backup_manifest(),
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_restore_evidence_signature_covers_unknown_finalized_fields():
    evidence = restore_evidence()
    evidence["cleanup_observation"] = "all verifier resources absent"
    signed = signed_restore_evidence(evidence=evidence)
    signed["cleanup_observation"] = "changed after signing"

    with pytest.raises(SafetyError, match="Restore evidence signature is invalid"):
        validate_restore_evidence(
            signed,
            backup_manifest=backup_manifest(),
            backup_signing_key=SIGNING_KEY,
            expected_uuid=TARGET_UUID,
        )


def test_restore_contract_cli_signs_and_revalidates_finalized_evidence(tmp_path):
    manifest = backup_manifest()
    evidence_path = tmp_path / "restore-evidence.json"
    manifest_path = tmp_path / "backup-manifest.json"
    key_path = tmp_path / "backup-manifest.key"
    evidence_path.write_text(json.dumps(restore_evidence()), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    key_path.write_bytes(SIGNING_KEY)

    result = restore_contract_main(
        [
            "--evidence-json", str(evidence_path),
            "--backup-manifest-json", str(manifest_path),
            "--signing-key-file", str(key_path),
            "--expected-target-uuid", TARGET_UUID,
            "--sign-evidence",
        ]
    )

    signed = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 0
    assert (
        signed["backup_manifest_signature_hmac_sha256"]
        == manifest["signature_hmac_sha256"]
    )
    assert signed["backup_manifest_sha256"]
    assert signed["restore_evidence_hmac_sha256"]
    validate_restore_evidence(
        signed,
        backup_manifest=manifest,
        backup_signing_key=SIGNING_KEY,
        expected_uuid=TARGET_UUID,
    )
