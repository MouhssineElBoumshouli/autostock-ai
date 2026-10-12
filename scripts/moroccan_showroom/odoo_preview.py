"""Read-only Odoo shell preview for the pinned Moroccan data plan.

Run this file through ``odoo shell`` only after a separate, approved target has
been initialized. It deliberately exposes no Apply mode.
"""

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
            raise RuntimeError("The read-only Moroccan fixture package could not be loaded.")
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        return package


package = _load_fixture_package()
generator = importlib.import_module(f"{package.__name__}.generator")
importer = importlib.import_module(f"{package.__name__}.odoo_importer")
seed = int(os.environ.get("AUTOSTOCK_MOROCCO_DATASET_SEED", generator.DEFAULT_SEED))
dataset = generator.generate_dataset(seed)
report = importer.run_import(env, dataset, mode="dry-run")
print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
