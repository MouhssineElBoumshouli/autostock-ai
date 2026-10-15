"""Guarded Odoo-shell Apply runner for the approved Moroccan dataset."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys


BACKUP_DIR = Path("/mnt/atlas-backup")


def _load_fixture_package():
    try:
        return importlib.import_module("scripts.moroccan_showroom")
    except ImportError:
        package_path = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            "autostock_moroccan_showroom",
            package_path / "__init__.py",
            submodule_search_locations=[str(package_path)],
        )
        if not spec or not spec.loader:
            raise RuntimeError("The Moroccan fixture package could not be loaded.")
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        return package


package = _load_fixture_package()
generator = importlib.import_module(f"{package.__name__}.generator")
import_plan = importlib.import_module(f"{package.__name__}.import_plan")
importer = importlib.import_module(f"{package.__name__}.odoo_importer")
local_backup = importlib.import_module(f"{package.__name__}.local_backup")

seed = int(os.environ.get("AUTOSTOCK_MOROCCO_DATASET_SEED", generator.DEFAULT_SEED))
typed_uuid = os.environ.get("AUTOSTOCK_MOROCCO_TYPED_TARGET_UUID", "")
system_identifier = os.environ.get("AUTOSTOCK_MOROCCO_POSTGRES_SYSTEM_IDENTIFIER", "")
db_container_name = os.environ.get("AUTOSTOCK_MOROCCO_DB_CONTAINER_NAME", "")
web_container_name = os.environ.get("AUTOSTOCK_MOROCCO_WEB_CONTAINER_NAME", "")
container_names = (db_container_name, web_container_name)
if not all(container_names):
    raise RuntimeError("The guarded Apply runner requires both verified Moroccan container names.")

manifest = json.loads((BACKUP_DIR / "backup-manifest.json").read_text(encoding="utf-8"))
signing_key = (BACKUP_DIR / "backup-manifest.key").read_bytes()
restore_evidence = json.loads((BACKUP_DIR / "restore-evidence.json").read_text(encoding="utf-8"))
identity = local_backup.target_identity(
    target_uuid=typed_uuid,
    postgres_system_identifier=system_identifier,
    container_names=container_names,
)
dataset = generator.generate_dataset(seed)
expected_entries = len(import_plan.fixture_records(dataset))
expected_forecast_requests = 3 * len(dataset.history_profiles)

try:
    apply_report = importer.run_import(
        env,
        dataset,
        mode="apply",
        typed_target_uuid=typed_uuid,
        target_identity=identity,
        backup_manifest=manifest,
        backup_signing_key=signing_key,
        backup_artifact_paths={
            "database": BACKUP_DIR / "database.dump",
            "filestore": BACKUP_DIR / "filestore.tar",
        },
        restore_evidence=restore_evidence,
    )

    if apply_report.get("mode") not in {"apply", "apply-noop"}:
        raise RuntimeError(f"Unexpected guarded Apply result: {apply_report.get('mode')!r}")
    if apply_report.get("dataset_sha256") != dataset.digest:
        raise RuntimeError("Guarded Apply result does not match the approved dataset digest.")

    verification = importer.run_import(env, dataset, mode="dry-run")
    expected_actions = {"create": 0, "unchanged": expected_entries}
    if verification.get("entry_actions") != expected_actions:
        raise RuntimeError(
            f"Post-Apply registry verification failed: {verification.get('entry_actions')!r}"
        )
    company = env.ref("base.main_company")
    if company.autostock_demo_dataset_version != dataset.version:
        raise RuntimeError("Post-Apply company dataset marker does not match the approved dataset.")
    registry = env["autostock.morocco.fixture"]
    if registry.search_count([]) != expected_entries:
        raise RuntimeError("Post-Apply fixture registry count does not match the approved plan.")
    if registry.search_count([("entity", "=", "forecast_request")]) != expected_forecast_requests:
        raise RuntimeError("Post-Apply forecast request registry count is incomplete.")

    env.cr.commit()
except Exception:
    env.cr.rollback()
    raise

print(
    json.dumps(
        {
            "status": "passed",
            "apply": apply_report,
            "verification": {
                "dataset_version": dataset.version,
                "dataset_sha256": dataset.digest,
                "fixture_registry_entries": expected_entries,
                "forecast_requests": expected_forecast_requests,
                "entry_actions": verification["entry_actions"],
                "target_marker_state": verification["target_marker_state"],
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
)
