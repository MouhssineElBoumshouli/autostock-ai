import secrets
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("post_install", "-at_install")
class TestAutoStockSupplierApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.test_password = secrets.token_urlsafe(24)
        admin = self.env.ref("base.user_admin")
        admin.write({"password": self.test_password})
        self.authenticate(admin.login, self.test_password)

    def _get_json(self, path, expected_status=200):
        response = self.url_open(path, allow_redirects=False)
        self.assertEqual(response.status_code, expected_status, response.text[:500])
        self.assertIn("application/json", response.headers.get("Content-Type", ""))
        return response.json()

    def _warehouse(self, company):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse:
            warehouse = self.env["stock.warehouse"].create(
                {
                    "name": f"Gate 6 {company.name} Warehouse",
                    "code": f"G6{company.id:03d}"[-5:],
                    "company_id": company.id,
                }
            )
        return warehouse

    def _part(self, name, *, company=False, sku=False, tracked=False):
        template = self.env["product.template"].create(
            {
                "name": name,
                "default_code": sku or name.upper().replace(" ", "-")[:40],
                "company_id": company.id if company else False,
                "is_storable": True,
                "autostock_enabled": tracked,
            }
        )
        return template, template.product_variant_id

    def _supplier(self, name, *, company=False):
        return self.env["res.partner"].create(
            {
                "name": name,
                "company_type": "company",
                "company_id": company.id if company else False,
                "supplier_rank": 1,
            }
        )

    def _vendor_term(
        self, supplier, template, *, company, currency, sequence, min_qty, price,
        moq, delay, product=False, date_start=False,
    ):
        values = {
            "partner_id": supplier.id,
            "product_tmpl_id": template.id,
            "product_id": product.id if product else False,
            "company_id": company.id if company else False,
            "currency_id": currency.id,
            "sequence": sequence,
            "min_qty": min_qty,
            "price": price,
            "autostock_min_order_qty": moq,
            "delay": delay,
            "product_name": f"Vendor part {sequence}",
            "product_code": f"VENDOR-{sequence}",
        }
        if date_start:
            values["date_start"] = date_start
        return self.env["product.supplierinfo"].create(values)

    def test_supplier_page_search_and_detail_keep_live_purchase_history_optional(self):
        company = self.env.company
        mad = company.currency_id
        usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        self.assertTrue(usd, "USD currency should be available for testing term currency preservation")
        template, product = self._part(
            "Gate6 Alternator Assembly", company=company, sku="G6-ALT-1"
        )
        supplier = self._supplier("Gate6 Northline Auto Supply")
        first = self._vendor_term(
            supplier, template, company=company, currency=mad, sequence=1,
            min_qty=1, price=1450, moq=4, delay=8,
        )
        second = self._vendor_term(
            supplier, template, company=False, currency=usd, sequence=2,
            min_qty=10, price=129, moq=4, delay=14, product=product,
        )
        third = self._vendor_term(
            supplier, template, company=company, currency=mad, sequence=3,
            min_qty=25, price=111, moq=4, delay=14, product=product,
            date_start=fields.Date.today() + timedelta(days=10),
        )

        page = self._get_json(
            "/autostock/api/v1/suppliers?q=Gate6%20Northline&page_size=12"
        )
        self.assertEqual(page["pagination"]["total_count"], 1)
        self.assertEqual(page["suppliers"][0]["id"], supplier.id)
        self.assertEqual(page["suppliers"][0]["active_parts"], 1)
        self.assertEqual(page["suppliers"][0]["lead_time_min_days"], 8)
        self.assertEqual(page["suppliers"][0]["lead_time_max_days"], 14)
        self.assertGreaterEqual(page["summary"]["parts_with_supplier"], 1)
        self.assertTrue(page["read_only"])

        terms = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier.id}/parts/{product.id}/terms"
        )
        no_matching_parts = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier.id}/parts?q=No%20matching%20part"
        )
        self.assertEqual([row["id"] for row in terms["terms"]], [first.id, second.id, third.id])
        self.assertEqual([row["currency"]["code"] for row in terms["terms"]], [mad.name, usd.name, mad.name])
        self.assertEqual([row["price_break_min_qty"] for row in terms["terms"]], [1, 10, 25])
        self.assertEqual([row["minimum_order_qty"] for row in terms["terms"]], [4, 4, 4])
        self.assertEqual([row["active_today"] for row in terms["terms"]], [True, True, False])
        self.assertEqual(terms["terms"][0]["vendor_product_code"], "VENDOR-1")
        self.assertEqual(no_matching_parts["pagination"]["total_count"], 0)
        self.assertTrue(no_matching_parts["coverage"]["reorder_complete"])

        detail = self._get_json(f"/autostock/api/v1/suppliers/{supplier.id}")
        self.assertEqual(detail["supplier"]["id"], supplier.id)
        self.assertIn("available", detail["purchase_history"])
        if "purchase.order" not in self.env.registry.models:
            self.assertFalse(detail["purchase_history"]["available"])
            self.assertIn("not available", detail["purchase_history"]["note"].lower())

    def test_supplier_pages_cover_500_suppliers_and_1000_terms(self):
        company = self.env.company
        template, _product = self._part("Gate6 Large Terms Part", company=company)
        suppliers = self.env["res.partner"].create(
            [
                {
                    "name": f"Gate6 Bulk Supplier {index:04d}",
                    "company_type": "company",
                    "supplier_rank": 1,
                }
                for index in range(500)
            ]
        )
        currencies = self.env["res.currency"].search(
            [("name", "in", [company.currency_id.name, "USD"])], order="name"
        )
        self.assertTrue(currencies)
        terms = []
        for index, supplier in enumerate(suppliers):
            for tier, minimum in enumerate((1, 10)):
                terms.append(
                    {
                        "partner_id": supplier.id,
                        "product_tmpl_id": template.id,
                        "company_id": company.id if index % 2 == 0 else False,
                        "currency_id": currencies[(index + tier) % len(currencies)].id,
                        "sequence": tier + 1,
                        "min_qty": minimum,
                        "price": 20 + index + tier,
                        "autostock_min_order_qty": 2,
                        "delay": 5 + tier,
                    }
                )
        self.env["product.supplierinfo"].create(terms)

        first_page = self._get_json("/autostock/api/v1/suppliers?page=1&page_size=50")
        tenth_page = self._get_json("/autostock/api/v1/suppliers?page=10&page_size=50")
        search_result = self._get_json(
            "/autostock/api/v1/suppliers?q=Gate6%20Bulk%20Supplier%200499&page_size=12"
        )
        self.assertEqual(first_page["pagination"]["total_count"], 500)
        self.assertEqual(first_page["summary"]["active_suppliers"], 500)
        self.assertEqual(len(first_page["suppliers"]), 50)
        self.assertEqual(tenth_page["pagination"]["page"], 10)
        self.assertEqual(len(tenth_page["suppliers"]), 50)
        self.assertEqual(search_result["pagination"]["total_count"], 1)
        self.assertEqual(search_result["suppliers"][0]["name"], "Gate6 Bulk Supplier 0499")
        self.assertEqual(search_result["suppliers"][0]["active_terms"], 2)
        self.assertEqual(search_result["summary"]["active_suppliers"], 500)

    def test_supplier_reorder_attention_reuses_current_odoo_recommendations(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        template, product = self._part(
            "Gate6 Restock Rotor", company=company, sku="G6-RESTOCK", tracked=True
        )
        supplier = self._supplier("Gate6 Restock Supplier")
        self._vendor_term(
            supplier, template, company=company, currency=company.currency_id,
            sequence=1, min_qty=1, price=70, moq=1, delay=5,
        )
        self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": product.id,
                "location_id": warehouse.lot_stock_id.id,
                "warehouse_id": warehouse.id,
                "company_id": company.id,
                "product_min_qty": 4,
                "product_max_qty": 10,
            }
        )

        attention = self._get_json(
            "/autostock/api/v1/suppliers?attention=reorder&q=Gate6%20Restock"
        )
        detail = self._get_json(f"/autostock/api/v1/suppliers/{supplier.id}")
        self.assertEqual(attention["pagination"]["total_count"], 1)
        self.assertEqual(attention["suppliers"][0]["id"], supplier.id)
        self.assertGreater(attention["suppliers"][0]["reorder_parts"], 0)
        self.assertGreater(detail["summary"]["reorder_locations"], 0)
        self.assertTrue(detail["coverage"]["reorder_complete"])

    def test_supplier_apis_preserve_company_scope_for_shared_and_company_parts(self):
        company_a = self.env.company
        company_b = self.env["res.company"].create({"name": "Gate6 Company B"})
        admin = self.env.ref("base.user_admin")
        admin.write({"company_ids": [Command.link(company_b.id)]})
        warehouse_a = self._warehouse(company_a)
        warehouse_b = self._warehouse(company_b)
        shared_template, shared_product = self._part("Gate6 Shared Rotor", sku="G6-SHARED")
        _company_b_template, company_b_product = self._part(
            "Gate6 B Only Rotor", company=company_b, sku="G6-B-ONLY"
        )
        _company_b_unassigned_template, company_b_unassigned = self._part(
            "Gate6 B Unassigned Rotor", company=company_b, sku="G6-B-UNASSIGNED"
        )
        _company_a_unassigned_template, company_a_unassigned = self._part(
            "Gate6 A Unassigned Rotor", company=company_a, sku="G6-A-UNASSIGNED"
        )
        supplier_a = self._supplier("Gate6 Supplier A")
        supplier_b = self._supplier("Gate6 Supplier B")
        mad = company_a.currency_id
        self._vendor_term(
            supplier_a, shared_template, company=company_a, currency=mad,
            sequence=1, min_qty=1, price=40, moq=1, delay=6,
        )
        self._vendor_term(
            supplier_b, shared_template, company=company_b, currency=mad,
            sequence=2, min_qty=1, price=33, moq=2, delay=12,
        )
        self._vendor_term(
            supplier_b, _company_b_template, company=company_b, currency=mad,
            sequence=3, min_qty=1, price=22, moq=1, delay=15,
        )
        self.env["stock.quant"].with_company(company_a)._update_available_quantity(
            shared_product, warehouse_a.lot_stock_id, 4
        )
        self.env["stock.quant"].with_company(company_b)._update_available_quantity(
            shared_product, warehouse_b.lot_stock_id, 19
        )

        suppliers_a = self._get_json(
            f"/autostock/api/v1/suppliers?q=Gate6%20Supplier%20A&company_id={company_a.id}"
        )
        suppliers_a_other = self._get_json(
            f"/autostock/api/v1/suppliers?q=Gate6%20Supplier%20B&company_id={company_a.id}"
        )
        supplier_b_a_detail = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_b.id}?company_id={company_a.id}",
            expected_status=403,
        )
        supplier_b_data = self._get_json(
            f"/autostock/api/v1/suppliers?q=Gate6%20Supplier%20B&company_id={company_b.id}"
        )
        parts_a = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_a.id}/parts?q=G6-SHARED&company_id={company_a.id}"
        )
        parts_b = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_b.id}/parts?q=G6-SHARED&company_id={company_b.id}"
        )
        b_only_parts_a = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_a.id}/parts?q=G6-B-ONLY&company_id={company_a.id}"
        )
        b_only_parts_b = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_b.id}/parts?q=G6-B-ONLY&company_id={company_b.id}"
        )
        b_only_in_a = self._get_json(
            f"/autostock/api/v1/supplier-gaps?q=G6-B-ONLY&company_id={company_a.id}"
        )
        b_only_in_b = self._get_json(
            f"/autostock/api/v1/supplier-gaps?q=G6-B-ONLY&company_id={company_b.id}"
        )
        b_unassigned_in_a = self._get_json(
            f"/autostock/api/v1/supplier-gaps?q=G6-B-UNASSIGNED&company_id={company_a.id}"
        )
        b_unassigned_in_b = self._get_json(
            f"/autostock/api/v1/supplier-gaps?q=G6-B-UNASSIGNED&company_id={company_b.id}"
        )
        a_unassigned_in_a = self._get_json(
            f"/autostock/api/v1/supplier-gaps?q=G6-A-UNASSIGNED&company_id={company_a.id}"
        )

        self.assertEqual([row["id"] for row in suppliers_a["suppliers"]], [supplier_a.id])
        self.assertEqual(suppliers_a_other["pagination"]["total_count"], 0)
        self.assertEqual(supplier_b_a_detail["error"]["code"], "forbidden")
        self.assertEqual([row["id"] for row in supplier_b_data["suppliers"]], [supplier_b.id])
        self.assertEqual(parts_a["items"][0]["on_hand"], 4)
        self.assertEqual(parts_b["items"][0]["on_hand"], 19)
        self.assertEqual(b_only_parts_a["pagination"]["total_count"], 0)
        self.assertEqual(b_only_parts_b["pagination"]["total_count"], 1)
        self.assertEqual(b_only_parts_b["items"][0]["product_id"], company_b_product.id)
        self.assertEqual(b_only_in_a["pagination"]["total_count"], 0)
        self.assertEqual(b_only_in_b["pagination"]["total_count"], 0)
        self.assertEqual(b_unassigned_in_a["pagination"]["total_count"], 0)
        self.assertEqual(b_unassigned_in_b["pagination"]["total_count"], 1)
        self.assertEqual(b_unassigned_in_b["items"][0]["product_id"], company_b_unassigned.id)
        self.assertEqual(a_unassigned_in_a["pagination"]["total_count"], 1)
        self.assertEqual(a_unassigned_in_a["items"][0]["product_id"], company_a_unassigned.id)
        terms_a = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_a.id}/parts/{shared_product.id}/terms?company_id={company_a.id}"
        )
        terms_b = self._get_json(
            f"/autostock/api/v1/suppliers/{supplier_b.id}/parts/{shared_product.id}/terms?company_id={company_b.id}"
        )
        self.assertEqual([item["company_id"] for item in terms_a["terms"]], [company_a.id])
        self.assertEqual([item["company_id"] for item in terms_b["terms"]], [company_b.id])

    def test_supplier_api_requires_inventory_access(self):
        user = self.env["res.users"].create(
            {
                "name": "Gate6 Supplier Read-only User",
                "login": "gate6-supplier-no-inventory",
                "email": "gate6-supplier-no-inventory@example.invalid",
                "company_id": self.env.company.id,
                "company_ids": [Command.set([self.env.company.id])],
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        user.write({"password": self.test_password})
        self.authenticate(user.login, self.test_password)
        response = self._get_json("/autostock/api/v1/suppliers", expected_status=403)
        self.assertEqual(response["error"]["code"], "forbidden")
        self.assertIn("inventory access", response["error"]["message"].lower())

    def test_supplier_detail_remains_available_without_purchase_history_access(self):
        company = self.env.company
        template, _product = self._part("Gate6 Supplier Without Purchase Access", company=company)
        supplier = self._supplier("Gate6 Purchase-Restricted Supplier")
        self._vendor_term(
            supplier, template, company=company, currency=company.currency_id,
            sequence=1, min_qty=1, price=24, moq=1, delay=9,
        )
        user = self.env["res.users"].create(
            {
                "name": "Gate6 Inventory User Without Purchase Rights",
                "login": "gate6-supplier-no-purchase",
                "email": "gate6-supplier-no-purchase@example.invalid",
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
                "group_ids": [Command.set([
                    self.env.ref("base.group_user").id,
                    self.env.ref("stock.group_stock_user").id,
                ])],
            }
        )
        user.write({"password": self.test_password})
        self.authenticate(user.login, self.test_password)
        detail = self._get_json(f"/autostock/api/v1/suppliers/{supplier.id}")
        self.assertEqual(detail["supplier"]["id"], supplier.id)
        self.assertFalse(detail["purchase_history"]["available"])
        self.assertTrue(detail["purchase_history"]["note"])
