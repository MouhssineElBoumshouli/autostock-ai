"""Company-scoped, read-only supplier and vendor-term data for the React client."""

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


DEFAULT_SUPPLIER_PAGE_SIZE = 12
MAX_SUPPLIER_PAGE_SIZE = 50
MAX_SUPPLIERS = 5000
MAX_SUPPLIER_TERMS = 100000
MAX_SUPPLIER_PRODUCTS = 50000
MAX_SUPPLIER_REORDER_SCAN = 5000
MAX_SUPPLIER_TERM_DETAIL = 10000


class AutoStockSupplierCatalog(models.AbstractModel):
    _name = "autostock.supplier.catalog"
    _description = "AutoStock Read-only Supplier Catalog"

    @api.model
    def _company_env(self, company):
        return self.with_company(company).with_context(
            allowed_company_ids=[company.id]
        )

    @api.model
    def _can_read(self, model):
        try:
            model.check_access("read")
        except AccessError:
            return False
        return True

    @api.model
    def _require_supplier_access(self, Scoped):
        if not Scoped.env.user.has_group("stock.group_stock_user"):
            raise AccessError(
                _("Inventory access is required to view supplier and stock information.")
            )
        Partner = Scoped.env["res.partner"]
        SupplierInfo = Scoped.env["product.supplierinfo"]
        Product = Scoped.env["product.product"]
        Product.check_access("read")
        if not self._can_read(Partner) or not self._can_read(SupplierInfo):
            raise AccessError(
                _("Your Odoo role cannot read supplier details and vendor terms.")
            )

    @api.model
    def _product_domain(self, company):
        return [
            ("active", "=", True),
            ("is_storable", "=", True),
            ("company_id", "in", [False, company.id]),
        ]

    @api.model
    def _term_domain(self, company, *, today=False, partner_ids=False):
        domain = [
            ("company_id", "in", [False, company.id]),
            ("partner_id", "!=", False),
            ("partner_id.company_id", "in", [False, company.id]),
            ("product_tmpl_id.active", "=", True),
            ("product_tmpl_id.is_storable", "=", True),
            ("product_tmpl_id.company_id", "in", [False, company.id]),
        ]
        if partner_ids is not False:
            domain.append(("partner_id", "in", partner_ids or [0]))
        if today:
            domain += [
                "|", ("date_start", "=", False), ("date_start", "<=", today),
                "|", ("date_end", "=", False), ("date_end", ">=", today),
                ("partner_id.active", "=", True),
            ]
        return domain

    @api.model
    def _parse_page(self, page, page_size):
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid supplier page.")) from error
        if page < 1 or page > 1000000:
            raise ValidationError(_("Choose a valid supplier page."))
        if page_size < 1 or page_size > MAX_SUPPLIER_PAGE_SIZE:
            raise ValidationError(
                _("Page size must be between %(limit)s and %(max)s suppliers.",
                  limit=1, max=MAX_SUPPLIER_PAGE_SIZE)
            )
        return page, page_size

    @api.model
    def _parse_catalog_filters(self, *, status, sort, direction):
        if status not in {"all", "in_stock", "low_stock", "out_of_stock"}:
            raise ValidationError(_("Choose a supported part stock status."))
        if sort not in {"name", "sku"}:
            raise ValidationError(_("Sort parts by name or SKU."))
        if direction not in {"asc", "desc"}:
            raise ValidationError(_("Choose ascending or descending order."))

    @api.model
    def _partner_ids_from_terms(self, SupplierInfo, domain):
        groups = SupplierInfo._read_group(
            domain, ["partner_id"], [], limit=MAX_SUPPLIERS + 1, order="partner_id"
        )
        return {partner.id for (partner,) in groups if partner}, len(groups) > MAX_SUPPLIERS

    @api.model
    def _expand_products(self, Product, company, lines):
        """Map supplier terms to visible active variants, expanding template terms."""
        by_partner_templates = defaultdict(set)
        variant_ids = set()
        for line in lines:
            if line.product_id:
                variant_ids.add(line.product_id.id)
            elif line.product_tmpl_id:
                by_partner_templates[line.partner_id.id].add(line.product_tmpl_id.id)
        product_domain = self._product_domain(company)
        variant_products = Product.search(
            product_domain + [("id", "in", sorted(variant_ids))],
            order="id",
            limit=MAX_SUPPLIER_PRODUCTS + 1,
        ) if variant_ids else Product.browse()
        template_ids = sorted(
            {template_id for ids in by_partner_templates.values() for template_id in ids}
        )
        template_products = Product.search(
            product_domain + [("product_tmpl_id", "in", template_ids)],
            order="id",
            limit=MAX_SUPPLIER_PRODUCTS + 1,
        ) if template_ids else Product.browse()
        limited = (
            len(variant_products) > MAX_SUPPLIER_PRODUCTS
            or len(template_products) > MAX_SUPPLIER_PRODUCTS
        )
        variant_products = variant_products[:MAX_SUPPLIER_PRODUCTS]
        template_products = template_products[:MAX_SUPPLIER_PRODUCTS]
        by_template = defaultdict(set)
        for product in template_products:
            by_template[product.product_tmpl_id.id].add(product.id)
        result = defaultdict(set)
        for line in lines:
            if line.product_id and line.product_id.id in variant_products.ids:
                result[line.partner_id.id].add(line.product_id.id)
            elif not line.product_id:
                result[line.partner_id.id].update(
                    by_template.get(line.product_tmpl_id.id, set())
                )
        for partner_id, ids in by_partner_templates.items():
            for template_id in ids:
                result[partner_id].update(by_template.get(template_id, set()))
        return result, limited

    @api.model
    def _risk_recommendations(self, Scoped, *, supplier_id=False, product_ids=False):
        """Reuse the existing risk service and disclose bounded, incomplete scans."""
        if product_ids is not False and not product_ids:
            return {
                "by_supplier": {},
                "by_product": {},
                "complete": True,
                "candidate_pairs": 0,
                "scanned_pairs": 0,
                "scan_limit": MAX_SUPPLIER_REORDER_SCAN,
            }
        Risk = Scoped.env["autostock.inventory.risk"]
        first = Risk.get_risk_data(
            supplier_id=supplier_id or False,
            product_ids=product_ids or False,
            risk_filter="recommendations",
            offset=0,
        )
        candidate_pairs = first["pagination"]["candidate_pair_count"]
        page_size = first["pagination"]["page_size"]
        scan_count = min(candidate_pairs, MAX_SUPPLIER_REORDER_SCAN)
        by_supplier = defaultdict(lambda: {"products": set(), "locations": []})
        by_product = defaultdict(list)
        complete = candidate_pairs <= MAX_SUPPLIER_REORDER_SCAN
        offset = 0
        while offset < scan_count:
            result = first if offset == 0 else Risk.get_risk_data(
                supplier_id=supplier_id or False,
                product_ids=product_ids or False,
                risk_filter="recommendations",
                offset=offset,
            )
            if (
                result["warehouse_scope_limited"]
                or result["supplier_lookup_limited"]
                or result["reordering_rule_lookup_limited"]
            ):
                complete = False
            for row in result["rows"]:
                if not row.get("reorder_needed") or not row.get("recommended_qty"):
                    continue
                position = {
                    "warehouse_id": row["warehouse_id"],
                    "warehouse": row["warehouse"],
                    "quantity": row["recommended_qty"],
                    "uom": row["uom"],
                }
                by_product[row["product_id"]].append(position)
                vendor = row.get("supplier") or {}
                if vendor.get("id"):
                    summary = by_supplier[vendor["id"]]
                    summary["products"].add(row["product_id"])
                    summary["locations"].append(
                        {"product_id": row["product_id"], **position}
                    )
            offset += page_size
        return {
            "by_supplier": by_supplier,
            "by_product": by_product,
            "complete": complete and offset >= candidate_pairs,
            "candidate_pairs": candidate_pairs,
            "scanned_pairs": min(offset, candidate_pairs),
            "scan_limit": MAX_SUPPLIER_REORDER_SCAN,
        }

    @api.model
    def _supplier_stats(self, Scoped, company, partners, *, risk_snapshot=False):
        SupplierInfo = Scoped.env["product.supplierinfo"].with_context(active_test=False)
        Product = Scoped.env["product.product"].with_context(active_test=False)
        Inventory = Scoped.env["autostock.inventory.catalog"]
        partner_ids = partners.ids
        today = fields.Date.today()
        active_domain = self._term_domain(company, today=today, partner_ids=partner_ids)
        configured_domain = self._term_domain(company, partner_ids=partner_ids)
        active_partner_ids, active_partner_scan_limited = self._partner_ids_from_terms(
            SupplierInfo, active_domain
        )
        configured_partner_ids, configured_partner_scan_limited = self._partner_ids_from_terms(
            SupplierInfo, configured_domain
        )
        active_lines = SupplierInfo.search(
            active_domain, order="partner_id, sequence, min_qty, id",
            limit=MAX_SUPPLIER_TERMS + 1,
        )
        configured_lines = SupplierInfo.search(
            configured_domain, order="partner_id, sequence, min_qty, id",
            limit=MAX_SUPPLIER_TERMS + 1,
        )
        active_limited = len(active_lines) > MAX_SUPPLIER_TERMS
        configured_limited = len(configured_lines) > MAX_SUPPLIER_TERMS
        active_lines = active_lines[:MAX_SUPPLIER_TERMS]
        configured_lines = configured_lines[:MAX_SUPPLIER_TERMS]
        active_products, active_products_limited = self._expand_products(
            Product, company, active_lines
        )
        configured_products, configured_products_limited = self._expand_products(
            Product, company, configured_lines
        )
        products_limited = active_products_limited or configured_products_limited
        product_ids = sorted(
            {product_id for ids in active_products.values() for product_id in ids}
        )
        quantities_available = len(product_ids) <= MAX_SUPPLIER_PRODUCTS
        products = Product.browse(product_ids[:MAX_SUPPLIER_PRODUCTS])
        quantities = Inventory._quantity_values(Product, products, company) if quantities_available else {}
        product_records = {product.id: product for product in products}

        active_lines_by_partner = defaultdict(list)
        active_terms_by_product = defaultdict(list)
        for line in active_lines:
            active_lines_by_partner[line.partner_id.id].append(line)
            if line.product_id:
                active_terms_by_product[line.product_id.id].append(line)
            else:
                for product_id in active_products.get(line.partner_id.id, set()):
                    product = product_records.get(product_id)
                    if product and product.product_tmpl_id == line.product_tmpl_id:
                        active_terms_by_product[product_id].append(line)

        reorder_data = risk_snapshot or {"by_supplier": {}, "complete": False}
        rows = []
        for partner in partners:
            ids = active_products.get(partner.id, set())
            tracked = {product_id for product_id in ids if product_records.get(product_id) and product_records[product_id].autostock_enabled}
            low_or_out = set()
            if quantities_available:
                for product_id in ids:
                    product = product_records.get(product_id)
                    values = quantities.get(product_id, {})
                    if product and Inventory._stock_status(product, values.get("qty_available", 0.0)) != "in_stock":
                        low_or_out.add(product_id)
            lines = active_lines_by_partner.get(partner.id, [])
            lead_days = [max(0, int(line.delay or 0)) for line in lines]
            reorder = reorder_data["by_supplier"].get(partner.id, {})
            reorder_parts = len(reorder.get("products", set())) if reorder_data["complete"] else False
            reorder_locations = len(reorder.get("locations", [])) if reorder_data["complete"] else False
            active_terms_known = not active_partner_scan_limited
            configured_terms_known = not configured_partner_scan_limited
            has_active_terms = partner.id in active_partner_ids
            has_configured_terms = partner.id in configured_partner_ids
            supplier_products_complete = (
                not active_limited and not active_products_limited
            )
            rows.append({
                "id": partner.id,
                "name": partner.display_name,
                "vendor_code": partner.ref or False,
                "company_name": (partner.parent_id.display_name or False) if partner.parent_id else False,
                "email": partner.email or False,
                "phone": partner.phone or False,
                "city": partner.city or False,
                "country": partner.country_id.name or False,
                "partner_company": partner.company_id.display_name or False,
                "active": bool(partner.active),
                "active_parts": len(ids) if supplier_products_complete else False,
                "tracked_parts": len(tracked) if supplier_products_complete else False,
                "low_or_out_parts": len(low_or_out) if quantities_available else False,
                "reorder_parts": reorder_parts,
                "reorder_locations": reorder_locations,
                "active_terms": len(lines) if not active_limited else False,
                "has_active_terms": has_active_terms,
                "active_terms_status": "has_terms" if has_active_terms else "no_terms" if active_terms_known else "unknown",
                "has_configured_terms": has_configured_terms,
                "configured_terms_status": "has_terms" if has_configured_terms else "no_terms" if configured_terms_known else "unknown",
                "lead_time_min_days": min(lead_days) if lead_days and not active_limited else False,
                "lead_time_max_days": max(lead_days) if lead_days and not active_limited else False,
                "attention": bool(reorder_parts) if reorder_parts is not False else False,
            })
        return {
            "rows": rows,
            "active_lines": active_lines,
            "active_lines_by_product": active_terms_by_product,
            "active_products_by_partner": active_products,
            "configured_products_by_partner": configured_products,
            "active_terms_complete": not active_limited and not active_products_limited,
            "configured_terms_complete": not configured_limited and not configured_products_limited,
            "active_partner_scan_complete": not active_partner_scan_limited,
            "configured_partner_scan_complete": not configured_partner_scan_limited,
            "stock_complete": quantities_available,
            "active_product_ids": set(product_ids),
            "reorder": reorder_data,
        }

    @api.model
    def _supplier_partners(self, Scoped, company, query=""):
        Partner = Scoped.env["res.partner"].with_context(active_test=False)
        SupplierInfo = Scoped.env["product.supplierinfo"].with_context(active_test=False)
        all_term_partner_ids, all_term_partners_limited = self._partner_ids_from_terms(
            SupplierInfo, self._term_domain(company)
        )
        configured_domain = self._term_domain(company)
        if query:
            configured_domain += [
                "|", ("partner_id.name", "ilike", query),
                ("partner_id.ref", "ilike", query),
            ]
        term_partner_ids, term_partner_limited = self._partner_ids_from_terms(
            SupplierInfo, configured_domain
        )

        def partner_domain(term_partner_ids):
            return [
                ("active", "=", True),
                ("company_id", "in", [False, company.id]),
                "|",
                ("id", "in", sorted(term_partner_ids) or [0]),
                "&", ("company_id", "=", company.id), ("supplier_rank", ">", 0),
            ]

        full_domain = partner_domain(all_term_partner_ids)
        active_supplier_count = (
            False if all_term_partners_limited else Partner.search_count(full_domain)
        )
        domain = partner_domain(term_partner_ids)
        if query:
            domain += ["|", ("name", "ilike", query), ("ref", "ilike", query)]
        partners = Partner.search(domain, order="name, id", limit=MAX_SUPPLIERS + 1)
        return partners, term_partner_limited or len(partners) > MAX_SUPPLIERS, active_supplier_count

    @api.model
    def get_supplier_page(
        self, *, query="", attention="all", terms="all", sort="name",
        direction="asc", page=1, page_size=DEFAULT_SUPPLIER_PAGE_SIZE,
    ):
        company = self.env.company
        Scoped = self._company_env(company)
        self._require_supplier_access(Scoped)
        query = (query or "").strip()[:80]
        attention = (attention or "all").strip()
        terms = (terms or "all").strip()
        sort = (sort or "name").strip()
        direction = (direction or "asc").strip()
        if attention not in {"all", "reorder"}:
            raise ValidationError(_("Choose a supported supplier attention filter."))
        if terms not in {"all", "active", "none"}:
            raise ValidationError(_("Choose whether suppliers have active part terms."))
        if sort not in {"name", "reorder", "parts", "lead_time"}:
            raise ValidationError(_("Choose a supported supplier sort order."))
        if direction not in {"asc", "desc"}:
            raise ValidationError(_("Choose ascending or descending sort order."))
        page, page_size = self._parse_page(page, page_size)
        partners, partner_scan_limited, active_supplier_count = self._supplier_partners(Scoped, company, query)
        if partner_scan_limited:
            raise ValidationError(_(
                "The supplier list exceeds the safe summary limit. Search by supplier name or vendor code to narrow it."
            ))
        risk = self._risk_recommendations(Scoped)
        stats = self._supplier_stats(Scoped, company, partners, risk_snapshot=risk)
        rows = stats["rows"]
        if terms == "active":
            if not stats["active_partner_scan_complete"]:
                raise ValidationError(_("Active supplier terms could not be checked completely. Search by supplier name to narrow the list."))
            rows = [row for row in rows if row["has_active_terms"]]
        elif terms == "none":
            if not stats["active_partner_scan_complete"]:
                raise ValidationError(_("Active supplier terms could not be checked completely. Search by supplier name to narrow the list."))
            rows = [row for row in rows if not row["has_active_terms"]]
        if attention == "reorder":
            if not risk["complete"]:
                raise ValidationError(_(
                    "Reorder links could not be checked across the full catalog. Clear the attention filter to review the supplier list."
                ))
            rows = [row for row in rows if row["reorder_parts"]]

        reverse = direction == "desc"
        sort_fields = {
            "name": lambda row: (row["name"].casefold(),),
            "reorder": lambda row: (row["reorder_parts"] is False, row["reorder_parts"] or 0, row["name"].casefold()),
            "parts": lambda row: (row["active_parts"] is False, row["active_parts"] or 0, row["name"].casefold()),
            "lead_time": lambda row: (row["lead_time_min_days"] is False, row["lead_time_min_days"] or 0, row["name"].casefold()),
        }
        rows.sort(key=sort_fields[sort], reverse=reverse)
        total = len(rows)
        total_pages = (total + page_size - 1) // page_size
        page = min(page, total_pages) if total_pages else 1
        start = (page - 1) * page_size
        rows = rows[start:start + page_size]

        Product = Scoped.env["product.product"].with_context(active_test=False)
        catalog_count = Product.search_count(self._product_domain(company))
        configured_lines = Scoped.env["product.supplierinfo"].with_context(active_test=False).search(
            self._term_domain(company), order="partner_id, sequence, min_qty, id",
            limit=MAX_SUPPLIER_TERMS + 1,
        )
        configured_limited = len(configured_lines) > MAX_SUPPLIER_TERMS
        configured_lines = configured_lines[:MAX_SUPPLIER_TERMS]
        configured_products, configured_products_limited = self._expand_products(
            Product, company, configured_lines
        )
        linked_product_ids = {item for ids in configured_products.values() for item in ids}
        terms_complete = (
            not configured_limited and not configured_products_limited
            and stats["configured_terms_complete"]
        )
        reorder_suppliers = len({supplier_id for supplier_id, row in risk["by_supplier"].items() if row["products"]})
        summary = {
            "active_suppliers": active_supplier_count,
            "parts_with_supplier": len(linked_product_ids) if terms_complete else False,
            "parts_missing_supplier": max(0, catalog_count - len(linked_product_ids)) if terms_complete else False,
            "suppliers_with_reorder_needs": reorder_suppliers if risk["complete"] else False,
        }
        notes = []
        if active_supplier_count is False:
            notes.append(_("The active supplier total is unavailable because its safe supplier-term scan limit was reached."))
        if not terms_complete:
            notes.append(_("Supplier-term coverage exceeded its safe scan limit; part totals are unavailable."))
        if not stats["stock_complete"]:
            notes.append(_("Stock attention counts are unavailable because the linked product set is too large to scan safely."))
        if not risk["complete"]:
            notes.append(_("Reorder links are incomplete because the company stock scan reached its safety limit."))
        return {
            "as_of": fields.Datetime.to_string(fields.Datetime.now()),
            "summary": summary,
            "filters": {"query": query, "attention": attention, "terms": terms, "sort": sort, "direction": direction},
            "suppliers": rows,
            "pagination": {
                "page": page, "page_size": page_size, "total_count": total,
                "total_pages": total_pages, "has_previous": page > 1,
                "has_next": page < total_pages,
            },
            "coverage": {
                "supplier_terms_complete": terms_complete and stats["active_terms_complete"],
                "product_catalog_complete": catalog_count <= MAX_SUPPLIER_PRODUCTS,
                "stock_complete": stats["stock_complete"],
                "reorder_complete": risk["complete"],
                "supplier_limit": MAX_SUPPLIERS,
                "term_scan_limit": MAX_SUPPLIER_TERMS,
                "product_scan_limit": MAX_SUPPLIER_PRODUCTS,
                "reorder_scan_limit": MAX_SUPPLIER_REORDER_SCAN,
                "note": " ".join(notes) if notes else False,
            },
            "read_only": True,
        }

    @api.model
    def _get_supplier(self, Scoped, company, supplier_id):
        try:
            supplier_id = int(supplier_id)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid supplier.")) from error
        if supplier_id <= 0:
            raise ValidationError(_("Choose a valid supplier."))
        Partner = Scoped.env["res.partner"].with_context(active_test=False)
        SupplierInfo = Scoped.env["product.supplierinfo"].with_context(active_test=False)
        has_terms = SupplierInfo.search_count(
            self._term_domain(company) + [("partner_id", "=", supplier_id)]
        ) > 0
        partner = Partner.search([
            ("id", "=", supplier_id), ("active", "=", True),
            ("company_id", "in", [False, company.id]),
        ], limit=1)
        is_company_supplier = bool(
            partner and partner.company_id == company and partner.supplier_rank > 0
        )
        if not partner or not (has_terms or is_company_supplier):
            raise AccessError(_("That supplier is not available in the selected company."))
        return partner

    @api.model
    def _purchase_activity(self, Scoped, company, partner):
        if "purchase.order" not in Scoped.env.registry.models:
            return {
                "available": False,
                "note": _("Purchase order history is not available in this setup. Supplier terms and stock details are still available."),
                "items": [],
            }
        PurchaseOrder = Scoped.env["purchase.order"]
        if not self._can_read(PurchaseOrder):
            return {
                "available": False,
                "note": _("Purchase order history is not available for your Odoo role. Supplier terms and stock details are still available."),
                "items": [],
            }
        if "purchase.order.line" in Scoped.env.registry.models and not self._can_read(Scoped.env["purchase.order.line"]):
            return {
                "available": False,
                "note": _("Purchase order history is not available for your Odoo role. Supplier terms and stock details are still available."),
                "items": [],
            }
        commercial_partner = partner.commercial_partner_id
        orders = PurchaseOrder.search(
            [
                ("company_id", "=", company.id),
                ("partner_id", "child_of", commercial_partner.id),
                ("state", "!=", "cancel"),
            ],
            order="date_order desc, id desc",
            limit=8,
        )
        state_labels = {
            "draft": _("Draft purchase order"), "sent": _("Purchase order sent"),
            "to approve": _("Purchase order awaiting approval"),
            "purchase": _("Purchase order confirmed"), "done": _("Purchase order closed"),
        }
        items = [{
            "id": order.id,
            "kind": "purchase_order",
            "label": state_labels.get(order.state, _("Purchase order")),
            "reference": order.name or False,
            "date": fields.Datetime.to_string(order.date_order) if order.date_order else False,
        } for order in orders]

        Picking = Scoped.env["stock.picking"]
        if self._can_read(Picking):
            pickings = Picking.search(
                [
                    ("company_id", "=", company.id),
                    ("partner_id", "child_of", commercial_partner.id),
                    ("picking_type_id.code", "=", "incoming"),
                    ("state", "in", ["done", "assigned", "confirmed", "waiting", "partially_available"]),
                ],
                order="date_done desc, scheduled_date desc, id desc",
                limit=8,
            )
            for picking in pickings:
                is_done = picking.state == "done"
                activity_date = picking.date_done if is_done else picking.scheduled_date
                items.append({
                    "id": 100000000 + picking.id,
                    "kind": "receipt",
                    "label": _("Stock received") if is_done else _("Incoming stock expected"),
                    "reference": picking.name or picking.origin or False,
                    "date": fields.Datetime.to_string(activity_date) if activity_date else False,
                })
        items.sort(key=lambda item: item["date"] or "", reverse=True)
        return {
            "available": True,
            "note": _("Recent purchase orders and incoming receipts visible to your role."),
            "items": items[:10],
        }

    @api.model
    def get_supplier_detail(self, supplier_id):
        company = self.env.company
        Scoped = self._company_env(company)
        self._require_supplier_access(Scoped)
        partner = self._get_supplier(Scoped, company, supplier_id)
        risk = self._risk_recommendations(Scoped, supplier_id=partner.id)
        stats = self._supplier_stats(Scoped, company, partner, risk_snapshot=risk)
        summary = stats["rows"][0]
        activity = self._purchase_activity(Scoped, company, partner)
        return {
            "supplier": {
                "id": partner.id,
                "name": partner.display_name,
                "vendor_code": partner.ref or False,
                "company_name": (partner.parent_id.display_name or False) if partner.parent_id else False,
                "email": partner.email or False,
                "phone": partner.phone or False,
                "city": partner.city or False,
                "country": partner.country_id.name or False,
                "partner_company": partner.company_id.display_name or False,
            },
            "summary": summary,
            "purchase_history": activity,
            "coverage": {
                "supplier_terms_complete": stats["active_terms_complete"],
                "stock_complete": stats["stock_complete"],
                "reorder_complete": risk["complete"],
                "reorder_scanned": risk["scanned_pairs"],
                "reorder_candidates": risk["candidate_pairs"],
            },
            "as_of": fields.Datetime.to_string(fields.Datetime.now()),
            "read_only": True,
        }

    @api.model
    def get_supplier_parts(
        self, supplier_id, *, query="", status="all", sort="name", direction="asc",
        page=1, page_size=25,
    ):
        company = self.env.company
        Scoped = self._company_env(company)
        self._require_supplier_access(Scoped)
        partner = self._get_supplier(Scoped, company, supplier_id)
        query = (query or "").strip()[:80]
        status = (status or "all").strip()
        sort = (sort or "name").strip()
        direction = (direction or "asc").strip()
        self._parse_catalog_filters(status=status, sort=sort, direction=direction)
        page, page_size = self._parse_page(page, page_size)
        Inventory = Scoped.env["autostock.inventory.catalog"]
        result = Inventory.get_inventory_page(
            query=query, status=status, supplier_id=partner.id, warehouse_id=None,
            sort=sort, direction=direction, page=page, page_size=page_size,
        )
        items = result["items"]
        Product = Scoped.env["product.product"].with_context(active_test=False)
        products = Product.browse([row["product_id"] for row in items])
        SupplierInfo = Scoped.env["product.supplierinfo"].with_context(active_test=False)
        lines = SupplierInfo.search(
            self._term_domain(company, partner_ids=[partner.id])
            + [("product_tmpl_id", "in", products.mapped("product_tmpl_id").ids)],
            order="sequence, min_qty, id",
            limit=MAX_SUPPLIER_TERMS + 1,
        )
        terms_limited = len(lines) > MAX_SUPPLIER_TERMS
        lines = lines[:MAX_SUPPLIER_TERMS]
        applicable = defaultdict(list)
        today = fields.Date.today()
        for line in lines:
            if line.product_id:
                applicable[line.product_id.id].append(line)
            else:
                for product in products.filtered(lambda item: item.product_tmpl_id == line.product_tmpl_id):
                    applicable[product.id].append(line)
        risk = self._risk_recommendations(
            Scoped, supplier_id=partner.id,
            product_ids=[row["product_id"] for row in items],
        )
        for row in items:
            rows = applicable.get(row["product_id"], [])
            active_rows = [line for line in rows if (not line.date_start or line.date_start <= today) and (not line.date_end or line.date_end >= today)]
            delays = [max(0, int(line.delay or 0)) for line in active_rows]
            row["supplier_terms_count"] = len(rows)
            row["lead_time_min_days"] = min(delays) if delays else False
            row["lead_time_max_days"] = max(delays) if delays else False
            row["reorder_locations"] = risk["by_product"].get(row["product_id"], [])
            row["reorder_parts"] = bool(row["reorder_locations"])
        result["items"] = items
        result["filters"]["query"] = query
        result["filters"]["status"] = status
        result["filters"]["sort"] = sort
        result["filters"]["direction"] = direction
        result["coverage"].update({
            "supplier_terms_complete": not terms_limited,
            "reorder_complete": risk["complete"],
        })
        return result

    @api.model
    def get_supplier_terms(self, supplier_id, product_id):
        company = self.env.company
        Scoped = self._company_env(company)
        self._require_supplier_access(Scoped)
        partner = self._get_supplier(Scoped, company, supplier_id)
        try:
            product_id = int(product_id)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid part.")) from error
        Product = Scoped.env["product.product"].with_context(active_test=False)
        product = Product.search(
            self._product_domain(company) + [("id", "=", product_id)], limit=1
        )
        if not product:
            raise AccessError(_("That part is not available in the selected company."))
        SupplierInfo = Scoped.env["product.supplierinfo"].with_context(active_test=False)
        lines = SupplierInfo.search(
            self._term_domain(company, partner_ids=[partner.id])
            + [("product_tmpl_id", "=", product.product_tmpl_id.id)],
            order="sequence, min_qty, id",
            limit=MAX_SUPPLIER_TERM_DETAIL + 1,
        )
        lines = lines.filtered(lambda line: not line.product_id or line.product_id == product)
        if not lines:
            raise AccessError(_("No vendor terms for this part are available for the selected company."))
        limited = len(lines) > MAX_SUPPLIER_TERM_DETAIL
        today = fields.Date.today()
        terms = []
        for line in lines[:MAX_SUPPLIER_TERM_DETAIL]:
            currency = line.currency_id
            vendor_uom = line.product_uom_id if "product_uom_id" in line._fields and line.product_uom_id else product.uom_id
            start_date = line.date_start if "date_start" in line._fields else False
            end_date = line.date_end if "date_end" in line._fields else False
            terms.append({
                "id": line.id,
                "sequence": line.sequence,
                "vendor_product_name": line.product_name if "product_name" in line._fields and line.product_name else False,
                "vendor_product_code": line.product_code if "product_code" in line._fields and line.product_code else False,
                "price": line.price if line.price and line.price > 0 else False,
                "price_available": bool(line.price and line.price > 0),
                "currency": {"code": currency.name, "symbol": currency.symbol, "decimal_places": currency.decimal_places},
                "price_break_min_qty": line.min_qty,
                "price_break_uom": vendor_uom.display_name,
                "minimum_order_qty": line.autostock_min_order_qty or 0.0,
                "minimum_order_uom": vendor_uom.display_name,
                "lead_time_days": max(0, int(line.delay or 0)),
                "company_id": line.company_id.id if line.company_id else False,
                "company_name": line.company_id.display_name if line.company_id else False,
                "valid_from": fields.Date.to_string(start_date) if start_date else False,
                "valid_until": fields.Date.to_string(end_date) if end_date else False,
                "active_today": bool(partner.active and (not start_date or start_date <= today) and (not end_date or end_date >= today)),
                "variant_specific": bool(line.product_id),
            })
        return {
            "product": {"id": product.id, "name": product.product_tmpl_id.name, "sku": product.default_code or "—"},
            "supplier": {"id": partner.id, "name": partner.display_name},
            "terms": terms,
            "terms_truncated": limited,
            "read_only": True,
        }

    @api.model
    def get_supplier_gaps(self, *, query="", status="all", sort="name", direction="asc", page=1, page_size=25):
        company = self.env.company
        Scoped = self._company_env(company)
        self._require_supplier_access(Scoped)
        query = (query or "").strip()[:80]
        status = (status or "all").strip()
        sort = (sort or "name").strip()
        direction = (direction or "asc").strip()
        self._parse_catalog_filters(status=status, sort=sort, direction=direction)
        page, page_size = self._parse_page(page, page_size)
        Inventory = Scoped.env["autostock.inventory.catalog"]
        result = Inventory.get_inventory_page(
            query=query, status=status, sort=sort, direction=direction,
            page=page, page_size=page_size, missing_supplier=True,
        )
        risk = self._risk_recommendations(
            Scoped, product_ids=[row["product_id"] for row in result["items"]]
        )
        for row in result["items"]:
            suggestions = risk["by_product"].get(row["product_id"], [])
            row["reorder_locations"] = suggestions
            row["reorder_parts"] = bool(suggestions)
            row["supplier_terms_count"] = 0
            row["lead_time_min_days"] = False
            row["lead_time_max_days"] = False
        result["filters"]["query"] = query
        result["coverage"].update({
            "supplier_terms_complete": True,
            "reorder_complete": risk["complete"],
        })
        return result
