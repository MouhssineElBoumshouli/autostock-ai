"""Deterministic contract for the already-imported Moroccan showroom state."""

from __future__ import annotations

import hashlib

from .generator import DEFAULT_SEED, generate_dataset
from .import_plan import fixture_records
from .safety import SafetyError


POST_APPLY_STATE_VERSION = 1


def fixture_registry_sha256(records) -> str:
    """Hash the logical fixture registry independently of Odoo record IDs."""
    lines = sorted(
        f"{record.entity}\t{record.entity}:{record.key}\t{record.payload_sha256}"
        for record in records
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def expected_post_apply_state(seed: int = DEFAULT_SEED) -> dict:
    """Return the exact deterministic state expected after the approved Apply."""
    dataset = generate_dataset(seed)
    records = fixture_records(dataset)
    return {
        "state_version": POST_APPLY_STATE_VERSION,
        "dataset_version": dataset.version,
        "dataset_sha256": dataset.digest,
        "fixture_registry_entries": len(records),
        "forecast_requests": sum(
            1 for record in records if record.entity == "forecast_request"
        ),
        "fixture_registry_sha256": fixture_registry_sha256(records),
    }


def validate_post_apply_state(state: dict, seed: int = DEFAULT_SEED) -> None:
    """Require a signed manifest to describe exactly the approved imported state."""
    if not isinstance(state, dict):
        raise SafetyError("Post-Apply state must be a JSON object.")
    expected = expected_post_apply_state(seed)
    if state != expected:
        raise SafetyError("Post-Apply state does not match the approved Moroccan dataset.")
