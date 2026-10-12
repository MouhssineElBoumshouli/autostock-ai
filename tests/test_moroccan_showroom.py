from collections import defaultdict
from datetime import date
import hashlib
import pytest

from scripts.moroccan_showroom.generator import (
    END_DATE,
    FOCUS_START,
    HISTORY_START,
    FORECAST_PROFILE_COUNT,
    _event_time_utc,
    canonical_json,
    generate_dataset,
)
from scripts.moroccan_showroom.safety import (
    SafetyError,
    TargetIdentity,
    backup_manifest_signature,
    require_apply_approval,
    validate_backup_manifest,
    validate_target_identity,
)
from scripts.moroccan_showroom.import_plan import FixtureRecord, preview_import
from scripts.moroccan_showroom.cli import build_dry_run_report


TARGET_UUID = "0f7d8360-4aa6-48dc-9337-6438f704db12"


def safe_identity(**changes):
    fields = {
        "database_name": "autostock_atlas_morocco_demo",
        "compose_project": "autostock-atlas-morocco",
        "postgres_system_identifier": "7654321098765432109",
        "database_uuid": TARGET_UUID,
        "marker_uuid": TARGET_UUID,
        "postgres_volume": "autostock_atlas_morocco_postgres",
        "filestore_volume": "autostock_atlas_morocco_filestore",
        "endpoint_host": "127.0.0.1",
        "endpoint_port": 8070,
        "container_names": (
            "autostock-atlas-morocco-db-1",
            "autostock-atlas-morocco-web-1",
        ),
    }
    fields.update(changes)
    return TargetIdentity(**fields)


def test_dataset_is_deterministic_and_hits_approved_counts():
    first = generate_dataset()
    second = generate_dataset()

    assert first.digest == second.digest
    assert first.as_dict() == second.as_dict()
    assert canonical_json(first.as_dict()) == canonical_json(second.as_dict())
    expected_counts = {
        "companies": 1,
        "warehouses": 2,
        "products": 150,
        "suppliers": 8,
        "customers": 18,
        "focus_completed_orders": 350,
        "focus_completed_delivery_lines": 1050,
        "receipt_pickings": 30,
        "linked_customer_returns": 12,
        "internal_transfer_journeys": 18,
        "open_customer_orders": 20,
        "history_profiles": 24,
        "history_calendar_days_per_profile": 181,
    }
    assert {key: first.counts[key] for key in expected_counts} == expected_counts
    assert first.counts["history_orders_before_focus"] > 0
    assert first.counts["history_profile_move_count"] > 0
    assert first.digest == generate_dataset(seed=36036).digest
    assert first.digest != generate_dataset(seed=36037).digest


def test_product_and_partner_keys_are_new_and_currency_is_explicit():
    data = generate_dataset()

    assert len({product.key for product in data.products}) == 150
    assert len({product.sku for product in data.products}) == 150
    assert all(product.sale_price_mad > 0 for product in data.products)
    assert all(
        term.currency == "MAD"
        and term.moq > 0
        and term.ordering_uom == product.inventory_uom
        for product in data.products
        for term in product.supplier_terms
    )
    assert len({supplier["key"] for supplier in data.suppliers}) == 8
    assert len({customer["key"] for customer in data.customers}) == 18
    assert all(supplier["fictional"] for supplier in data.suppliers)
    assert all(customer["fictional"] for customer in data.customers)
    assert not any("create_date" in product for product in data.as_dict()["products"])
    assert all(product.history_profile_key for product in data.products[:24])
    assert all(product.history_profile_key is None for product in data.products[24:])


