from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
from pathlib import Path
import pytest

from scripts.moroccan_showroom.generator import (
    DATASET_VERSION,
    END_DATE,
    FOCUS_START,
    HISTORY_START,
    FORECAST_PROFILE_COUNT,
    MISSING_SUPPLIER_SKU,
    WAREHOUSE_HISTORY_PROFILE_SKUS,
    _event_time_utc,
    canonical_json,
    generate_dataset,
)
from scripts.moroccan_showroom.restore_contract import sign_restore_evidence
from scripts.moroccan_showroom.safety import (
    SafetyError,
    TargetIdentity,
    backup_manifest_signature,
    require_apply_approval,
    validate_backup_manifest_integrity,
    validate_target_identity,
)
from scripts.moroccan_showroom.compose_contract import (
    ADDONS_TARGET,
    DATABASE_TARGET,
    FILESTORE_TARGET,
    NETWORK_KEY,
    SCRIPTS_TARGET,
    TARGET_NETWORK,
    WEB_HEALTHCHECK_TEST,
    WEB_REQUIRED_ENVIRONMENT_KEYS,
    WEB_START_COMMAND,
    validate_compose_config,
    validate_container_inspect,
    validate_network_inspect,
)
from scripts.moroccan_showroom.import_plan import FixtureRecord, preview_import
from scripts.moroccan_showroom.cli import build_dry_run_report


TARGET_UUID = "0f7d8360-4aa6-48dc-9337-6438f704db12"


def compose_config(repo_root: Path):
    return {
        "name": "autostock-atlas-morocco",
        "services": {
            "db": {
                "image": "postgres:16",
                "volumes": [
                    {"type": "volume", "source": "morocco_postgres", "target": DATABASE_TARGET, "read_only": False}
                ],
                "networks": {NETWORK_KEY: None},
                "ports": [],
            },
            "web": {
                "image": "autostock-ai-odoo-morocco:19.0",
                "volumes": [
                    {"type": "volume", "source": "morocco_filestore", "target": FILESTORE_TARGET, "read_only": False},
                    {"type": "bind", "source": str(repo_root / "addons"), "target": ADDONS_TARGET, "read_only": True},
                    {"type": "bind", "source": str(repo_root / "scripts" / "moroccan_showroom"), "target": SCRIPTS_TARGET, "read_only": True},
                ],
                "networks": {NETWORK_KEY: None},
                "ports": [{"host_ip": "127.0.0.1", "published": "8070", "target": 8069}],
                "command": list(WEB_START_COMMAND),
                "healthcheck_test": list(WEB_HEALTHCHECK_TEST),
                "environment_keys": sorted(WEB_REQUIRED_ENVIRONMENT_KEYS),
            },
        },
        "volumes": {
            "morocco_postgres": {"name": "autostock_atlas_morocco_postgres"},
            "morocco_filestore": {"name": "autostock_atlas_morocco_filestore"},
        },
        "networks": {
            NETWORK_KEY: {
                "name": TARGET_NETWORK,
                "labels": {"com.autostock.target-uuid": TARGET_UUID},
            }
        },
    }


def container_inspect(repo_root: Path, service: str = "web"):
    if service == "db":
        mounts = [{
            "Type": "volume",
            "Name": "autostock_atlas_morocco_postgres",
            "Source": "/var/lib/docker/volumes/autostock_atlas_morocco_postgres/_data",
            "Destination": DATABASE_TARGET,
            "RW": True,
        }]
    else:
        mounts = [
            {"Type": "volume", "Name": "autostock_atlas_morocco_filestore", "Source": "/var/lib/docker/volumes/autostock_atlas_morocco_filestore/_data", "Destination": FILESTORE_TARGET, "RW": True},
            {"Type": "bind", "Name": "", "Source": str(repo_root / "addons"), "Destination": ADDONS_TARGET, "RW": False},
            {"Type": "bind", "Name": "", "Source": str(repo_root / "scripts" / "moroccan_showroom"), "Destination": SCRIPTS_TARGET, "RW": False},
        ]
    return {
        "name": f"/autostock-atlas-morocco-{service}-1",
        "image": "postgres:16" if service == "db" else "autostock-ai-odoo-morocco:19.0",
        "labels": {
            "com.docker.compose.project": "autostock-atlas-morocco",
            "com.docker.compose.service": service,
            "com.autostock.target-uuid": TARGET_UUID,
        },
        "mounts": mounts,
        "networks": [TARGET_NETWORK],
    }


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


