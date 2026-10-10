"""Populate the isolated Atlas Auto Distribution Odoo showroom.

Run only inside Odoo shell for the exact local database
``autostock_showroom_demo``. Every value in this fixture is fictional. Sale
orders and deliveries are created and validated through Odoo; forecasting and
reorder guidance are then produced by the installed AutoStock code.
"""

from __future__ import annotations

import base64
import io
import math
import os
import random
from datetime import datetime, time, timedelta

from PIL import Image, ImageDraw, ImageFont
from odoo import Command, fields


SHOWROOM_DATABASE = "autostock_showroom_demo"
SEED_VERSION = "2026-10-10.1"
HISTORY_DAYS = 180

# Guard before looking up or changing any business record. This script is not a
# general purpose fixture loader; it can write only to this disposable database.
if env.cr.dbname != SHOWROOM_DATABASE:  # noqa: F821 - env is injected by odoo shell
    raise RuntimeError(
        "Refusing to seed any database except autostock_showroom_demo. "
        f"The connected database is {env.cr.dbname}."  # noqa: F821
    )

parameters = env["ir.config_parameter"]  # noqa: F821
if parameters.get_param("autostock_showroom.seed_version") == SEED_VERSION:
    print("Atlas Auto Distribution showroom is already populated; no records were changed.")