def test_history_coverage_is_contiguous_and_scoped_to_profiles():
    data = generate_dataset()
    rows_by_sku = defaultdict(list)
    for row in data.daily_observations:
        rows_by_sku[row["sku"]].append(row)

    assert len(rows_by_sku) == FORECAST_PROFILE_COUNT
    expected_days = (END_DATE - HISTORY_START).days + 1
    for rows in rows_by_sku.values():
        rows.sort(key=lambda row: row["day"])
        assert len(rows) == expected_days == 181
        assert rows[0]["day"] == HISTORY_START
        assert rows[-1]["day"] == END_DATE
        assert all(row["coverage_complete"] for row in rows)
        assert all(row["delivered_units"] >= 0 for row in rows)
        assert all(row["returned_units"] >= 0 for row in rows)
    assert all(row["day"] <= END_DATE for row in data.daily_observations)
    assert len(data.history_profiles) == FORECAST_PROFILE_COUNT
    assert all(
        profile["status"] == "fixture_plan_only_not_verified_in_odoo"
        and profile["calendar_days"] == 181
        and len(profile["planned_daily_rows_sha256"]) == 64
        for profile in data.history_profiles
    )


def test_order_delivery_return_and_transfer_links_are_coherent():
    data = generate_dataset()
    orders = {order.key: order for order in data.orders}
    delivered_movements = {
        movement.key: movement
        for movement in data.movements
        if movement.kind == "sale_delivery"
    }

    assert sum(
        1
        for order in data.orders
        if order.state == "delivered"
        and FOCUS_START <= order.day <= END_DATE
    ) == 350
    for order in data.orders:
        assert len(order.lines) in range(1, 6)
        if order.state == "delivered":
            for line in order.lines:
                delivery = delivered_movements[line.movement_key]
                assert delivery.order_key == order.key
                assert delivery.day == order.day
                assert delivery.quantity == line.quantity

    returns = [item for item in data.movements if item.kind == "customer_return"]
    assert len(returns) == 12
    for returned in returns:
        original = delivered_movements[returned.original_movement_key]
        original_order = orders[original.order_key]
        assert returned.day > original.day
        assert returned.quantity <= original.quantity
        assert returned.sku == original.sku
        assert original_order.customer_key == returned.partner_key

    transfers = [item for item in data.movements if item.kind == "internal_transfer"]
    assert len(transfers) == 18
    assert all(item.source != item.destination for item in transfers)
    assert all(item.journey_key for item in transfers)


def test_location_ledgers_reconcile_without_negative_intermediate_stock():
    data = generate_dataset()
    running = defaultdict(int)
    for movement in data.movements:
        if movement.kind == "opening_adjustment":
            running[(movement.sku, movement.destination)] += movement.quantity
        elif movement.kind in {"vendor_receipt", "customer_return"}:
            running[(movement.sku, movement.destination)] += movement.quantity
        elif movement.kind == "sale_delivery":
            running[(movement.sku, movement.source)] -= movement.quantity
        elif movement.kind == "internal_transfer":
            running[(movement.sku, movement.source)] -= movement.quantity
            running[(movement.sku, movement.destination)] += movement.quantity
        else:
            pytest.fail(f"Unexpected physical movement: {movement.kind}")
        assert all(quantity >= 0 for quantity in running.values())

    planned = {
        (row["sku"], row["warehouse_key"]): row["on_hand"]
        for row in data.ending_on_hand
    }
    assert all(running.get(key, 0) == value for key, value in planned.items())
    assert all(isinstance(value, int) for value in planned.values())
    assert any(value == 0 for value in planned.values())
    assert planned[(data.products[0].sku, "warehouse_atlas_central")] == 0
    assert (
        planned[(data.products[1].sku, "warehouse_atlas_central")]
        < data.products[1].reorder_minimum
    )
    assert (
        planned[(data.products[2].sku, "warehouse_atlas_central")]
        > data.products[2].reorder_maximum
    )


def test_open_orders_are_reservations_not_physical_movements():
    data = generate_dataset()
    assert len(data.open_orders) == 20
    assert not any(
        movement.order_key in {order.key for order in data.open_orders}
        for movement in data.movements
    )
    assert all(
        order.reservation_policy
        == "reserve_with_native_odoo_rules_when_available_otherwise_wait"
        for order in data.open_orders
    )


