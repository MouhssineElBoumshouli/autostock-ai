"""Seed clearly labeled automotive inventory in a disposable local Odoo demo DB.

Run through `odoo shell`; AUTOSTOCK_QA_DEMO_ACTION defaults to `seed` and may
be set to `cleanup`. This script refuses to run outside the named local QA
databases and does not create sales, supplier, customer, or purchase records.
"""
import os

from odoo.exceptions import UserError


ALLOWED_DATABASES = {"autostock_phase2_demo", "autostock_phase2_qa"}
SAMPLES = [
    ("DEMO-QA-BP-001", "Front brake pads", 48, 12),
    ("DEMO-QA-OF-002", "Oil filter", 8, 18),
    ("DEMO-QA-SP-003", "Spark plug", 0, 6),
    ("DEMO-QA-BT-004", "12V battery", 15, 10),
    ("DEMO-QA-AF-005", "Cabin air filter", 4, 5),
]


if env.cr.dbname not in ALLOWED_DATABASES:
    raise UserError("Synthetic QA inventory is allowed only in the documented local demo database.")

action = os.environ.get("AUTOSTOCK_QA_DEMO_ACTION", "seed")
company = env.company
warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
if not warehouse or not warehouse.lot_stock_id:
    raise UserError("The active company needs a stock warehouse before the QA fixture can run.")

Template = env["product.template"].with_company(company)
Quant = env["stock.quant"].with_company(company).with_context(inventory_mode=True)
fixture_label = "[SYNTHETIC QA] "
results = []

for sku, part_name, on_hand, safety_stock in SAMPLES:
    template = Template.search(
        [("default_code", "=", sku), ("company_id", "=", company.id)], limit=1
    )

    if action == "seed":
        if template and not template.name.startswith(fixture_label):
            raise UserError(f"Refusing to overwrite non-QA product with SKU {sku}.")
        if not template:
            template = Template.create(
                {
                    "name": f"{fixture_label}{part_name}",
                    "default_code": sku,
                    "is_storable": True,
                    "autostock_enabled": True,
                    "autostock_safety_stock": safety_stock,
                    "company_id": company.id,
                }
            )
        else:
            template.write(
                {
                    "name": f"{fixture_label}{part_name}",
                    "is_storable": True,
                    "autostock_enabled": True,
                    "autostock_safety_stock": safety_stock,
                }
            )

        product = template.product_variant_id
        quant = Quant.search(
            [("product_id", "=", product.id), ("location_id", "=", warehouse.lot_stock_id.id)],
            limit=1,
        )
        if not quant:
            quant = Quant.create(
                {"product_id": product.id, "location_id": warehouse.lot_stock_id.id}
            )
        if quant.quantity != on_hand:
            quant.inventory_quantity = on_hand
            quant.action_apply_inventory()
        results.append((sku, template.name, product.qty_available, safety_stock))

    elif action == "cleanup":
        if not template:
            continue
        if not template.name.startswith(fixture_label):
            raise UserError(f"Refusing to change non-QA product with SKU {sku}.")
        product = template.product_variant_id
        quant = Quant.search(
            [("product_id", "=", product.id), ("location_id", "=", warehouse.lot_stock_id.id)],
            limit=1,
        )
        if quant and quant.quantity:
            quant.inventory_quantity = 0
            quant.action_apply_inventory()
        template.write({"autostock_enabled": False, "autostock_safety_stock": 0})
        results.append((sku, template.name, product.qty_available, 0))

    else:
        raise UserError("AUTOSTOCK_QA_DEMO_ACTION must be either seed or cleanup.")

env.flush_all()
env.cr.commit()
print(f"{action.upper()} complete for {company.display_name}; {len(results)} labeled synthetic automotive records.")
for result in results:
    print(" | ".join(str(value) for value in result))
