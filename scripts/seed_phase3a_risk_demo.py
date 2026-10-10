"""Seed labeled automotive stock-risk examples into the disposable QA database.

Run with ``odoo shell -d autostock_phase3a_qa --no-http < scripts/seed_phase3a_risk_demo.py``.
The database-name guard prevents this synthetic fixture from touching another DB.
"""
if env.cr.dbname != "autostock_phase3a_qa":
    raise RuntimeError("Synthetic Phase 3A records may only be seeded into autostock_phase3a_qa.")

company = env.company
company.write({"name": "[SYNTHETIC QA] Automotive Demo Company"})
warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
if not warehouse:
    raise RuntimeError("The QA company needs an Odoo stock warehouse before seeding.")

unit = env.ref("uom.product_uom_unit")
dozen = env.ref("uom.product_uom_dozen")
vendor_name = "[SYNTHETIC QA] Atlas Parts Supply"
vendor = env["res.partner"].search([("name", "=", vendor_name)], limit=1)
if not vendor:
    vendor = env["res.partner"].create(
        {"name": vendor_name, "company_type": "company", "supplier_rank": 1}
    )

samples = [
    {
        "sku": "QA3A-OF-001",
        "name": "[SYNTHETIC QA] Oil Filter · Corolla 1.8L",
        "reference": "SQA-TOY-OF-001",
        "on_hand": 3,
        "minimum": 5,
        "target": 18,
        "lead_days": 10,
        "moq": 1,
        "vendor_uom": dozen,
        "pack_uom": dozen,
        "price_tier": 3,
    },
    {
        "sku": "QA3A-BP-002",
        "name": "[SYNTHETIC QA] Front Brake Pad Set · Corolla",
        "reference": "SQA-TOY-BP-002",
        "on_hand": 0,
        "minimum": 4,
        "target": 12,
        "lead_days": 14,
        "moq": 2,
        "vendor_uom": unit,
        "pack_uom": unit,
        "price_tier": 10,
    },
    {
        "sku": "QA3A-SP-003",
        "name": "[SYNTHETIC QA] Spark Plug Set · Civic 2.0L",
        "reference": "SQA-HON-SP-003",
        "on_hand": 5,
        "minimum": 5,
        "target": 12,
        "lead_days": 7,
        "moq": 1,
        "vendor_uom": dozen,
        "pack_uom": unit,
        "price_tier": 3,
    },
    {
        "sku": "QA3A-AL-004",
        "name": "[SYNTHETIC QA] Alternator · Duster 1.5 dCi",
        "reference": "SQA-DAC-AL-004",
        "on_hand": 32,
        "minimum": 6,
        "target": 18,
        "lead_days": 21,
        "moq": 1,
        "vendor_uom": unit,
        "pack_uom": unit,
        "price_tier": 3,
    },
    {
        "sku": "QA3A-CF-005",
        "name": "[SYNTHETIC QA] Cabin Air Filter · Tiguan",
        "reference": "SQA-VW-CF-005",
        "on_hand": 5,
        "minimum": None,
        "target": None,
        "lead_days": 7,
        "moq": None,
        "vendor_uom": unit,
        "pack_uom": None,
        "price_tier": None,
    },
]

Template = env["product.template"].with_company(company)
Quant = env["stock.quant"].with_company(company)
SupplierInfo = env["product.supplierinfo"].with_company(company)
Orderpoint = env["stock.warehouse.orderpoint"].with_company(company)
location = warehouse.lot_stock_id

for sample in samples:
    template = Template.search(
        [
            ("default_code", "=", sample["sku"]),
            ("company_id", "=", company.id),
        ],
        limit=1,
    )
    values = {
        "name": sample["name"],
        "default_code": sample["sku"],
        "company_id": company.id,
        "is_storable": True,
        "uom_id": unit.id,
        "autostock_enabled": True,
        "autostock_oem_reference": sample["reference"],
        "autostock_priority": "critical" if sample["sku"] == "QA3A-BP-002" else "standard",
        "autostock_safety_stock": 0,
        "autostock_lead_time_days": sample["lead_days"],
    }
    if template:
        template.write(values)
    else:
        template = Template.create(values)
    product = template.product_variant_id

    quants = Quant.search([("product_id", "=", product.id), ("location_id", "=", location.id)])
    current_qty = sum(quants.mapped("quantity"))
    difference = sample["on_hand"] - current_qty
    if difference:
        Quant._update_available_quantity(product, location, difference)

    rules = Orderpoint.search(
        [
            ("product_id", "=", product.id),
            ("warehouse_id", "=", warehouse.id),
            ("location_id", "=", location.id),
            ("company_id", "=", company.id),
        ],
        limit=1,
    )
    if sample["minimum"] is not None:
        rule_values = {
            "product_id": product.id,
            "warehouse_id": warehouse.id,
            "location_id": location.id,
            "company_id": company.id,
            "product_min_qty": sample["minimum"],
            "product_max_qty": sample["target"],
            "replenishment_uom_id": sample["pack_uom"].id,
        }
        if rules:
            rules.write(rule_values)
        else:
            Orderpoint.create(rule_values)
    elif rules:
        rules.unlink()

    supplier_lines = SupplierInfo.search(
        [
            ("product_tmpl_id", "=", template.id),
            ("partner_id", "=", vendor.id),
            ("company_id", "=", company.id),
        ],
        limit=1,
    )
    if sample["moq"] is None:
        if supplier_lines:
            supplier_lines.unlink()
        continue
    supplier_values = {
        "partner_id": vendor.id,
        "product_tmpl_id": template.id,
        "company_id": company.id,
        "product_uom_id": sample["vendor_uom"].id,
        "delay": sample["lead_days"],
        "min_qty": sample["price_tier"],
        "autostock_min_order_qty": sample["moq"],
        "price": 125.0,
    }
    if supplier_lines:
        supplier_lines.write(supplier_values)
    else:
        SupplierInfo.create(supplier_values)

env.cr.commit()
print("Seeded 5 labeled synthetic automotive parts, stock rules, and vendor terms.")