def valid_restore_evidence(manifest, signing_key):
    project = "autostock-restore-proof-local-test"
    attachment_hash = "a" * 64
    tree_hash = "b" * 64
    evidence = {
        "restore_project": project,
        "published_ports": [],
        "restore_postgres_volume": f"{project}-postgres",
        "restore_filestore_volume": f"{project}-filestore",
        "restore_database": "autostock_atlas_morocco_demo",
        "backup_database_sha256": manifest["database_sha256"],
        "backup_filestore_sha256": manifest["filestore_sha256"],
        "pg_restore_succeeded": True,
        "module_state": "installed",
        "marker_uuid": TARGET_UUID,
        "fixture_table_exists": True,
        "source_attachment_sha256": attachment_hash,
        "restored_attachment_sha256": attachment_hash,
        "source_filestore_tree_sha256": tree_hash,
        "restored_filestore_tree_sha256": tree_hash,
        "source_attachment_count": 1,
        "restored_attachment_count": 1,
        "proof_attachment_present": True,
        "cleanup_scope": project,
        "restore_resources_removed": True,
    }
    return sign_restore_evidence(
        evidence,
        backup_manifest=manifest,
        backup_signing_key=signing_key,
    )


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
        "products_without_supplier_terms": 1,
        "reordering_rules": 298,
        "suppliers": 8,
        "customers": 18,
        "focus_completed_orders": 350,
        "focus_completed_delivery_lines": 1050,
        "receipt_pickings": 30,
        "linked_customer_returns": 12,
        "internal_transfer_journeys": 18,
        "open_customer_orders": 20,
        "history_profiles": 30,
        "companywide_history_profiles": 24,
        "warehouse_history_profiles": 6,
        "history_daily_observation_rows": 5430,
        "history_calendar_days_per_profile": 181,
    }
    assert {key: first.counts[key] for key in expected_counts} == expected_counts
    assert first.version == DATASET_VERSION == "atlas-ma-2026.4"
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
    profiled = [product for product in data.products if product.history_profile_key]
    assert len(profiled) == FORECAST_PROFILE_COUNT
    assert Counter(product.category for product in profiled) == {
        "filtration_engine_service": 4,
        "braking": 4,
        "suspension_steering": 4,
        "electrical_batteries": 4,
        "cooling_belts_drivetrain": 4,
        "ignition_sensors_fluids": 4,
    }
    assert all(product.history_profile_key is None for product in data.products if product not in profiled)


def test_reserved_slow_product_has_no_vendor_terms_history_or_order_recommendation_inputs():
    data = generate_dataset()
    product = next(item for item in data.products if item.sku == MISSING_SUPPLIER_SKU)
    events = [item for item in data.movements if item.sku == MISSING_SUPPLIER_SKU]

    assert product.name == "Fuel Filter Element (Series 3)"
    assert product.demand_class == "slow"
    assert product.supplier_terms == ()
    assert product.history_profile_key is None
    assert product.reorder_minimum is None
    assert product.reorder_maximum is None
    assert not any(order.sku == MISSING_SUPPLIER_SKU for order in data.open_orders)
    assert not any(
        line.sku == MISSING_SUPPLIER_SKU
        for order in data.orders
        for line in order.lines
    )
    assert all(item.kind == "opening_adjustment" for item in events)
    assert not any(item.kind == "vendor_receipt" for item in events)
    balances = {
        row["warehouse_key"]: row["on_hand"]
        for row in data.ending_on_hand
        if row["sku"] == MISSING_SUPPLIER_SKU
    }
    assert balances == {"warehouse_atlas_central": 8, "warehouse_south_depot": 5}


