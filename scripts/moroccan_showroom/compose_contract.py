"""Fail-closed checks for the Moroccan Compose and Docker mount boundary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .safety import (
    SafetyError,
    TARGET_FILESTORE_VOLUME,
    TARGET_POSTGRES_VOLUME,
    TARGET_PROJECT,
    validate_uuid,
)

TARGET_NETWORK = "autostock-atlas-morocco-private"
NETWORK_KEY = "morocco_private"
DATABASE_TARGET = "/var/lib/postgresql/data"
FILESTORE_TARGET = "/var/lib/odoo"
ADDONS_TARGET = "/mnt/extra-addons"
SCRIPTS_TARGET = "/mnt/atlas-morocco"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SafetyError(message)


def _property_names(value: object) -> set[str]:
    _require(isinstance(value, dict), "Compose object must be a JSON object.")
    return set(value)


def _path_key(value: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(value)))


def _mount_signature(mount: dict) -> tuple[str, str, str, bool]:
    _require(isinstance(mount, dict), "Every configured mount must be an object.")
    mount_type = mount.get("type")
    source = mount.get("source")
    target = mount.get("target")
    read_only = mount.get("read_only", False)
    _require(mount_type in {"volume", "bind"}, "Mount type must be volume or bind.")
    _require(isinstance(source, str) and source, "Every mount needs a source.")
    _require(isinstance(target, str) and target, "Every mount needs a target.")
    _require(isinstance(read_only, bool), "Mount read_only must be an explicit boolean.")
    if mount_type == "bind":
        source = _path_key(source)
    return mount_type, source, target, read_only


def validate_compose_config(config: dict, *, repo_root: Path, expected_uuid: str) -> None:
    """Validate the resolved Compose resources and exact host/volume mounts."""
    expected_uuid = validate_uuid(expected_uuid, "Expected target UUID")
    _require(config.get("name") == TARGET_PROJECT, "Compose project name does not match the Moroccan target.")

    services = config.get("services")
    _require(_property_names(services) == {"db", "web"}, "Only the isolated db and web services are allowed.")
    volumes = config.get("volumes")
    _require(_property_names(volumes) == {"morocco_postgres", "morocco_filestore"}, "Unexpected Compose volume declaration.")
    volume_names = {
        key: spec.get("name")
        for key, spec in volumes.items()
        if isinstance(spec, dict)
    }
    _require(
        volume_names == {
            "morocco_postgres": TARGET_POSTGRES_VOLUME,
            "morocco_filestore": TARGET_FILESTORE_VOLUME,
        },
        "Compose volume names do not match the isolated Moroccan database and filestore.",
    )

    networks = config.get("networks")
    _require(_property_names(networks) == {NETWORK_KEY}, "Unexpected Compose network declaration.")
    network = networks[NETWORK_KEY]
    _require(isinstance(network, dict), "Moroccan network declaration is malformed.")
    _require(network.get("name") == TARGET_NETWORK, "Moroccan network name is not isolated.")
    labels = network.get("labels")
    _require(isinstance(labels, dict), "Moroccan network labels are missing.")
    _require(
        labels.get("com.autostock.target-uuid") == expected_uuid,
        "Moroccan network must carry the prepared target UUID label.",
    )

    for service_name, service in services.items():
        _require(isinstance(service, dict), f"Compose service {service_name} is malformed.")
        _require(
            _property_names(service.get("networks")) == {NETWORK_KEY},
            f"Compose service {service_name} must attach only to the private Moroccan network.",
        )

    db = services["db"]
    web = services["web"]
    _require(not db.get("ports"), "PostgreSQL must not publish a host port.")
    web_ports = web.get("ports") or []
    _require(len(web_ports) == 1, "Odoo must publish exactly one local port.")
    port = web_ports[0]
    _require(isinstance(port, dict), "Odoo port mapping is malformed.")
    _require(
        port.get("host_ip") == "127.0.0.1"
        and str(port.get("published")) == "8070"
        and str(port.get("target")) == "8069",
        "Odoo must bind 127.0.0.1:8070 to container port 8069.",
    )

    db_mounts = [_mount_signature(item) for item in db.get("volumes", [])]
    _require(
        db_mounts == [("volume", "morocco_postgres", DATABASE_TARGET, False)],
        "PostgreSQL must use only its dedicated volume at /var/lib/postgresql/data.",
    )
    web_mounts = [_mount_signature(item) for item in web.get("volumes", [])]
    expected_web_mounts = [
        ("volume", "morocco_filestore", FILESTORE_TARGET, False),
        ("bind", _path_key(str(repo_root / "addons")), ADDONS_TARGET, True),
        ("bind", _path_key(str(repo_root / "scripts" / "moroccan_showroom")), SCRIPTS_TARGET, True),
    ]
    _require(
        sorted(web_mounts) == sorted(expected_web_mounts),
        "Odoo must use only the dedicated filestore and the two expected read-only bind mounts.",
    )


def validate_container_inspect(
    evidence: dict, *, repo_root: Path, expected_uuid: str
) -> None:
    """Validate an existing target container's identity, mounts, and network."""
    expected_uuid = validate_uuid(expected_uuid, "Expected target UUID")
    labels = evidence.get("labels")
    _require(isinstance(labels, dict), "Container identity labels are missing.")
    service = labels.get("com.docker.compose.service")
    _require(service in {"db", "web"}, "Target container is not a declared Moroccan service.")
    _require(labels.get("com.docker.compose.project") == TARGET_PROJECT, "Container belongs to another Compose project.")
    _require(labels.get("com.autostock.target-uuid") == expected_uuid, "Container target UUID does not match.")
    name = str(evidence.get("name", "")).lstrip("/")
    _require(TARGET_PROJECT in name, "Container name does not identify the Moroccan project.")

    mounts = evidence.get("mounts")
    _require(isinstance(mounts, list), "Container mount evidence is missing.")
    actual = []
    for mount in mounts:
        _require(isinstance(mount, dict), "Container mount evidence is malformed.")
        mount_type = mount.get("Type")
        target = mount.get("Destination")
        read_write = mount.get("RW")
        _require(isinstance(target, str) and target, "Container mount destination is missing.")
        _require(isinstance(read_write, bool), "Container mount access mode is unknown.")
        if mount_type == "volume":
            source = mount.get("Name")
            _require(isinstance(source, str) and source, "Named volume identity is missing from the container mount.")
        elif mount_type == "bind":
            source = mount.get("Source")
            _require(isinstance(source, str) and source, "Bind mount source is missing from the container mount.")
            source = _path_key(source)
        else:
            raise SafetyError("Container has an unsupported mount type.")
        actual.append((mount_type, source, target, read_write))

    if service == "db":
        expected_mounts = [("volume", TARGET_POSTGRES_VOLUME, DATABASE_TARGET, True)]
    else:
        expected_mounts = [
            ("volume", TARGET_FILESTORE_VOLUME, FILESTORE_TARGET, True),
            ("bind", _path_key(str(repo_root / "addons")), ADDONS_TARGET, False),
            ("bind", _path_key(str(repo_root / "scripts" / "moroccan_showroom")), SCRIPTS_TARGET, False),
        ]
    _require(
        sorted(actual) == sorted(expected_mounts),
        f"Live {service} mounts differ from the isolated read/write contract.",
    )

    attached_networks = evidence.get("networks")
    _require(
        isinstance(attached_networks, list) and attached_networks == [TARGET_NETWORK],
        f"Live {service} container must attach only to the private Moroccan network.",
    )


