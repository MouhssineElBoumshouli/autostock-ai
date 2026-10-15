"""Read-only post-commit verifier for the Moroccan showroom dataset."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys


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

seed = int(os.environ.get("AUTOSTOCK_MOROCCO_DATASET_SEED", generator.DEFAULT_SEED))
dataset = generator.generate_dataset(seed)
expected_entries = len(import_plan.fixture_records(dataset))
expected_forecast_requests = 3 * len(dataset.history_profiles)
report = importer.run_import(env, dataset, mode="dry-run")
expected_actions = {"create": 0, "unchanged": expected_entries}
if report.get("entry_actions") != expected_actions:
    raise RuntimeError(f"Committed fixture registry is incomplete or drifted: {report.get('entry_actions')!r}")

company = env.ref("base.main_company")
if company.autostock_demo_dataset_version != dataset.version:
    raise RuntimeError("Committed company dataset marker does not match the approved dataset.")
registry = env["autostock.morocco.fixture"]
if registry.search_count([]) != expected_entries:
    raise RuntimeError("Committed fixture registry count does not match the approved plan.")
if registry.search_count([("entity", "=", "forecast_request")]) != expected_forecast_requests:
    raise RuntimeError("Committed forecast request registry count is incomplete.")

print(
    json.dumps(
        {
            "status": "passed",
            "dataset_version": dataset.version,
            "dataset_sha256": dataset.digest,
            "fixture_registry_entries": expected_entries,
            "forecast_requests": expected_forecast_requests,
            "entry_actions": report["entry_actions"],
            "target_marker_state": report["target_marker_state"],
            "database_mutations": 0,
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
)