def test_history_coverage_is_contiguous_and_scoped_to_profiles():
    data = generate_dataset()
    rows_by_profile = defaultdict(list)
    for row in data.daily_observations:
        rows_by_profile[row["profile_key"]].append(row)

    assert len(rows_by_profile) == len(data.history_profiles) == 30
    expected_days = (END_DATE - HISTORY_START).days + 1
    for rows in rows_by_profile.values():
        rows.sort(key=lambda row: row["day"])
        assert len(rows) == expected_days == 181
        assert rows[0]["day"] == HISTORY_START
        assert rows[-1]["day"] == END_DATE
        assert all(row["coverage_complete"] for row in rows)
        assert all(row["delivered_units"] >= 0 for row in rows)
        assert all(row["returned_units"] >= 0 for row in rows)
    assert all(row["day"] <= END_DATE for row in data.daily_observations)
    company_profiles = [profile for profile in data.history_profiles if not profile["warehouse_key"]]
    warehouse_profiles = [profile for profile in data.history_profiles if profile["warehouse_key"]]
    assert len(company_profiles) == FORECAST_PROFILE_COUNT == 24
    assert len(warehouse_profiles) == 6
    assert Counter(profile["category"] for profile in company_profiles) == {
        "filtration_engine_service": 4,
        "braking": 4,
        "suspension_steering": 4,
        "electrical_batteries": 4,
        "cooling_belts_drivetrain": 4,
        "ignition_sensors_fluids": 4,
    }
    assert Counter(profile["demand_class"] for profile in company_profiles) == {
        "fast": 6,
        "steady": 6,
        "intermittent": 6,
        "slow": 6,
    }
    assert all(profile["planned_delivery_move_count"] > 0 for profile in data.history_profiles)
    assert all(profile["planned_nonzero_delivery_days"] >= 7 for profile in data.history_profiles)
    assert all(
        profile["status"] == "fixture_plan_only_not_verified_in_odoo"
        and profile["calendar_days"] == 181
        and len(profile["planned_daily_rows_sha256"]) == 64
        for profile in data.history_profiles
    )
    assert all(
        any(
            movement.kind == "sale_delivery"
            and movement.sku == profile["sku"]
            and movement.day < FOCUS_START
            and (
                profile["warehouse_key"] is None
                or (
                    movement.source == profile["warehouse_key"]
                    and profile["warehouse_key"] == "warehouse_south_depot"
                )
                or (
                    movement.source == profile["warehouse_key"]
                    and profile["warehouse_key"] == "warehouse_atlas_central"
                )
            )
            for movement in data.movements
        )
        for profile in data.history_profiles
    )

    for warehouse_key, skus in WAREHOUSE_HISTORY_PROFILE_SKUS.items():
        scoped = [profile for profile in warehouse_profiles if profile["warehouse_key"] == warehouse_key]
        assert {profile["sku"] for profile in scoped} == set(skus)
        assert all(profile["planned_delivery_move_count"] > 0 for profile in scoped)
        assert all(
            row["warehouse_key"] == warehouse_key
            for profile in scoped
            for row in rows_by_profile[profile["key"]]
        )
        assert Counter(profile["category"] for profile in scoped) == {
            "filtration_engine_service": 1,
            "braking": 1,
            "suspension_steering": 1,
        }
    for sku in WAREHOUSE_HISTORY_PROFILE_SKUS["warehouse_atlas_central"]:
        atc = next(profile for profile in warehouse_profiles if profile["sku"] == sku and profile["warehouse_key"] == "warehouse_atlas_central")
        asd = next(profile for profile in warehouse_profiles if profile["sku"] == sku and profile["warehouse_key"] == "warehouse_south_depot")
        company = next(profile for profile in company_profiles if profile["sku"] == sku)
        atc_rows = rows_by_profile[atc["key"]]
        asd_rows = rows_by_profile[asd["key"]]
        company_rows = rows_by_profile[company["key"]]
        assert atc_rows != asd_rows
        assert company_rows != atc_rows
        assert company_rows != asd_rows
    for warehouse_key in WAREHOUSE_HISTORY_PROFILE_SKUS:
        return_profile = next(
            profile for profile in warehouse_profiles
            if profile["warehouse_key"] == warehouse_key and profile["sku"] == "AT-MA-FLT-101"
        )
        assert return_profile["planned_return_move_count"] >= 1


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


