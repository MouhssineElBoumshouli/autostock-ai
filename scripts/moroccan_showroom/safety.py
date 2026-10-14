"""Fail-closed identity checks for the future isolated Moroccan target."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from pathlib import Path
from uuid import UUID

TARGET_DATABASE = "autostock_atlas_morocco_demo"
TARGET_PROJECT = "autostock-atlas-morocco"
TARGET_POSTGRES_VOLUME = "autostock_atlas_morocco_postgres"
TARGET_FILESTORE_VOLUME = "autostock_atlas_morocco_filestore"
TARGET_WEB_PORT = 8070

LEGACY_DATABASES = {"autostock_showroom_demo"}
LEGACY_PROJECTS = {"autostock-showroom-demo"}
LEGACY_CONTAINERS = {
    "autostock-showroom-demo-odoo-1",
    "autostock-showroom-demo-db-1",
}
LEGACY_VOLUMES = {
    "autostock_ai_showroom_postgres",
    "autostock_ai_showroom_filestore",
}


class SafetyError(ValueError):
    """Raised when a target identity is incomplete, ambiguous, or unsafe."""


@dataclass(frozen=True)
class TargetIdentity:
    database_name: str
    compose_project: str
    postgres_system_identifier: str
    database_uuid: str
    marker_uuid: str
    postgres_volume: str
    filestore_volume: str
    endpoint_host: str
    endpoint_port: int
    container_names: tuple[str, ...] = ()


def validate_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise SafetyError(f"{label} must be a valid UUID.") from error


def validate_target_identity(
    identity: TargetIdentity, *, expected_uuid: str, allow_uninitialized: bool = False
) -> None:
    """Require every identity component and deny all observed legacy resources."""
    database_uuid = validate_uuid(identity.database_uuid, "Database target UUID")
    marker_uuid = validate_uuid(identity.marker_uuid, "Database marker UUID")
    expected_uuid = validate_uuid(expected_uuid, "Expected target UUID")

    if identity.database_name in LEGACY_DATABASES:
        raise SafetyError("The existing USD showroom database is explicitly denied.")
    if identity.compose_project in LEGACY_PROJECTS:
        raise SafetyError("The existing USD showroom Compose project is explicitly denied.")
    if set(identity.container_names) & LEGACY_CONTAINERS:
        raise SafetyError("An existing USD showroom container was included in the target identity.")
    if {identity.postgres_volume, identity.filestore_volume} & LEGACY_VOLUMES:
        raise SafetyError("An existing USD showroom volume was included in the target identity.")

    if identity.database_name != TARGET_DATABASE:
        raise SafetyError("Database name does not match the Moroccan target.")
    if identity.compose_project != TARGET_PROJECT:
        raise SafetyError("Compose project does not match the isolated Moroccan target.")
    if identity.postgres_volume != TARGET_POSTGRES_VOLUME:
        raise SafetyError("PostgreSQL data volume does not match the isolated Moroccan target.")
    if identity.filestore_volume != TARGET_FILESTORE_VOLUME:
        raise SafetyError("Odoo filestore volume does not match the isolated Moroccan target.")
    if database_uuid != expected_uuid or marker_uuid != expected_uuid:
        raise SafetyError("Target UUID and database marker must both match the prepared target.")
    if not re.fullmatch(r"[0-9]{10,}", identity.postgres_system_identifier or ""):
        if not (allow_uninitialized and identity.postgres_system_identifier == "uninitialized"):
            raise SafetyError("PostgreSQL system identifier is missing or malformed.")
    if identity.endpoint_host not in {"127.0.0.1", "localhost"}:
        raise SafetyError("The Moroccan showroom must bind to localhost only.")
    if identity.endpoint_port != TARGET_WEB_PORT:
        raise SafetyError("The Moroccan showroom web port must be the isolated port 8070.")
    if not identity.container_names:
        raise SafetyError("Container names are required for an identity check.")
    if any(TARGET_PROJECT not in name for name in identity.container_names):
        raise SafetyError("A target container name does not identify the Moroccan Compose project.")


def sha256_file(path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a backup artifact without loading it into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def backup_manifest_signature(manifest: dict, signing_key: bytes) -> str:
    """Return the HMAC for the manifest body; the key must remain outside Git."""
    if not signing_key or len(signing_key) < 32:
        raise SafetyError("A private backup-manifest signing key of at least 32 bytes is required.")
    body = {key: value for key, value in manifest.items() if key != "signature_hmac_sha256"}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(signing_key, payload, hashlib.sha256).hexdigest()

def validate_backup_manifest_signature(manifest: dict, signing_key: bytes) -> None:
    """Require the manifest HMAC to match before trusting its contents."""
    signature = manifest.get("signature_hmac_sha256", "")
    expected_signature = backup_manifest_signature(manifest, signing_key)
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected_signature):
        raise SafetyError("Backup manifest signature is invalid.")


def validate_backup_manifest_integrity(
    manifest: dict,
    *,
    expected_uuid: str,
    target_identity: TargetIdentity,
    signing_key: bytes,
    artifact_paths: dict[str, Path] | None = None,
) -> None:
    """Verify signed backup metadata and artifact bytes, not a restore operation.

    A manifest signature proves only that its contents were signed by the
    configured key. It cannot establish that a restore actually ran or passed.
    """
    expected = validate_uuid(expected_uuid, "Expected target UUID")
    validate_target_identity(target_identity, expected_uuid=expected)
    expected_fields = {
        "database_name": TARGET_DATABASE,
        "target_uuid": expected,
        "compose_project": TARGET_PROJECT,
        "postgres_system_identifier": target_identity.postgres_system_identifier,
        "postgres_volume": TARGET_POSTGRES_VOLUME,
        "filestore_volume": TARGET_FILESTORE_VOLUME,
        "endpoint_host": target_identity.endpoint_host,
        "endpoint_port": target_identity.endpoint_port,
    }
    for key, value in expected_fields.items():
        if manifest.get(key) != value:
            raise SafetyError(f"Backup manifest field {key} does not match the verified target.")
    for key in ("database_sha256", "filestore_sha256"):
        value = manifest.get(key, "")
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise SafetyError(f"Backup manifest field {key} must be a SHA-256 digest.")
    validate_backup_manifest_signature(manifest, signing_key)
    for prefix in ("database", "filestore"):
        path = manifest.get(f"{prefix}_path")
        size = manifest.get(f"{prefix}_size_bytes")
        if not path or not isinstance(size, int) or size <= 0:
            raise SafetyError(f"Backup manifest must include a readable {prefix} artifact and size.")
        artifact_path = Path((artifact_paths or {}).get(prefix, path))
        try:
            actual_size = artifact_path.stat().st_size
            actual_hash = sha256_file(artifact_path)
        except OSError as error:
            raise SafetyError(f"Backup {prefix} artifact cannot be read.") from error
        if actual_size != size or actual_hash != manifest[f"{prefix}_sha256"]:
            raise SafetyError(f"Backup {prefix} artifact does not match the signed manifest.")


def require_apply_approval(
    *,
    mode: str,
    typed_target_uuid: str | None = None,
    expected_target_uuid: str | None = None,
    target_identity: TargetIdentity | None = None,
    backup_manifest: dict | None = None,
    backup_signing_key: bytes | None = None,
    backup_artifact_paths: dict[str, Path] | None = None,
    restore_evidence: dict | None = None,
) -> None:
    """Require the exact target, signed backup bytes, and independent restore proof before Apply."""
    if mode not in {"dry-run", "offline-dry-run", "preview", "apply"}:
        raise SafetyError(f"Unsupported execution mode: {mode!r}.")
    if mode in {"dry-run", "offline-dry-run", "preview"}:
        return

    if expected_target_uuid is None:
        raise SafetyError("Apply requires the prepared target UUID.")
    expected = validate_uuid(expected_target_uuid, "Expected target UUID")
    if typed_target_uuid != expected:
        raise SafetyError("Apply requires typing the exact prepared target UUID.")
    if target_identity is None:
        raise SafetyError("Apply requires a complete cross-checked target identity.")
    validate_target_identity(target_identity, expected_uuid=expected)
    if not backup_manifest:
        raise SafetyError("Apply requires a signed database and matching filestore backup.")
    if not backup_signing_key:
        raise SafetyError("Apply requires the private key for backup-manifest integrity checks.")
    validate_backup_manifest_integrity(
        backup_manifest,
        expected_uuid=expected,
        target_identity=target_identity,
        signing_key=backup_signing_key,
        artifact_paths=backup_artifact_paths,
    )
    if not restore_evidence:
        raise SafetyError("Apply requires successful independent restore evidence.")
    # Imported lazily to avoid a module-import cycle: restore_contract itself
    # uses the target/manifest primitives defined in this module.
    from .restore_contract import validate_restore_evidence

    validate_restore_evidence(
        restore_evidence,
        backup_manifest=backup_manifest,
        backup_signing_key=backup_signing_key,
        expected_uuid=expected,
    )
