"""Permission-aware, read-only product inventory catalog for the React client."""

from datetime import datetime, timedelta
import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools.float_utils import float_round


DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_STATUS_CANDIDATES = 50000
MAX_SUPPLIER_MATCH_GROUPS = 50000
STATUS_SCAN_BATCH_SIZE = 500
MAX_INVENTORY_WAREHOUSES = 50
MAX_INVENTORY_CATEGORIES = 500
MAX_INVENTORY_SUPPLIERS = 500
MAX_SUPPLIER_LINES_PER_PAGE = 20000
MAX_RECENT_MOVEMENTS = 20
OPEN_MOVE_STATES = ("waiting", "confirmed", "assigned", "partially_available")


class AutoStockInventoryCatalog(models.AbstractModel):
    _name = "autostock.inventory.catalog"
    _description = "AutoStock Read-only Inventory Catalog"

    @api.model
    def _company_env(self, company):
        return self.with_company(company).with_context(
            allowed_company_ids=[company.id]
        )

    @api.model
    def _require_inventory_access(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError(
                _("Inventory access is required to view the parts catalog.")
            )

    @api.model
    def _can_read(self, model):
        try:
            model.check_access("read")
        except AccessError:
            return False
        return True

    @api.model
    def _parse_id(self, value, label, *, allow_empty=True):
        if value in (None, "") and allow_empty:
            return False
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid %(label)s.", label=label)) from error
        if parsed <= 0:
            raise ValidationError(_("Choose a valid %(label)s.", label=label))
        return parsed

    @api.model
    def _supplier_domain(self, company, today, *, query=False, supplier_id=False):
        domain = [
            ("company_id", "in", [False, company.id]),
            ("partner_id", "!=", False),
            ("product_tmpl_id.active", "=", True),
            ("product_tmpl_id.is_storable", "=", True),
            ("product_tmpl_id.company_id", "in", [False, company.id]),
            "|",
            ("date_start", "=", False),
            ("date_start", "<=", today),
            "|",
            ("date_end", "=", False),
            ("date_end", ">=", today),
        ]
        if supplier_id:
            domain.append(("partner_id", "=", supplier_id))
        if query:
            domain.append(("partner_id.name", "ilike", query))
        return domain

    @api.model
    def _supplier_product_domain(self, SupplierInfo, company, *, query=False, supplier_id=False):
        """Find exact vendor-linked variants, without a first-page product cap."""
        today = fields.Date.today()
        grouped_lines = SupplierInfo._read_group(
            self._supplier_domain(
                company, today, query=query, supplier_id=supplier_id
            ),
            ["product_tmpl_id", "product_id"],
            [],
            limit=MAX_SUPPLIER_MATCH_GROUPS + 1,
            order="product_tmpl_id, product_id",
        )
        if len(grouped_lines) > MAX_SUPPLIER_MATCH_GROUPS:
            raise ValidationError(
                _(
                    "This supplier filter matches more than %(limit)s parts. Add a product name, SKU, or OEM reference to narrow the results.",
                    limit=MAX_SUPPLIER_MATCH_GROUPS,
                )
            )
        general_templates = set()
        variant_ids = set()
        for template, variant in grouped_lines:
            if variant:
                variant_ids.add(variant.id)
            elif template:
                general_templates.add(template.id)

        matches = []
        if general_templates:
            matches.append(Domain([("product_tmpl_id", "in", sorted(general_templates))]))
        if variant_ids:
            matches.append(Domain([("id", "in", sorted(variant_ids))]))
        return Domain.OR(matches) if matches else Domain([("id", "=", 0)])

    @api.model
    def _catalog_domain(
        self,
        Product,
        SupplierInfo,
        company,
        *,
        query="",
        supplier_query="",
        supplier_id=False,
        category_id=False,
        tracked="all",
        active="active",
        supplier_access=True,
    ):
        domain = Domain(
            [
                ("is_storable", "=", True),
                ("company_id", "in", [False, company.id]),
            ]
        )
        if active == "active":
            domain &= Domain([("active", "=", True)])
        elif active == "archived":
            domain &= Domain([("active", "=", False)])
        if tracked == "tracked":
            domain &= Domain([("autostock_enabled", "=", True)])
        elif tracked == "not_tracked":
            domain &= Domain([("autostock_enabled", "=", False)])
        if category_id:
            domain &= Domain([("categ_id", "=", category_id)])

        if query:
            query_domains = [
                Domain([("name", "ilike", query)]),
                Domain([("default_code", "ilike", query)]),
                Domain([("autostock_oem_reference", "ilike", query)]),
            ]
            if supplier_access:
                query_domains.append(
                    self._supplier_product_domain(
                        SupplierInfo, company, query=query
                    )
                )
            domain &= Domain.OR(query_domains)

        if supplier_query:
            if not supplier_access:
                raise AccessError(
                    _("Your Odoo role cannot filter parts by supplier information.")
                )
            domain &= self._supplier_product_domain(
                SupplierInfo, company, query=supplier_query
            )
        if supplier_id:
            if not supplier_access:
                raise AccessError(
                    _("Your Odoo role cannot filter parts by supplier information.")
                )
            domain &= self._supplier_product_domain(
                SupplierInfo, company, supplier_id=supplier_id
            )
        return domain

    @api.model
    def _visible_warehouses(self, Scoped, company, *, selected_id=False):
        Warehouse = Scoped.env["stock.warehouse"]
        domain = [("company_id", "=", company.id)]
        total = Warehouse.search_count(domain)
        warehouses = Warehouse.search(
            domain, order="name, id", limit=MAX_INVENTORY_WAREHOUSES + 1
        )
        limited = len(warehouses) > MAX_INVENTORY_WAREHOUSES
        warehouses = warehouses[:MAX_INVENTORY_WAREHOUSES]
        selected = False
        if selected_id:
            selected = Warehouse.search(
                domain + [("id", "=", selected_id)], limit=1
            )
            if not selected:
                raise AccessError(
                    _("That warehouse is not available in the selected company.")
                )
            if selected.id not in warehouses.ids:
                warehouses |= selected
        return warehouses, selected, total, limited

    @api.model
    def get_options(self, supplier_query=""):
        """Return bounded, permission-aware filter choices for one company."""
        self._require_inventory_access()
        company = self.env.company
        Scoped = self._company_env(company)
        Product = Scoped.env["product.product"].with_context(active_test=False)
        SupplierInfo = Scoped.env["product.supplierinfo"]
        warehouses, _selected, total_warehouses, warehouse_limited = (
            self._visible_warehouses(Scoped, company)
        )
        product_domain = Domain(
            [
                ("active", "=", True),
                ("is_storable", "=", True),
                ("company_id", "in", [False, company.id]),
            ]
        )
        category_groups = Product._read_group(
            product_domain,
            ["categ_id"],
            [],
            limit=MAX_INVENTORY_CATEGORIES + 1,
            order="categ_id",
        )
        category_limited = len(category_groups) > MAX_INVENTORY_CATEGORIES
        categories = [
            {"id": category.id, "name": category.display_name}
            for (category,) in category_groups[:MAX_INVENTORY_CATEGORIES]
            if category
        ]

        supplier_access = self._can_read(SupplierInfo)
        suppliers = []
        supplier_limited = False
        supplier_query = (supplier_query or "").strip()[:80]
        if supplier_access:
            supplier_domain = self._supplier_domain(
                company,
                fields.Date.today(),
                query=supplier_query if len(supplier_query) >= 2 else False,
            )
            supplier_groups = SupplierInfo._read_group(
                supplier_domain,
                ["partner_id"],
                [],
                limit=MAX_INVENTORY_SUPPLIERS + 1,
                order="partner_id",
            )
            supplier_limited = len(supplier_groups) > MAX_INVENTORY_SUPPLIERS
            suppliers = [
                {"id": partner.id, "name": partner.display_name}
                for (partner,) in supplier_groups[:MAX_INVENTORY_SUPPLIERS]
                if partner
            ]

        return {
            "warehouses": [
                {"id": warehouse.id, "name": warehouse.display_name}
                for warehouse in warehouses
            ],
            "warehouse_options_limited": warehouse_limited,
            "total_warehouses": total_warehouses,
            "categories": categories,
            "category_options_limited": category_limited,
            "suppliers": suppliers,
            "supplier_options_limited": supplier_limited,
            "supplier_access": supplier_access,
            "supplier_access_note": (
                False
                if supplier_access
                else _("Your role cannot view supplier terms or filter by supplier.")
            ),
        }

    @api.model
    def _stock_status(self, product, on_hand):
        if on_hand <= 0:
            return "out_of_stock"
        threshold = product.autostock_safety_stock or 0.0
        if threshold > 0 and on_hand <= threshold:
            return "low_stock"
        return "in_stock"

    @api.model
    def _status_filtered_ids(self, Product, domain, status, order, page, page_size):
        if status == "all":
            total = Product.search_count(domain)
            pages = math.ceil(total / page_size) if total else 0
            page = min(page, pages) if pages else 1
            products = Product.search(
                domain,
                order=order,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return total, page, products, False

        if status == "out_of_stock":
            status_domain = domain & Domain([("qty_available", "<=", 0)])
            total = Product.search_count(status_domain)
            pages = math.ceil(total / page_size) if total else 0
            page = min(page, pages) if pages else 1
            products = Product.search(
                status_domain,
                order=order,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return total, page, products, False

        candidate_domain = domain & Domain([("qty_available", ">", 0)])
        if status == "low_stock":
            candidate_domain &= Domain([("autostock_safety_stock", ">", 0)])
        candidates = Product.search_count(candidate_domain)
        if candidates > MAX_STATUS_CANDIDATES:
            raise ValidationError(
                _(
                    "This stock-status filter covers more than %(limit)s parts. Add a search, warehouse, category, or supplier filter and try again.",
                    limit=MAX_STATUS_CANDIDATES,
                )
            )

        matching_ids = []
        scan_offset = 0
        while scan_offset < candidates:
            batch = Product.search(
                candidate_domain,
                order=order,
                offset=scan_offset,
                limit=STATUS_SCAN_BATCH_SIZE,
            )
            if not batch:
                break
            for product in batch:
                item_status = self._stock_status(product, product.qty_available)
                if item_status == status:
                    matching_ids.append(product.id)
            scan_offset += len(batch)

        total = len(matching_ids)
        pages = math.ceil(total / page_size) if total else 0
        page = min(page, pages) if pages else 1
        start = (page - 1) * page_size
        products = Product.browse(matching_ids[start : start + page_size])
        return total, page, products, candidates > 0

    @api.model
    def _quantity_values(self, Product, products, company, warehouse=False):
        if not products:
            return {}
        context = {"allowed_company_ids": [company.id]}
        if warehouse:
            context["warehouse_id"] = warehouse.id
        rows = Product.with_context(**context).browse(products.ids).read(
            [
                "qty_available",
                "free_qty",
                "incoming_qty",
                "outgoing_qty",
                "virtual_available",
            ]
        )
        return {row["id"]: row for row in rows}

    @api.model
    def _rounded(self, product, value):
        return float_round(
            value or 0.0, precision_rounding=product.uom_id.rounding
        )

    @api.model
    def _active_supplier(self, Risk, lines, product, company):
        return Risk._active_supplier(
            lines,
            product,
            company,
            fields.Date.today(),
        )

    @api.model
    def _supplier_payload(self, line, product):
        if not line:
            return False
        supplier_uom = line.product_uom_id or product.uom_id
        return {
            "id": line.partner_id.id,
            "name": line.partner_id.display_name,
            "lead_time_days": max(0, int(line.delay or 0)),
            "lead_time_label": _("Supplier lead time"),
            "minimum_order_qty": self._rounded(
                product,
                supplier_uom._compute_quantity(
                    line.autostock_min_order_qty or 0.0,
                    product.uom_id,
                    round=False,
                ),
            ),
            "minimum_order_uom": product.uom_id.display_name,
            "company_specific": bool(line.company_id),
        }

    @api.model
    def get_inventory_page(
        self,
        *,
        query="",
        supplier_query="",
        status="all",
        warehouse_id=False,
        category_id=False,
        supplier_id=False,
        tracked="all",
        active="active",
        sort="name",
        direction="asc",
        page=1,
        page_size=DEFAULT_PAGE_SIZE,
    ):
        """Return one server-filtered page and accurate company stock summaries."""
        self._require_inventory_access()
        company = self.env.company
        Scoped = self._company_env(company)
        Product = Scoped.env["product.product"].with_context(active_test=False)
        SupplierInfo = Scoped.env["product.supplierinfo"]
        supplier_access = self._can_read(SupplierInfo)

        query = (query or "").strip()[:80]
        supplier_query = (supplier_query or "").strip()[:80]
        status = (status or "all").strip()
        tracked = (tracked or "all").strip()
        active = (active or "active").strip()
        sort = (sort or "name").strip()
        direction = (direction or "asc").strip()
        if status not in {"all", "in_stock", "low_stock", "out_of_stock"}:
            raise ValidationError(_("Choose a supported stock status."))
        if tracked not in {"all", "tracked", "not_tracked"}:
            raise ValidationError(_("Choose a supported tracking filter."))
        if active not in {"active", "archived", "all"}:
            raise ValidationError(_("Choose a supported product-state filter."))
        if sort not in {"name", "sku"}:
            raise ValidationError(_("Sort parts by name or SKU."))
        if direction not in {"asc", "desc"}:
            raise ValidationError(_("Choose ascending or descending sort order."))
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid inventory page.")) from error
        if page < 1 or page > 1000000:
            raise ValidationError(_("Choose a valid inventory page."))
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValidationError(
                _("Page size must be between 1 and %(limit)s parts.", limit=MAX_PAGE_SIZE)
            )
        if supplier_query and len(supplier_query) < 2:
            supplier_query = ""
        if supplier_query and not supplier_access:
            raise AccessError(
                _("Your Odoo role cannot filter parts by supplier information.")
            )

        warehouse_id = self._parse_id(warehouse_id, _("warehouse"))
        category_id = self._parse_id(category_id, _("category"))
        supplier_id = self._parse_id(supplier_id, _("supplier"))
        warehouses, selected_warehouse, total_warehouses, warehouse_limited = (
            self._visible_warehouses(Scoped, company, selected_id=warehouse_id)
        )
        if selected_warehouse:
            stock_warehouses = selected_warehouse
        else:
            stock_warehouses = warehouses

        Product.check_access("read")
        if category_id and not Scoped.env["product.category"].search(
            [("id", "=", category_id)], limit=1
        ):
            raise ValidationError(_("Choose a product category in this catalog."))
        base_domain = self._catalog_domain(
            Product,
            SupplierInfo,
            company,
            query=query,
            supplier_query=supplier_query,
            supplier_id=supplier_id,
            category_id=category_id,
            tracked=tracked,
            active=active,
            supplier_access=supplier_access,
        )
        quantity_context = {"allowed_company_ids": [company.id]}
        if selected_warehouse:
            quantity_context["warehouse_id"] = selected_warehouse.id
        ScopedProduct = Product.with_context(**quantity_context)
        order = f"{'default_code' if sort == 'sku' else 'name'} {direction}, id {direction}"
        total, page, products, status_scan_used = self._status_filtered_ids(
            ScopedProduct,
            base_domain,
            status,
            order,
            page,
            page_size,
        )
        products = Product.browse(products.ids)
        page_quantities = self._quantity_values(
            Product, products, company, selected_warehouse
        )

        warehouse_quantities = {}
        for warehouse in stock_warehouses:
            warehouse_quantities[warehouse.id] = self._quantity_values(
                Product, products, company, warehouse
            )

        supplier_lines_limited = False
        supplier_lines = SupplierInfo.browse()
        if supplier_access and products:
            supplier_lines = SupplierInfo.search(
                [
                    ("company_id", "in", [False, company.id]),
                    ("product_tmpl_id", "in", products.mapped("product_tmpl_id").ids),
                    "|",
                    ("product_id", "=", False),
                    ("product_id", "in", products.ids),
                ],
                order="sequence, min_qty, id",
                limit=MAX_SUPPLIER_LINES_PER_PAGE + 1,
            )
            supplier_lines_limited = len(supplier_lines) > MAX_SUPPLIER_LINES_PER_PAGE
            supplier_lines = supplier_lines[:MAX_SUPPLIER_LINES_PER_PAGE]
        Risk = Scoped.env["autostock.inventory.risk"]
        rows = []
        for product in products:
            quantities = page_quantities.get(product.id, {})
            on_hand = quantities.get("qty_available", 0.0)
            free_qty = quantities.get("free_qty", 0.0)
            supplier_line = (
                self._active_supplier(Risk, supplier_lines, product, company)
                if supplier_access and not supplier_lines_limited
                else False
            )
            supplier = self._supplier_payload(supplier_line, product)
            lead_days = (
                supplier["lead_time_days"]
                if supplier
                else max(0, int(product.autostock_lead_time_days or 0))
            )
            lead_source = "supplier" if supplier else "planning_assumption"
            lead_label = (
                supplier["lead_time_label"]
                if supplier
                else _("Planning assumption")
            )
            warehouse_stocks = []
            for warehouse in stock_warehouses:
                values = warehouse_quantities[warehouse.id].get(product.id, {})
                wh_on_hand = values.get("qty_available", 0.0)
                wh_free = values.get("free_qty", 0.0)
                wh_incoming = values.get("incoming_qty", 0.0)
                if wh_on_hand or wh_incoming or values.get("outgoing_qty", 0.0):
                    warehouse_stocks.append(
                        {
                            "id": warehouse.id,
                            "name": warehouse.display_name,
                            "on_hand": self._rounded(product, wh_on_hand),
                            "available": self._rounded(product, wh_free),
                            "reserved": self._rounded(product, wh_on_hand - wh_free),
                            "incoming": self._rounded(product, wh_incoming),
                            "outgoing": self._rounded(
                                product, values.get("outgoing_qty", 0.0)
                            ),
                        }
                    )
            rows.append(
                {
                    "product_id": product.id,
                    "template_id": product.product_tmpl_id.id,
                    "name": product.product_tmpl_id.name,
                    "sku": product.default_code or "—",
                    "reference": product.autostock_oem_reference or False,
                    "category_id": product.categ_id.id,
                    "category": product.categ_id.display_name or _("Uncategorized"),
                    "tracked": bool(product.autostock_enabled),
                    "active": bool(product.active),
                    "uom": product.uom_id.display_name,
                    "status": self._stock_status(product, on_hand),
                    "on_hand": self._rounded(product, on_hand),
                    "available": self._rounded(product, free_qty),
                    "reserved": self._rounded(product, on_hand - free_qty),
                    "incoming": self._rounded(
                        product, quantities.get("incoming_qty", 0.0)
                    ),
                    "outgoing": self._rounded(
                        product, quantities.get("outgoing_qty", 0.0)
                    ),
                    "projected": self._rounded(
                        product, quantities.get("virtual_available", 0.0)
                    ),
                    "warehouse_count": len(warehouse_stocks),
                    "warehouses": warehouse_stocks,
                    "supplier": supplier,
                    "supplier_access_note": (
                        False
                        if supplier_access
                        else _("Your role cannot view supplier terms.")
                    ),
                    "supplier_lookup_limited": supplier_lines_limited,
                    "lead_time_days": lead_days,
                    "lead_time_label": lead_label,
                    "lead_time_source": lead_source,
                }
            )

        dashboard = Scoped.env["autostock.dashboard"].get_dashboard_data()
        tracked_summary = dashboard["kpis"]
        total_catalog = Product.search_count(
            [
                ("active", "=", True),
                ("is_storable", "=", True),
                ("company_id", "in", [False, company.id]),
            ]
        )
        page_count = math.ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size
        return {
            "as_of": fields.Datetime.to_string(fields.Datetime.now()),
            "summary": {
                "total_tracked": dashboard["total_tracked"],
                "in_stock": tracked_summary["healthy"],
                "low_stock": tracked_summary["low"],
                "out_of_stock": tracked_summary["out"],
                "complete": not dashboard["summary_incomplete"],
                "sampled_products": tracked_summary["total"],
                "total_catalog": total_catalog,
            },
            "filters": {
                "query": query,
                "supplier_query": supplier_query,
                "status": status,
                "warehouse_id": selected_warehouse.id if selected_warehouse else False,
                "category_id": category_id or False,
                "supplier_id": supplier_id or False,
                "tracked": tracked,
                "active": active,
                "sort": sort,
                "direction": direction,
            },
            "items": rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": page_count,
                "has_previous": page > 1 and page_count > 0,
                "has_next": page < page_count,
                "summary_exact": True,
                "status_scan_used": status_scan_used,
            },
            "coverage": {
                "tracked_summary_complete": not dashboard["summary_incomplete"],
                "warehouse_scope_limited": warehouse_limited,
                "supplier_lines_limited": supplier_lines_limited,
                "supplier_terms_available": supplier_access,
                "status_filter_complete": True,
            },
            "empty_catalog": total_catalog == 0,
        }

    @api.model
    def _movement_label(self, move):
        if move.is_inventory:
            return "adjustment", _("Adjustment")
        if move.state == "done":
            if move.picking_code == "incoming" or move.location_usage in (
                "supplier",
                "transit",
            ):
                return "received", _("Received")
            if move.picking_code == "outgoing" or move.location_dest_usage == "customer":
                return "shipped", _("Shipped")
            return "internal_transfer", _("Internal transfer")
        if move.picking_code == "incoming":
            return "incoming_purchase", _("Incoming purchase")
        if move.picking_code == "outgoing":
            if move.quantity:
                return "reserved_delivery", _("Reserved for customer orders")
            return "scheduled_delivery", _("Customer delivery scheduled")
        return "internal_transfer_planned", _("Internal transfer planned")

    @api.model
    def _recent_movements(self, Scoped, company, product, warehouse=False):
        StockMove = Scoped.env["stock.move"]
        try:
            StockMove.check_access("read")
        except AccessError:
            return False, [], _("Your role cannot view recent stock movements.")

        now = fields.Datetime.to_datetime(fields.Datetime.now())
        recent_start = fields.Datetime.to_string(now - timedelta(days=90))
        future_limit = fields.Datetime.to_string(now + timedelta(days=90))
        recent_done = Domain(
            [
                ("state", "=", "done"),
                ("date", ">=", recent_start),
                ("date", "<=", now),
            ]
        )
        upcoming = Domain(
            [
                ("state", "in", list(OPEN_MOVE_STATES)),
                ("date", ">=", now),
                ("date", "<=", future_limit),
            ]
        )
        domain = Domain(
            [
                ("company_id", "=", company.id),
                ("product_id", "=", product.id),
            ]
        ) & Domain.OR([recent_done, upcoming])
        if warehouse:
            domain &= Domain.OR(
                [
                    Domain([("location_id", "child_of", warehouse.view_location_id.id)]),
                    Domain([("location_dest_id", "child_of", warehouse.view_location_id.id)]),
                ]
            )
        moves = StockMove.search(
            domain,
            order="date desc, id desc",
            limit=MAX_RECENT_MOVEMENTS + 1,
        )
        has_more = len(moves) > MAX_RECENT_MOVEMENTS
        records = []
        for move in moves[:MAX_RECENT_MOVEMENTS]:
            kind, label = self._movement_label(move)
            if move.state == "done" or (
                move.picking_code == "outgoing" and move.quantity
            ):
                # Done and reserved move quantities are in the move UoM.
                quantity = move.product_uom._compute_quantity(
                    move.quantity, product.uom_id, round=False
                )
            else:
                # Odoo's product_qty is already expressed in the product UoM.
                quantity = move.product_qty
            move_date = fields.Datetime.to_datetime(move.date)
            records.append(
                {
                    "id": move.id,
                    "kind": kind,
                    "label": label,
                    "date": move_date.strftime("%Y-%m-%dT%H:%M:%SZ") if move_date else False,
                    "quantity": self._rounded(product, quantity),
                    "uom": product.uom_id.display_name,
                    "warehouse": move.warehouse_id.display_name or False,
                    "reference": move.reference or move.origin or False,
                }
            )
        note = (
            _("Showing up to the latest 20 completed changes and expected moves.")
            if has_more
            else _(
                "Completed changes cover the last 90 days. Expected moves are current planned activity."
            )
        )
        return True, records, note

    @api.model
    def get_product_detail(self, product_id, warehouse_id=False):
        """Return truthful company/warehouse stock and read-only product context."""
        self._require_inventory_access()
        company = self.env.company
        Scoped = self._company_env(company)
        Product = Scoped.env["product.product"].with_context(active_test=False)
        SupplierInfo = Scoped.env["product.supplierinfo"]
        Product.check_access("read")
        product_id = self._parse_id(product_id, _("part"), allow_empty=False)
        warehouse_id = self._parse_id(warehouse_id, _("warehouse"))
        product = Product.search(
            [
                ("id", "=", product_id),
                ("is_storable", "=", True),
                ("company_id", "in", [False, company.id]),
            ],
            limit=1,
        )
        if not product:
            raise AccessError(_("That part is not available in the selected company."))

        warehouses, selected_warehouse, total_warehouses, warehouse_limited = (
            self._visible_warehouses(Scoped, company, selected_id=warehouse_id)
        )
        company_quantities = self._quantity_values(Product, product, company).get(
            product.id, {}
        )
        warehouse_quantities = []
        for warehouse in warehouses:
            values = self._quantity_values(Product, product, company, warehouse).get(
                product.id, {}
            )
            on_hand = values.get("qty_available", 0.0)
            free_qty = values.get("free_qty", 0.0)
            warehouse_quantities.append(
                {
                    "id": warehouse.id,
                    "name": warehouse.display_name,
                    "selected": bool(selected_warehouse and warehouse.id == selected_warehouse.id),
                    "on_hand": self._rounded(product, on_hand),
                    "available": self._rounded(product, free_qty),
                    "reserved": self._rounded(product, on_hand - free_qty),
                    "incoming": self._rounded(product, values.get("incoming_qty", 0.0)),
                    "outgoing": self._rounded(product, values.get("outgoing_qty", 0.0)),
                    "projected": self._rounded(product, values.get("virtual_available", 0.0)),
                }
            )

        supplier_access = self._can_read(SupplierInfo)
        supplier = False
        supplier_note = False
        if supplier_access:
            lines = SupplierInfo.search(
                [
                    ("company_id", "in", [False, company.id]),
                    ("product_tmpl_id", "=", product.product_tmpl_id.id),
                    "|",
                    ("product_id", "=", False),
                    ("product_id", "=", product.id),
                ],
                order="sequence, min_qty, id",
            )
            supplier_line = self._active_supplier(
                Scoped.env["autostock.inventory.risk"],
                lines,
                product,
                company,
            )
            supplier = self._supplier_payload(supplier_line, product)
            if not supplier:
                supplier_note = _("No active supplier terms are recorded for this part.")
        else:
            supplier_note = _("Your role cannot view supplier terms for this part.")

        recommendation_rows = []
        risk_coverage = {
            "complete": True,
            "candidate_locations": 0,
            "scanned_locations": 0,
            "forecast_access_available": False,
            "forecast_access_reason": False,
        }
        if product.autostock_enabled:
            risk_data = Scoped.env["autostock.inventory.risk"].get_risk_data(
                warehouse_id=selected_warehouse.id if selected_warehouse else False,
                product_id=product.id,
                offset=0,
            )
            recommendation_rows = risk_data["rows"]
            risk_pagination = risk_data["pagination"]
            risk_coverage = {
                "complete": not risk_data["warehouse_scope_limited"]
                and not risk_pagination["has_next"],
                "candidate_locations": risk_pagination["candidate_pair_count"],
                "scanned_locations": risk_pagination["evaluated_pair_count"],
                "forecast_access_available": risk_data["forecast_access_available"],
                "forecast_access_reason": (
                    risk_data.get("forecast_access_reason") or False
                ),
            }

        movement_scope = selected_warehouse or False
        movements_available, movements, movement_note = self._recent_movements(
            Scoped, company, product, movement_scope
        )
        if not supplier and supplier_access:
            lead_time_days = max(0, int(product.autostock_lead_time_days or 0))
            lead_time_label = _("Planning assumption")
            lead_time_source = "planning_assumption"
        elif supplier:
            lead_time_days = supplier["lead_time_days"]
            lead_time_label = supplier["lead_time_label"]
            lead_time_source = "supplier"
        else:
            lead_time_days = max(0, int(product.autostock_lead_time_days or 0))
            lead_time_label = _("Planning assumption")
            lead_time_source = "planning_assumption"
        if not supplier_note and not supplier_access:
            supplier_note = _("Your role cannot view supplier terms for this part.")

        on_hand = company_quantities.get("qty_available", 0.0)
        free_qty = company_quantities.get("free_qty", 0.0)
        forecast_rows = [
            row
            for row in recommendation_rows
            if row.get("forecast", {}).get("run_id")
        ]
        forecast_summary = {
            "status": "not_tracked" if not product.autostock_enabled else "unavailable",
            "message": (
                _("This part is not enabled for AutoStock monitoring.")
                if not product.autostock_enabled
                else risk_coverage["forecast_access_reason"]
                or _("No matching reviewed delivery forecast is available for this part.")
            ),
            "horizon_days": False,
            "history_start": False,
            "history_end": False,
            "used_for_restock": False,
            "demand_before_delivery": False,
        }
        if forecast_rows:
            chosen = forecast_rows[0]
            forecast = chosen["forecast"]
            used = bool(forecast.get("used"))
            forecast_summary.update(
                {
                    "status": "used" if used else "not_used",
                    "message": (
                        _("A reviewed delivery forecast contributed demand through the expected delivery date.")
                        if used
                        else forecast.get("reason")
                        or _("A saved forecast exists but was not eligible for the restock estimate.")
                    ),
                    "horizon_days": forecast.get("horizon_days") or False,
                    "history_start": forecast.get("history_start") or False,
                    "history_end": forecast.get("history_end") or False,
                    "used_for_restock": used,
                    "demand_before_delivery": (
                        chosen["forecast_demand"] if used else False
                    ),
                }
            )

        return {
            "product": {
                "id": product.id,
                "template_id": product.product_tmpl_id.id,
                "name": product.product_tmpl_id.name,
                "sku": product.default_code or "—",
                "reference": product.autostock_oem_reference or False,
                "category_id": product.categ_id.id,
                "category": product.categ_id.display_name or _("Uncategorized"),
                "tracked": bool(product.autostock_enabled),
                "active": bool(product.active),
                "uom": product.uom_id.display_name,
                "safety_stock": self._rounded(
                    product, product.autostock_safety_stock or 0.0
                ),
            },
            "company_stock": {
                "on_hand": self._rounded(product, on_hand),
                "available": self._rounded(product, free_qty),
                "reserved": self._rounded(product, on_hand - free_qty),
                "incoming": self._rounded(
                    product, company_quantities.get("incoming_qty", 0.0)
                ),
                "outgoing": self._rounded(
                    product, company_quantities.get("outgoing_qty", 0.0)
                ),
                "projected": self._rounded(
                    product, company_quantities.get("virtual_available", 0.0)
                ),
            },
            "warehouses": warehouse_quantities,
            "supplier": supplier,
            "supplier_access": supplier_access,
            "supplier_note": supplier_note,
            "lead_time_days": lead_time_days,
            "lead_time_label": lead_time_label,
            "lead_time_source": lead_time_source,
            "forecast": forecast_summary,
            "recommendation_rows": recommendation_rows,
            "recommendation_coverage": risk_coverage,
            "movements_available": movements_available,
            "movements": movements,
            "movement_note": movement_note,
            "coverage": {
                "warehouse_scope_limited": warehouse_limited,
                "total_warehouses": total_warehouses,
                "supplier_terms_available": supplier_access,
            },
            "read_only": True,
        }