def test_backup_manifest_integrity_is_separate_from_restore_verification(tmp_path):
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
    }
    manifest["signature_hmac_sha256"] = backup_manifest_signature(manifest, signing_key)
    validate_backup_manifest_integrity(
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
        validate_backup_manifest_integrity(
            wrong_target_manifest,
            expected_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            signing_key=signing_key,
        )
    with pytest.raises(SafetyError, match="signature is invalid"):
        validate_backup_manifest_integrity(
            {**manifest, "signature_hmac_sha256": "0" * 64},
            expected_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            signing_key=signing_key,
        )
    with pytest.raises(SafetyError, match="verified target"):
        validate_backup_manifest_integrity(
            manifest,
            expected_uuid=TARGET_UUID,
            target_identity=wrong_identity,
            signing_key=signing_key,
        )
    filestore_path.write_bytes(b"changed backup")
    with pytest.raises(SafetyError, match="does not match"):
        validate_backup_manifest_integrity(
            manifest,
            expected_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            signing_key=signing_key,
        )
    filestore_path.write_bytes(b"matching filestore backup fixture")
    restore_evidence = valid_restore_evidence(manifest, signing_key)
    require_apply_approval(mode="dry-run")
    with pytest.raises(SafetyError, match="Unsupported execution mode"):
        require_apply_approval(mode="aply")
    with pytest.raises(SafetyError, match="typing the exact prepared target UUID"):
        require_apply_approval(
            mode="apply",
            expected_target_uuid=TARGET_UUID,
            backup_manifest=manifest,
            backup_signing_key=signing_key,
            restore_evidence=restore_evidence,
        )
    with pytest.raises(SafetyError, match="cross-checked target identity"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=TARGET_UUID,
            expected_target_uuid=TARGET_UUID,
            backup_manifest=manifest,
            backup_signing_key=signing_key,
            restore_evidence=restore_evidence,
        )
    with pytest.raises(SafetyError, match="independent restore evidence"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=TARGET_UUID,
            expected_target_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            backup_manifest=manifest,
            backup_signing_key=signing_key,
        )

    tampered_restore = {**restore_evidence, "marker_uuid": "00000000-0000-0000-0000-000000000000"}
    with pytest.raises(SafetyError, match="Restore evidence signature is invalid"):
        require_apply_approval(
            mode="apply",
            typed_target_uuid=TARGET_UUID,
            expected_target_uuid=TARGET_UUID,
            target_identity=safe_identity(),
            backup_manifest=manifest,
            backup_signing_key=signing_key,
            restore_evidence=tampered_restore,
        )

    mounted_database = tmp_path / "mounted-database.dump"
    mounted_filestore = tmp_path / "mounted-filestore.tar"
    mounted_database.write_bytes(database_path.read_bytes())
    mounted_filestore.write_bytes(filestore_path.read_bytes())
    database_path.unlink()
    filestore_path.unlink()
    require_apply_approval(
        mode="apply",
        typed_target_uuid=TARGET_UUID,
        expected_target_uuid=TARGET_UUID,
        target_identity=safe_identity(),
        backup_manifest=manifest,
        backup_signing_key=signing_key,
        backup_artifact_paths={
            "database": mounted_database,
            "filestore": mounted_filestore,
        },
        restore_evidence=restore_evidence,
    )


def test_mocked_first_start_repeat_start_and_status_preflights_are_repeatable(tmp_path):
    config = compose_config(tmp_path)
    db = container_inspect(tmp_path, service="db")
    web = container_inspect(tmp_path)
    network = {
        "name": TARGET_NETWORK,
        "labels": {
            "com.docker.compose.project": "autostock-atlas-morocco",
            "com.autostock.target-uuid": TARGET_UUID,
        },
        "container_ids": ["db-id", "web-id"],
    }
    target_ids = {"db-id", "web-id"}
    transitions = (
        "first-start-before-up",
        "first-start-after-up",
        "repeat-start-before-up",
        "repeat-start-after-up",
        "status",
    )
    for transition in transitions:
        validate_compose_config(config, repo_root=tmp_path, expected_uuid=TARGET_UUID)
        if transition != "first-start-before-up":
            validate_container_inspect(db, repo_root=tmp_path, expected_uuid=TARGET_UUID)
            validate_container_inspect(web, repo_root=tmp_path, expected_uuid=TARGET_UUID)
            validate_network_inspect(
                network,
                target_container_ids=target_ids,
                expected_uuid=TARGET_UUID,
            )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda config: config["services"]["db"]["volumes"][0].update(source="autostock_ai_showroom_postgres"),
        lambda config: config["services"]["db"]["volumes"][0].update(target="/wrong/postgres"),
        lambda config: config["services"]["web"]["volumes"][0].update(source="morocco_postgres"),
        lambda config: config["services"]["web"]["volumes"][0].update(target="/wrong/filestore"),
        lambda config: config["services"]["web"]["volumes"].append({"type": "bind", "source": ".showroom", "target": "/leak", "read_only": False}),
        lambda config: config["services"]["web"]["volumes"][1].update(read_only=False),
        lambda config: config["services"]["web"].update(networks={NETWORK_KEY: None, "default": None}),
        lambda config: config["services"]["web"].update(image="autostock-ai-odoo:19.0"),
        lambda config: config["services"]["web"].update(command=["--admin-passwd=bad"]),
        lambda config: config["services"]["web"].update(healthcheck_test=[]),
        lambda config: config["services"]["web"].update(
            environment_keys=[
                key for key in config["services"]["web"]["environment_keys"]
                if key != "ODOO_MASTER_PASSWORD"
            ]
        ),
        lambda config: config["networks"][NETWORK_KEY]["labels"].pop("com.autostock.target-uuid"),
    ],
)
def test_compose_rejects_tampered_mounts_services_and_network_identity(tmp_path, mutate):
    config = deepcopy(compose_config(tmp_path))
    mutate(config)
    with pytest.raises(SafetyError):
        validate_compose_config(config, repo_root=tmp_path, expected_uuid=TARGET_UUID)


