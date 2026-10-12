"""Generate and preview the Moroccan dataset without connecting to Odoo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .generator import DEFAULT_SEED, generate_dataset
from .import_plan import preview_import
from .safety import SafetyError, TargetIdentity, validate_target_identity


def _identity_from_json(path: Path) -> TargetIdentity:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["container_names"] = tuple(raw.get("container_names", ()))
    return TargetIdentity(**raw)


def build_dry_run_report(dataset, identity: TargetIdentity | None, expected_uuid: str | None) -> dict:
    report = {
        "mode": "offline-dry-run",
        "connected_to_odoo": False,
        "database_mutations": 0,
        "dataset_version": dataset.version,
        "seed": dataset.seed,
        "dataset_sha256": dataset.digest,
        "counts": dataset.counts,
        "planned_stock_ledger_reconciled": True,
        "stock_ledger_scope": "generated target fixture plan per product/location/UoM",
        "forecast_provenance": {
            "profile_products": 24,
            "calendar_days": 181,
            "planned_qualifying_moves": dataset.counts["history_profile_move_count"],
            "source": "fixture plan only; qualifying Odoo moves have not been created or verified",
            "runs_generated": False,
            "manager_reviews_created": False,
            "production_create_date_guard_changed": False,
            "historical_runs_available": False,
        },
        "target_identity": "not_checked",
        "limitations": [
            "Offline preview validates generated fixture data only.",
            "It does not connect to or inspect either showroom database.",
            "Odoo record creation, application checks, and forecast execution remain unperformed.",
        ],
    }
    if identity is not None:
        if not expected_uuid:
            raise SafetyError("An expected UUID is required when checking a target identity.")
        validate_target_identity(identity, expected_uuid=expected_uuid)
        report["target_identity"] = "offline_identity_document_matches"
        report["limitations"].append(
            "The supplied identity document was not collected from a live Docker/Odoo target."
        )
    import_preview = preview_import(dataset)
    report["import_plan"] = {
        "target_state": "not_inspected",
        "planned_entry_count": len(import_preview.actions),
        "entry_actions_if_target_has_no_fixture_records": import_preview.counts,
        "target_snapshot_used": False,
        "writes_performed": 0,
        "idempotency": "same snapshot produces unchanged actions; conflicts abort",
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--identity-json", type=Path)
    parser.add_argument("--expected-target-uuid")
    parser.add_argument("--output", type=Path, help="Write the full deterministic fixture plan.")
    args = parser.parse_args(argv)

    try:
        dataset = generate_dataset(args.seed)
        identity = _identity_from_json(args.identity_json) if args.identity_json else None
        report = build_dry_run_report(dataset, identity, args.expected_target_uuid)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Dry run refused: {error}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(_canonical_plan(dataset))
        report["plan_output"] = str(args.output)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def _canonical_plan(dataset) -> bytes:
    from .generator import canonical_json

    return canonical_json(dataset.as_dict())


if __name__ == "__main__":
    raise SystemExit(main())