def test_import_dry_run_is_idempotent_and_aborts_on_duplicate_or_drift():
    data = generate_dataset()
    first = preview_import(data)
    assert first.counts["create"] == len(first.actions)
    assert first.counts["unchanged"] == 0

    existing = tuple(
        FixtureRecord(record.entity, record.key, record.payload_sha256)
        for record in first.actions
    )
    second = preview_import(data, existing)
    assert second.counts["create"] == 0
    assert second.counts["unchanged"] == len(second.actions)
    with pytest.raises(SafetyError, match="partial or unexpected"):
        preview_import(data, existing[:-1])
    with pytest.raises(SafetyError, match="partial or unexpected"):
        preview_import(data, existing + (FixtureRecord("unexpected", "old_entry", "c" * 64),))

    one = first.actions[0]
    duplicate = FixtureRecord(one.entity, one.key, one.payload_sha256)
    with pytest.raises(SafetyError, match="duplicate"):
        preview_import(data, existing + (duplicate,))

    conflict = FixtureRecord(one.entity, one.key, "f" * 64)
    changed_existing = list(existing)
    changed_existing[0] = conflict
    with pytest.raises(SafetyError, match="differs"):
        preview_import(data, tuple(changed_existing))


def test_offline_dry_run_makes_no_odoo_claim_and_checks_target_identity():
    data = generate_dataset()
    report = build_dry_run_report(data, safe_identity(), TARGET_UUID)

    assert report["mode"] == "offline-dry-run"
    assert report["connected_to_odoo"] is False
    assert report["database_mutations"] == 0
    assert report["target_identity"] == "offline_identity_document_matches"
    assert report["planned_stock_ledger_reconciled"] is True
    assert report["import_plan"]["target_snapshot_used"] is False
    assert "planned_entry_count" in report["import_plan"]
    assert report["forecast_provenance"]["historical_runs_available"] is False
    assert report["forecast_provenance"]["manager_reviews_created"] is False
    assert "not collected from a live Docker/Odoo target" in report["limitations"][-1]


def test_target_identity_requires_all_new_isolated_resources():
    validate_target_identity(safe_identity(), expected_uuid=TARGET_UUID)
    for changes in (
        {"database_name": "autostock_showroom_demo"},
        {"compose_project": "autostock-showroom-demo"},
        {"postgres_volume": "autostock_ai_showroom_postgres"},
        {"filestore_volume": "autostock_ai_showroom_filestore"},
        {"marker_uuid": "00000000-0000-0000-0000-000000000000"},
        {"postgres_system_identifier": ""},
        {"endpoint_host": "0.0.0.0"},
        {"endpoint_port": 8069},
        {"container_names": ("autostock-showroom-demo-db-1",)},
    ):
        with pytest.raises(SafetyError):
            validate_target_identity(safe_identity(**changes), expected_uuid=TARGET_UUID)


def test_target_identity_rejects_wrong_database_uuid_and_project_names():
    with pytest.raises(SafetyError, match="UUID"):
        validate_target_identity(
            safe_identity(database_uuid="f14b2fa8-a54a-46a6-917a-ef23259f8f70"),
            expected_uuid=TARGET_UUID,
        )
    with pytest.raises(SafetyError, match="Compose"):
        validate_target_identity(
            safe_identity(compose_project="autostock-unrelated"),
            expected_uuid=TARGET_UUID,
        )