def test_live_container_mounts_and_network_must_match_compose_contract(tmp_path):
    expected = container_inspect(tmp_path)
    validate_container_inspect(expected, repo_root=tmp_path, expected_uuid=TARGET_UUID)

    for changes in (
        {"mount_index": 0, "mount_changes": {"Name": "autostock_ai_showroom_filestore"}},
        {"mount_index": 1, "mount_changes": {"Source": str(tmp_path / ".showroom")}},
        {"mount_index": 1, "mount_changes": {"RW": True}},
        {"mount_index": 2, "mount_changes": {"Destination": "/unexpected"}},
    ):
        tampered = deepcopy(expected)
        tampered["mounts"][changes["mount_index"]].update(changes["mount_changes"])
        with pytest.raises(SafetyError):
            validate_container_inspect(tampered, repo_root=tmp_path, expected_uuid=TARGET_UUID)

    wrong_network = deepcopy(expected)
    wrong_network["networks"] = [TARGET_NETWORK, "legacy-network"]
    with pytest.raises(SafetyError):
        validate_container_inspect(wrong_network, repo_root=tmp_path, expected_uuid=TARGET_UUID)

    wrong_image = deepcopy(expected)
    wrong_image["image"] = "autostock-ai-odoo:19.0"
    with pytest.raises(SafetyError, match="image"):
        validate_container_inspect(wrong_image, repo_root=tmp_path, expected_uuid=TARGET_UUID)

    validate_container_inspect(
        wrong_image,
        repo_root=tmp_path,
        expected_uuid=TARGET_UUID,
        allow_shared_web_image=True,
    )

    unrelated_image = deepcopy(expected)
    unrelated_image["image"] = "autostock-unrelated:19.0"
    with pytest.raises(SafetyError, match="image"):
        validate_container_inspect(
            unrelated_image,
            repo_root=tmp_path,
            expected_uuid=TARGET_UUID,
            allow_shared_web_image=True,
        )


def test_live_database_mount_cannot_use_another_volume_or_target(tmp_path):
    expected = container_inspect(tmp_path, service="db")
    validate_container_inspect(expected, repo_root=tmp_path, expected_uuid=TARGET_UUID)
    for changes in (
        {"Name": "autostock_ai_showroom_postgres"},
        {"Destination": "/var/lib/postgresql"},
        {"RW": False},
    ):
        tampered = deepcopy(expected)
        tampered["mounts"][0].update(changes)
        with pytest.raises(SafetyError):
            validate_container_inspect(tampered, repo_root=tmp_path, expected_uuid=TARGET_UUID)

    wrong_image = deepcopy(expected)
    wrong_image["image"] = "postgres:15"
    with pytest.raises(SafetyError, match="image"):
        validate_container_inspect(wrong_image, repo_root=tmp_path, expected_uuid=TARGET_UUID)