def validate_network_inspect(
    evidence: dict,
    *,
    target_container_ids: set[str],
    expected_uuid: str,
) -> None:
    """Ensure a pre-existing named network belongs only to this target."""
    expected_uuid = validate_uuid(expected_uuid, "Expected target UUID")
    _require(evidence.get("name") == TARGET_NETWORK, "Existing network name does not match the Moroccan target.")
    labels = evidence.get("labels")
    _require(isinstance(labels, dict), "Network identity labels are missing.")
    _require(labels.get("com.docker.compose.project") == TARGET_PROJECT, "Existing network belongs to another Compose project.")
    _require(labels.get("com.autostock.target-uuid") == expected_uuid, "Existing network target UUID does not match.")
    attached_ids = evidence.get("container_ids")
    _require(isinstance(attached_ids, list), "Network attachment evidence is missing.")
    _require(
        set(attached_ids).issubset(target_container_ids),
        "Moroccan network has an endpoint outside its own Compose project.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("config", "container", "network"), required=True)
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--target-uuid", required=True)
    parser.add_argument("--target-container-id", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence_json.read_text(encoding="utf-8"))
        if args.mode == "config":
            validate_compose_config(evidence, repo_root=args.repo_root, expected_uuid=args.target_uuid)
        elif args.mode == "container":
            validate_container_inspect(evidence, repo_root=args.repo_root, expected_uuid=args.target_uuid)
        else:
            validate_network_inspect(
                evidence,
                target_container_ids=set(args.target_container_id),
                expected_uuid=args.target_uuid,
            )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Moroccan Compose isolation check refused: {error}", file=sys.stderr)
        return 2
    print(f"Moroccan {args.mode} isolation evidence passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
