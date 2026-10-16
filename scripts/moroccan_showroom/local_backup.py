"""Create and re-check a signed backup manifest for the local Moroccan target."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

from .post_apply_state import expected_post_apply_state, validate_post_apply_state
from .safety import (
    TARGET_DATABASE,
    TARGET_FILESTORE_VOLUME,
    TARGET_POSTGRES_VOLUME,
    TARGET_PROJECT,
    TARGET_WEB_PORT,
    TargetIdentity,
    backup_manifest_signature,
    sha256_file,
    validate_backup_manifest_integrity,
    validate_uuid,
)


def target_identity(
    *,
    target_uuid: str,
    postgres_system_identifier: str,
    container_names: tuple[str, ...],
) -> TargetIdentity:
    target_uuid = validate_uuid(target_uuid, "Expected target UUID")
    return TargetIdentity(
        database_name=TARGET_DATABASE,
        compose_project=TARGET_PROJECT,
        postgres_system_identifier=postgres_system_identifier,
        database_uuid=target_uuid,
        marker_uuid=target_uuid,
        postgres_volume=TARGET_POSTGRES_VOLUME,
        filestore_volume=TARGET_FILESTORE_VOLUME,
        endpoint_host="127.0.0.1",
        endpoint_port=TARGET_WEB_PORT,
        container_names=container_names,
    )


def create_backup_manifest(
    *,
    database_path: Path,
    filestore_path: Path,
    manifest_path: Path,
    signing_key_path: Path,
    target_uuid: str,
    postgres_system_identifier: str,
    container_names: tuple[str, ...],
    post_apply: bool = False,
) -> dict:
    """Write a new key + signed manifest, then immediately validate both artifacts."""
    identity = target_identity(
        target_uuid=target_uuid,
        postgres_system_identifier=postgres_system_identifier,
        container_names=container_names,
    )
    if manifest_path.exists() or signing_key_path.exists():
        raise ValueError("Refusing to overwrite an existing backup manifest or signing key.")

    for artifact in (database_path, filestore_path):
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise ValueError(f"Backup artifact is missing or empty: {artifact}")

    signing_key = secrets.token_bytes(32)
    manifest = {
        "database_name": TARGET_DATABASE,
        "target_uuid": validate_uuid(target_uuid, "Expected target UUID"),
        "compose_project": TARGET_PROJECT,
        "postgres_system_identifier": postgres_system_identifier,
        "postgres_volume": TARGET_POSTGRES_VOLUME,
        "filestore_volume": TARGET_FILESTORE_VOLUME,
        "endpoint_host": "127.0.0.1",
        "endpoint_port": TARGET_WEB_PORT,
        "database_path": str(database_path.resolve()),
        "database_size_bytes": database_path.stat().st_size,
        "database_sha256": sha256_file(database_path),
        "filestore_path": str(filestore_path.resolve()),
        "filestore_size_bytes": filestore_path.stat().st_size,
        "filestore_sha256": sha256_file(filestore_path),
    }
    if post_apply:
        manifest["post_apply_state"] = expected_post_apply_state()
    manifest["signature_hmac_sha256"] = backup_manifest_signature(manifest, signing_key)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(signing_key_path, "xb") as stream:
            stream.write(signing_key)
        try:
            os.chmod(signing_key_path, 0o600)
        except OSError:
            pass
        with open(manifest_path, "x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        validate_backup_manifest_integrity(
            manifest,
            expected_uuid=target_uuid,
            target_identity=identity,
            signing_key=signing_key,
        )
    except Exception:
        signing_key_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest


def validate_manifest_files(
    *,
    manifest_path: Path,
    signing_key_path: Path,
    target_uuid: str,
    postgres_system_identifier: str,
    container_names: tuple[str, ...],
) -> dict:
    identity = target_identity(
        target_uuid=target_uuid,
        postgres_system_identifier=postgres_system_identifier,
        container_names=container_names,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    signing_key = signing_key_path.read_bytes()
    validate_backup_manifest_integrity(
        manifest,
        expected_uuid=target_uuid,
        target_identity=identity,
        signing_key=signing_key,
    )
    if "post_apply_state" in manifest:
        validate_post_apply_state(manifest["post_apply_state"])
    return manifest


def _add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-uuid", required=True)
    parser.add_argument("--postgres-system-identifier", required=True)
    parser.add_argument("--container-name", action="append", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a new signed backup manifest.")
    _add_identity_args(create)
    create.add_argument("--database-path", type=Path, required=True)
    create.add_argument("--filestore-path", type=Path, required=True)
    create.add_argument("--manifest-path", type=Path, required=True)
    create.add_argument("--signing-key-path", type=Path, required=True)
    create.add_argument(
        "--post-apply",
        action="store_true",
        help="Bind the signed manifest to the exact approved imported dataset state.",
    )

    check = subparsers.add_parser("validate", help="Re-check an existing manifest and artifacts.")
    _add_identity_args(check)
    check.add_argument("--manifest-path", type=Path, required=True)
    check.add_argument("--signing-key-path", type=Path, required=True)

    args = parser.parse_args(argv)
    names = tuple(args.container_name)

    try:
        if args.command == "create":
            manifest = create_backup_manifest(
                database_path=args.database_path,
                filestore_path=args.filestore_path,
                manifest_path=args.manifest_path,
                signing_key_path=args.signing_key_path,
                target_uuid=args.target_uuid,
                postgres_system_identifier=args.postgres_system_identifier,
                container_names=names,
                post_apply=args.post_apply,
            )
        else:
            manifest = validate_manifest_files(
                manifest_path=args.manifest_path,
                signing_key_path=args.signing_key_path,
                target_uuid=args.target_uuid,
                postgres_system_identifier=args.postgres_system_identifier,
                container_names=names,
            )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"Backup manifest refused: {error}")
        return 2

    print(
        json.dumps(
            {
                "status": "passed",
                "database_name": manifest["database_name"],
                "target_uuid": manifest["target_uuid"],
                "database_sha256": manifest["database_sha256"],
                "filestore_sha256": manifest["filestore_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