else:
    from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE, SUPPORTED_HORIZONS

    today = fields.Date.context_today(env.user)
    history_start = today - timedelta(days=HISTORY_DAYS)
    history_end = today - timedelta(days=1)
    unit = env.ref("uom.product_uom_unit")
    dozen = env.ref("uom.product_uom_dozen")
    company = env.company
    company.write(
        {
            "name": "Atlas Auto Distribution",
            "autostock_demo_environment": True,
            "autostock_history_complete_from": history_start,
        }
    )
    company.partner_id.write(
        {
            "name": "Atlas Auto Distribution",
            "city": "Marrakech",
        }
    )
    morocco = env["res.country"].search([("code", "=", "MA")], limit=1)
    if morocco:
        company.partner_id.country_id = morocco
    mad = env["res.currency"].search([("name", "=", "MAD")], limit=1)
    if mad:
        company.currency_id = mad

    # A locally generated brand mark. It contains no third-party customer logo.
    logo_image = Image.new("RGB", (760, 190), "#ffffff")
    draw = ImageDraw.Draw(logo_image)
    draw.rounded_rectangle((4, 4, 186, 186), radius=38, fill="#7048e8")
    draw.ellipse((48, 47, 143, 142), outline="#ffffff", width=9)
    draw.ellipse((75, 74, 116, 115), fill="#ffffff")
    draw.line((96, 37, 96, 152), fill="#d9cdff", width=5)
    draw.line((38, 94, 153, 94), fill="#d9cdff", width=5)
    try:
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
        font_regular = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        font_bold = ImageFont.load_default()
        font_regular = font_bold
    draw.text((222, 34), "ATLAS AUTO", fill="#1b2340", font=font_bold)
    draw.text((225, 101), "DISTRIBUTION", fill="#7d8394", font=font_regular)
    logo_buffer = io.BytesIO()
    logo_image.save(logo_buffer, format="PNG", optimize=True)
    company.logo = base64.b64encode(logo_buffer.getvalue())

    warehouses_model = env["stock.warehouse"].with_company(company)
    central = warehouses_model.search([("company_id", "=", company.id)], limit=1)
    if central:
        central.write({"name": "Atlas Central Warehouse", "code": "ATC"})
    else:
        central = warehouses_model.create(
            {"name": "Atlas Central Warehouse", "code": "ATC", "company_id": company.id}
        )
    south = warehouses_model.search(
        [("company_id", "=", company.id), ("id", "!=", central.id)], limit=1
    )
    if south:
        south.write({"name": "South Service Depot", "code": "ASD"})
    else:
        south = warehouses_model.create(
            {"name": "South Service Depot", "code": "ASD", "company_id": company.id}
        )
    central.write({"autostock_history_complete_from": history_start})
    south.write({"autostock_history_complete_from": history_start})

    supplier_names = [
        "Atlas Parts Supply",
        "North Star Components",
        "Meridian Automotive Wholesale",
        "Pioneer Motion Parts",
    ]
    suppliers = []
    for name in supplier_names:
        partner = env["res.partner"].search(
            [("name", "=", name), ("supplier_rank", ">", 0)], limit=1
        )
        if not partner:
            partner = env["res.partner"].create(
                {"name": name, "company_type": "company", "supplier_rank": 1}
            )
        suppliers.append(partner)

    customers = []
    for name in ("Northside Auto Service", "Riverside Garage", "Atlas Fleet Care"):
        partner = env["res.partner"].search(
            [("name", "=", name), ("customer_rank", ">", 0)], limit=1
        )
        if not partner:
            partner = env["res.partner"].create(
                {"name": name, "company_type": "company", "customer_rank": 1}
            )
        customers.append(partner)

    category_names = [
        "Engine & Service",
        "Braking",
        "Electrical",
        "Suspension & Steering",
        "Cooling",
        "Drivetrain",
    ]
    categories = {}
    for name in category_names:
        category = env["product.category"].search([("name", "=", name)], limit=1)
        if not category:
            category = env["product.category"].create({"name": name})
        categories[name] = category

    focus_parts = [
        {
            "sku": "AT-FLT-001",
            "name": "Engine Oil Filter",
            "category": "Engine & Service",
            "daily_rate": 1.8,
            "on_hand": 4,
            "minimum": 12,
            "target": 48,
            "lead_days": 12,
            "supplier_index": 0,
            "moq": 1,
            "order_uom": dozen,
            "price": 139.0,
        },
        {
            "sku": "AT-BRK-001",
            "name": "Front Brake Pad Set",
            "category": "Braking",
            "daily_rate": 0.85,
            "on_hand": 0,
            "minimum": 6,
            "target": 30,
            "lead_days": 15,
            "supplier_index": 1,
            "moq": 4,
            "order_uom": unit,
            "price": 420.0,
        },
        {
            "sku": "AT-FLT-002",
            "name": "Engine Air Filter Element",
            "category": "Engine & Service",
            "daily_rate": 0.72,
            "on_hand": 10,
            "minimum": 12,
            "target": 42,
            "lead_days": 10,
            "supplier_index": 2,
            "moq": 1,
            "order_uom": dozen,
            "price": 189.0,
        },
        {
            "sku": "AT-ENG-001",
            "name": "Iridium Spark Plug",
            "category": "Engine & Service",
            "daily_rate": 1.12,
            "on_hand": 28,
            "minimum": 12,
            "target": 60,
            "lead_days": 18,
            "supplier_index": 3,
            "moq": 2,
            "order_uom": dozen,
            "price": 78.0,
        },
    ]
    extra_products = [
        ("Engine & Service", "Cabin Air Filter"),
        ("Engine & Service", "Fuel Filter Cartridge"),
        ("Engine & Service", "Ignition Coil"),
        ("Engine & Service", "Serpentine Belt"),
        ("Engine & Service", "Engine Mount"),
        ("Engine & Service", "Thermostat Assembly"),
        ("Engine & Service", "Water Pump Assembly"),
        ("Engine & Service", "Valve Cover Gasket"),
        ("Engine & Service", "Oil Pump"),
        ("Engine & Service", "Camshaft Position Sensor"),
        ("Braking", "Rear Brake Pad Set"),
        ("Braking", "Front Brake Disc"),
        ("Braking", "Rear Brake Disc"),
        ("Braking", "Brake Caliper Repair Kit"),
        ("Braking", "Brake Master Cylinder"),
        ("Braking", "ABS Wheel Speed Sensor"),
        ("Braking", "Front Brake Hose"),
        ("Braking", "Brake Shoe Set"),
        ("Braking", "Brake Wear Sensor"),
        ("Electrical", "Alternator 12V"),
        ("Electrical", "Starter Motor"),
        ("Electrical", "AGM Battery 70Ah"),
        ("Electrical", "Left Headlamp Assembly"),
        ("Electrical", "Right Tail Lamp Assembly"),
        ("Electrical", "Turn Signal Relay"),
        ("Electrical", "Starter Solenoid"),
        ("Electrical", "Front Wiper Motor"),
        ("Electrical", "Engine Control Relay"),
        ("Electrical", "Oxygen Sensor"),
        ("Suspension & Steering", "Front Shock Absorber"),
        ("Suspension & Steering", "Strut Mount Kit"),
        ("Suspension & Steering", "Lower Ball Joint"),
        ("Suspension & Steering", "Left Control Arm"),
        ("Suspension & Steering", "Tie Rod End"),
        ("Suspension & Steering", "Wheel Bearing Hub"),
        ("Suspension & Steering", "Stabilizer Link"),
        ("Suspension & Steering", "CV Joint Assembly"),
        ("Suspension & Steering", "Wheel Bolt Set"),
        ("Suspension & Steering", "Suspension Bushing Kit"),
        ("Cooling", "Radiator Assembly"),
        ("Cooling", "Radiator Fan Motor"),
        ("Cooling", "Coolant Expansion Tank"),
        ("Cooling", "Upper Coolant Hose"),
        ("Cooling", "Engine Temperature Sensor"),
        ("Cooling", "Intercooler Hose"),
        ("Cooling", "Radiator Cap"),
        ("Cooling", "Heater Core"),
        ("Cooling", "Coolant Reservoir Hose"),
        ("Cooling", "Fan Control Module"),
        ("Drivetrain", "Clutch Kit"),
        ("Drivetrain", "Clutch Slave Cylinder"),
        ("Drivetrain", "Transmission Mount"),
        ("Drivetrain", "Drive Shaft Boot Kit"),
        ("Drivetrain", "Differential Oil Seal"),
        ("Drivetrain", "Gearbox Oil Cooler"),
        ("Drivetrain", "Clutch Release Bearing"),
        ("Drivetrain", "CV Axle Shaft"),
        ("Drivetrain", "Manual Gear Selector Cable"),
        ("Drivetrain", "Flywheel Assembly"),
        ("Drivetrain", "Transmission Oil Pan"),
    ]
    if len(focus_parts) + len(extra_products) != 64:
        raise RuntimeError("The Atlas showroom catalogue must contain exactly 64 distinct parts.")

    all_parts = list(focus_parts)
    for number, (category, name) in enumerate(extra_products, start=1):
        all_parts.append(
            {
                "sku": f"AT-{category_names.index(category) + 1:02d}-{number:03d}",
                "name": name,
                "category": category,
                "daily_rate": 0.0,
                "on_hand": (0, 3, 8, 16, 24, 45)[number % 6],
                "minimum": (4, 6, 8, 10)[number % 4],
                "target": (18, 24, 32, 40)[number % 4],
                "lead_days": 7 + (number * 3 % 24),
                "supplier_index": number % len(suppliers),
                "moq": (1, 2, 4, 6)[number % 4],
                "order_uom": unit,
                "price": float(65 + number * 11),
            }
        )

    product_model = env["product.template"].with_company(company)
    supplier_info_model = env["product.supplierinfo"].with_company(company)
    orderpoint_model = env["stock.warehouse.orderpoint"].with_company(company)
    quant_model = env["stock.quant"].with_company(company)
    product_records = {}
    for index, part in enumerate(all_parts):
        template = product_model.search(
            [
                ("default_code", "=", part["sku"]),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        is_focus = part["daily_rate"] > 0
        safety_stock = part["minimum"] if index % 5 != 0 or is_focus else 0
        values = {
            "name": part["name"],
            "default_code": part["sku"],
            "company_id": company.id,
            "categ_id": categories[part["category"]].id,
            "is_storable": True,
            "sale_ok": True,
            "purchase_ok": True,
            "uom_id": unit.id,
            "list_price": part["price"],
            "standard_price": round(part["price"] * 0.48, 2),
            "autostock_enabled": True,
            "autostock_oem_reference": False,
            "autostock_priority": "critical" if is_focus and part["sku"] in {"AT-FLT-001", "AT-BRK-001"} else "standard",
            "autostock_safety_stock": safety_stock,
            "autostock_lead_time_days": part["lead_days"],
        }
        if template:
            template.write(values)
        else:
            template = product_model.create(values)
        product = template.product_variant_id
        product_records[part["sku"]] = {"template": template, "product": product, "part": part}
        if is_focus:
            created_at = fields.Datetime.to_string(datetime.combine(history_start, time.min))
            # Odoo intentionally prevents ORM writes to its audit columns once
            # the registry is ready. The showroom uses truthful historical
            # fixture dates, so update only these two newly seeded records'
            # creation metadata with parameterized SQL. All business records
            # and their transitions continue through the Odoo ORM/workflows.
            env.cr.execute(
                "UPDATE product_template SET create_date = %s WHERE id = %s",
                (created_at, template.id),
            )
            env.cr.execute(
                "UPDATE product_product SET create_date = %s WHERE id = %s",
                (created_at, product.id),
            )
            template.invalidate_recordset(["create_date"])
            product.invalidate_recordset(["create_date"])
            if fields.Datetime.to_datetime(product.create_date).date() > history_start:
                raise RuntimeError(
                    f"Odoo kept {part['sku']} creation date at {product.create_date}; "
                    "cannot safely claim earlier delivery-history coverage."
                )

        orderpoint = orderpoint_model.search(
            [
                ("product_id", "=", product.id),
                ("warehouse_id", "=", central.id),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if index % 9 == 8 and not is_focus:
            if orderpoint:
                orderpoint.unlink()
        else:
            rule_values = {
                "product_id": product.id,
                "warehouse_id": central.id,
                "location_id": central.lot_stock_id.id,
                "company_id": company.id,
                "product_min_qty": part["minimum"],
                "product_max_qty": part["target"],
                "replenishment_uom_id": part["order_uom"].id,
            }
            if orderpoint:
                orderpoint.write(rule_values)
            else:
                orderpoint_model.create(rule_values)

        supplier = suppliers[part["supplier_index"]]
        supplier_line = supplier_info_model.search(
            [
                ("product_tmpl_id", "=", template.id),
                ("partner_id", "=", supplier.id),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if index % 14 == 13 and not is_focus:
            if supplier_line:
                supplier_line.unlink()
        else:
            term_values = {
                "partner_id": supplier.id,
                "product_tmpl_id": template.id,
                "company_id": company.id,
                "product_uom_id": unit.id,
                "delay": part["lead_days"],
                "min_qty": 1.0,
                "autostock_min_order_qty": part["moq"],
                "price": round(part["price"] * 0.42, 2),
            }
            if supplier_line:
                supplier_line.write(term_values)
            else:
                supplier_info_model.create(term_values)

    # Ensure inventory transactions, policies and vendor terms use actual Odoo
    # records. The locally generated demand series is deterministic and only
    # supplies inputs to these completed sale/delivery workflows.
    rng = random.Random(20261010)
    focus_skus = [part["sku"] for part in focus_parts]
    weekday_factors = (0.88, 1.08, 1.12, 1.06, 1.0, 0.76, 0.62)

    def poisson(lam):
        limit = math.exp(-lam)
        count = 0
        product_value = 1.0
        while product_value > limit:
            count += 1
            product_value *= rng.random()
        return count - 1

    scheduled_sales = []
    demand_totals = {sku: 0 for sku in focus_skus}
    for offset in range(HISTORY_DAYS):
        day = history_start + timedelta(days=offset)
        seasonal_factor = 1 + 0.12 * math.sin(offset / 24)
        lines = []
        for sku in focus_skus:
            part = product_records[sku]["part"]
            mean = part["daily_rate"] * weekday_factors[day.weekday()] * seasonal_factor
            if offset % 47 in (15, 16):
                mean *= 1.45
            quantity = poisson(mean)
            if quantity:
                lines.append((sku, quantity))
                demand_totals[sku] += quantity
        if lines:
            scheduled_sales.append((day, lines))

    for sku in focus_skus:
        item = product_records[sku]
        opening_quantity = demand_totals[sku] + item["part"]["on_hand"] + 60
        quant_model._update_available_quantity(
            item["product"], central.lot_stock_id, opening_quantity
        )

    customers_for_sales = env["res.partner"].browse([partner.id for partner in customers])
    sale_order_model = env["sale.order"].with_company(company)
    completed_deliveries = 0
    for order_index, (day, lines) in enumerate(scheduled_sales):
        client_reference = f"ATLAS-SHOWROOM-{day.strftime('%Y%m%d')}"
        order = sale_order_model.search(
            [
                ("company_id", "=", company.id),
                ("client_order_ref", "=", client_reference),
            ],
            limit=1,
        )
        if not order:
            customer = customers_for_sales[order_index % len(customers_for_sales)]
            order = sale_order_model.create(
                {
                    "company_id": company.id,
                    "partner_id": customer.id,
                    "partner_invoice_id": customer.id,
                    "partner_shipping_id": customer.id,
                    "warehouse_id": central.id,
                    "date_order": fields.Datetime.to_string(datetime.combine(day, time(10, 0))),
                    "client_order_ref": client_reference,
                    "note": (
                        "Fictional local showroom transaction generated for demonstration. "
                        "No customer order was received or supplied by a real business."
                    ),
                    "order_line": [
                        Command.create(
                            {
                                "product_id": product_records[sku]["product"].id,
                                "product_uom_qty": quantity,
                                "product_uom_id": unit.id,
                                "price_unit": product_records[sku]["part"]["price"],
                            }
                        )
                        for sku, quantity in lines
                    ],
                }
            )
            order.action_confirm()

        picking = order.picking_ids.filtered(lambda record: record.state != "done")[:1]
        if not picking:
            completed_deliveries += len(order.picking_ids.filtered(lambda record: record.state == "done"))
            continue
        picking.action_assign()
        for move in picking.move_ids.filtered(lambda record: record.state not in ("done", "cancel")):
            move.write({"quantity": move.product_uom_qty, "picked": True})
        validation = picking.button_validate()
        if isinstance(validation, dict):
            raise RuntimeError(
                f"Odoo requested an unexpected delivery wizard for {client_reference}: {validation.get('res_model')}"
            )
        if picking.state != "done":
            raise RuntimeError(f"Delivery {picking.name} did not reach the done state.")
        picking.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(day, time(12, 0)))}
        )
        completed_deliveries += 1

    # The closing inventory snapshot deliberately represents a varied, current
    # business scenario after historical deliveries. It is written using Odoo's
    # stock quant API and is labeled by the company-level demo indicator.
    for index, item in enumerate(all_parts):
        product = product_records[item["sku"]]["product"]
        central_product = product.with_company(company).with_context(location=central.lot_stock_id.id)
        central_current = central_product.qty_available
        central_target = item["on_hand"]
        central_difference = central_target - central_current
        if central_difference:
            quant_model._update_available_quantity(product, central.lot_stock_id, central_difference)
        if index % 3 != 2 or item["daily_rate"]:
            south_target = (0, 2, 5, 9, 14, 22)[index % 6]
            if item["sku"] == "AT-FLT-001":
                south_target = 8
            south_product = product.with_company(company).with_context(location=south.lot_stock_id.id)
            south_current = south_product.qty_available
            south_difference = south_target - south_current
            if south_difference:
                quant_model._update_available_quantity(product, south.lot_stock_id, south_difference)

    # Process forecasts by calling the same validated request, source snapshot,
    # worker and manager-review methods used by the Odoo screens.
    admin = env.ref("base.user_admin")
    admin_password = os.environ.get("AUTOSTOCK_SHOWROOM_ADMIN_PASSWORD", "")
    if len(admin_password) < 32:
        raise RuntimeError("A locally generated showroom administrator password is required.")
    admin.write(
        {
            "password": admin_password,
            "company_id": company.id,
            "company_ids": [Command.set([company.id])],
            "group_ids": [
                Command.link(env.ref("stock.group_stock_manager").id),
                Command.link(env.ref("sales_team.group_sale_manager").id),
            ],
        }
    )
    forecast_model = (
        env["autostock.forecast.run"]
        .with_user(admin)
        .with_company(company)
        .with_context(allowed_company_ids=[company.id])
    )
    if set(SUPPORTED_HORIZONS) != {7, 30, 60}:
        raise RuntimeError("The available AutoStock forecast horizons no longer match this showroom setup.")
    forecast_runs = []
    horizons = (7, 30, 60)
    forecast_skus = [sku for sku in focus_skus if sku != "AT-FLT-001"] + ["AT-FLT-001"]
    for sku in forecast_skus:
        product = product_records[sku]["product"]
        for horizon in horizons:
            existing = env["autostock.forecast.run"].search(
                [
                    ("company_id", "=", company.id),
                    ("warehouse_id", "=", central.id),
                    ("product_id", "=", product.id),
                    ("source_type", "=", REAL_SOURCE),
                    ("horizon_days", "=", str(horizon)),
                    ("history_start_date", "=", history_start),
                    ("history_end_date", "=", history_end),
                ],
                order="create_date desc, id desc",
                limit=1,
            )
            if existing:
                run = existing
            else:
                result = forecast_model.request_forecast(
                    product.id, horizon, history_start, history_end, central.id
                )
                run = env["autostock.forecast.run"].browse(result["id"])
            if run.state == "queued":
                run._process_queued_run()
                run.invalidate_recordset()
            if run.state != "completed":
                raise RuntimeError(
                    f"Forecast for {sku} ({horizon} days) did not complete: "
                    f"{run.state}: {run.failure_reason or run.evaluation_status}"
                )
            if run.review_status != "reviewed":
                run.with_user(admin).action_mark_reviewed()
            forecast_runs.append(run)

    parameters.set_param("autostock_showroom.seed_version", SEED_VERSION)
    parameters.set_param(
        "autostock_showroom.data_provenance",
        "Fictional local showroom: products, suppliers, stock counts, customer records, "
        "and sales orders were generated for demonstration. Historical sale/delivery "
        "records were completed through Odoo; forecasts use the installed AutoStock "
        "worker and evaluated fulfilled-sales history. No real business or customer data was imported.",
    )
    parameters.set_param(
        "autostock_showroom.forecast_runs",
        ",".join(str(run.id) for run in forecast_runs),
    )
    env.cr.commit()  # noqa: F821
    print(
        "Seeded Atlas Auto Distribution: 64 fictional automotive parts, 2 warehouses, "
        f"{len(suppliers)} suppliers, {len(scheduled_sales)} completed customer deliveries "
        f"({completed_deliveries} Odoo transfers), and {len(forecast_runs)} evaluated "
        "and manager-reviewed Odoo forecasts (7/30/60 days)."
    )