@pytest.mark.parametrize(
    "docker_prefix",
    [
        "/run/desktop/mnt/host/c",
        "/host_mnt/c",
    ],
)
def test_live_windows_docker_desktop_bind_aliases_match_exact_repo_path(docker_prefix):
    repo_root = Path(r"C:\Users\Mouhssine\Documents\autostock ai\autostock-ai")
    expected = container_inspect(repo_root)
    expected["mounts"][1]["Source"] = (
        f"{docker_prefix}/Users/Mouhssine/Documents/autostock ai/autostock-ai/addons"
    )
    expected["mounts"][2]["Source"] = (
        f"{docker_prefix}/Users/Mouhssine/Documents/autostock ai/autostock-ai/"
        "scripts/moroccan_showroom"
    )

    validate_container_inspect(expected, repo_root=repo_root, expected_uuid=TARGET_UUID)

    wrong = deepcopy(expected)
    wrong["mounts"][1]["Source"] = (
        f"{docker_prefix}/Users/Mouhssine/Documents/another-repo/addons"
    )
    with pytest.raises(SafetyError, match="Live web mounts differ"):
        validate_container_inspect(wrong, repo_root=repo_root, expected_uuid=TARGET_UUID)


def test_existing_network_rejects_foreign_endpoints_and_uuid(tmp_path):
    evidence = {
        "name": TARGET_NETWORK,
        "labels": {
            "com.docker.compose.project": "autostock-atlas-morocco",
            "com.autostock.target-uuid": TARGET_UUID,
        },
        "container_ids": ["db-id", "web-id"],
    }
    validate_network_inspect(
        evidence,
        target_container_ids={"db-id", "web-id"},
        expected_uuid=TARGET_UUID,
    )
    with pytest.raises(SafetyError, match="outside its own Compose project"):
        validate_network_inspect(
            {**evidence, "container_ids": ["legacy-container-id"]},
            target_container_ids={"db-id", "web-id"},
            expected_uuid=TARGET_UUID,
        )
    with pytest.raises(SafetyError, match="UUID"):
        validate_network_inspect(
            {**evidence, "labels": {**evidence["labels"], "com.autostock.target-uuid": "wrong"}},
            target_container_ids={"db-id", "web-id"},
            expected_uuid=TARGET_UUID,
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



def test_post_apply_restore_contract_is_separate_and_dataset_guarded():
    repo_root = Path(__file__).resolve().parents[1]
    local_target = (repo_root / "scripts" / "moroccan_showroom" / "local_target.ps1").read_text(encoding="utf-8")

    assert '"PostApplyRestore"' in local_target
    assert '"PostApplyRestore" { Backup-And-Restore $true }' in local_target
    assert '"DiagnosePostApply" { Diagnose-PostApply }' in local_target
    assert 'Invoke-OdooMountedScript "odoo_diagnose.py"' in local_target
    assert '"BackupRestore" { Backup-And-Restore $false }' in local_target
    assert 'Invoke-Prepare "RuntimeStatus"' in local_target
    assert 'Do not rebuild or recreate it before' in local_target
    assert '$datasetVersion = "atlas-ma-2026.4"' in local_target
    assert '$expectedForecastRequests = 90' in local_target
    assert 'Invoke-OdooMountedScript "odoo_verify.py"' in local_target
    assert "fixture_registry_sha256" in local_target
    assert "Restored fixture registry digest differs from source." in local_target
    assert 'backup_stage = if ($PostApply) { "post-import" } else { "pre-import" }' in local_target
    assert "No application connection was changed. Legacy USD Atlas remains separate." in local_target


def test_post_apply_diagnostic_does_not_require_purchase_module():
    repo_root = Path(__file__).resolve().parents[1]
    diagnostic = (repo_root / "scripts" / "moroccan_showroom" / "odoo_diagnose.py").read_text(encoding="utf-8")

    assert '"purchase.order" in env.registry.models' in diagnostic
    assert '"purchase.order.line" in env.registry.models' in diagnostic
    assert 'purchase_model_available' in diagnostic
    assert 'purchase_orders = []' in diagnostic


def test_guarded_apply_container_names_avoid_json_native_argument_quoting():
    repo_root = Path(__file__).resolve().parents[1]
    local_target = (repo_root / "scripts" / "moroccan_showroom" / "local_target.ps1").read_text(encoding="utf-8")
    apply_runner = (repo_root / "scripts" / "moroccan_showroom" / "odoo_apply.py").read_text(encoding="utf-8")

    assert "AUTOSTOCK_MOROCCO_CONTAINER_NAMES_JSON" not in local_target
    assert "AUTOSTOCK_MOROCCO_CONTAINER_NAMES_JSON" not in apply_runner
    for variable in (
        "AUTOSTOCK_MOROCCO_DB_CONTAINER_NAME",
        "AUTOSTOCK_MOROCCO_WEB_CONTAINER_NAME",
    ):
        assert variable in local_target
        assert variable in apply_runner