def test_apply_requires_exact_uuid_and_signed_verified_matching_backup(tmp_path):
    signing_key = b"local-private-test-signing-key-32bytes"
    database_path = tmp_path / "target.dump"
    filestore_path = tmp_path / "target-filestore.tar"
    database_path.write_bytes(b"private database backup fixture")
    filestore_path.write_bytes(b"matching filestore backup fixture")
    manifest = {
        "database_name": "autostock_atlas_morocco_demo",
        "target_uuid": TARGET_UUID,
        "compose_project": "autostock-atlas-morocco",
        "postgres_system_identifier": safe_identity().postgres_system_identifier,
        "postgres_volume": "autostock_atlas_morocco_postgres",
        "filestore_volume": "autostock_atlas_morocco_filestore",
        "endpoint_host": "127.0.0.1",
        "endpoint_port": 8070,
        "database_path": str(database_path),
        "database_size_bytes": database_path.stat().st_size,
        "database_sha256": hashlib.sha256(database_path.read_bytes()).hexdigest(),
        "filestore_path": str(filestore_path),
        "filestore_size_bytes": filestore_path.stat().st_size,
        "filestore_sha256": hashlib.sha256(filestore_path.read_bytes()).hexdigest(),
        "verified_restore": True,
        "restore_target": "separate_disposable_project",
    }
    manifest["signature_hmac_sha256"] = backup_manifest_signature(manifest, signing_key)
    validate_backup_manifest(
        manifest,
        expected_uuid=TARGET_UUID,
        target_identity=safe_identity(),
        signing_key=signing_key,
    )
    wrong_identity = safe_identity(postgres_system_identifier="7654321098765432199")
    wrong_target_manifest = {**manifest, "postgres_system_identifier": "7654321098765432199"}
    wrong_target_manifest["signature_hmac_sha256"] = backup_manifest_signature(
        wrong_target_manifest, signing_key
    )
    with pytest.raises(SafetyError, match="verified target"):
        validate_backup_manifest(
            wrong_target_manifest,
            expected_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            signing_key=signing_key,
        )
    with pytest.raises(SafetyError, match="signature is invalid"):
        validate_backup_manifest(
            {**manifest, "signature_hmac_sha256": "0" * 64},
            expected_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            signing_key=signing_key,
        )
    with pytest.raises(SafetyError, match="verified target"):
        validate_backup_manifest(
            manifest,
            expected_uuid=TARGET_UUID,
            target_identity=wrong_identity,
            signing_key=signing_key,
        )
    filestore_path.write_bytes(b"changed backup")
    with pytest.raises(SafetyError, match="does not match"):
        validate_backup_manifest(
            manifest,
            expected_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            signing_key=signing_key,
        )
    filestore_path.write_bytes(b"matching filestore backup fixture")
    require_apply_approval(
        mode="dry-run",
        typed_target_uuid=None,
        expected_target_uuid=TARGET_UUID,
        backup_manifest=None,
    )
    with pytest.raises(SafetyError, match="typing"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=None,
            expected_target_uuid=TARGET_UUID,
            backup_manifest=manifest,
        )
    with pytest.raises(SafetyError, match="verified"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=TARGET_UUID,
            expected_target_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            backup_manifest={**manifest, "verified_restore": False},
            backup_signing_key=signing_key,
        )
    with pytest.raises(SafetyError, match="cross-checked target identity"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=TARGET_UUID,
            expected_target_uuid=TARGET_UUID,
            backup_manifest=manifest,
            backup_signing_key=signing_key,
        )
    with pytest.raises(SafetyError, match="Database name"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=TARGET_UUID,
            expected_target_uuid=TARGET_UUID,
            target_identity=safe_identity(database_name="wrong_database"),
            backup_manifest=manifest,
            backup_signing_key=signing_key,
        )
    require_apply_approval(
        mode="apply",
        typed_target_uuid=TARGET_UUID,
        expected_target_uuid=TARGET_UUID,
        target_identity=safe_identity(),
        backup_manifest=manifest,
        backup_signing_key=signing_key,
    )


def test_example_event_window_is_explicitly_pinned():
    data = generate_dataset()
    assert min(item.day for item in data.movements) == HISTORY_START
    assert max(item.day for item in data.movements) == END_DATE
    assert all(
        item.day <= END_DATE
        for item in data.movements
    )
    assert HISTORY_START < FOCUS_START < END_DATE


def test_morocco_effective_noon_uses_date_specific_timezone_offset():
    # Morocco's 2026 DST schedule changes during this fixture's window.
    assert _event_time_utc(date(2026, 4, 13)) == "2026-04-13T11:00:00"
    assert _event_time_utc(date(2026, 9, 19)) == "2026-09-19T11:00:00"
    assert _event_time_utc(date(2026, 9, 20)) == "2026-09-20T12:00:00"
