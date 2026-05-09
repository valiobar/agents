from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.business import BusinessClient, BusinessClientError
from app.models.financial import ExpenseFilters
from app.models.inventory import InventoryItemCreate, InventorySearchRequest, StockMovementCreate
from app.models.financial.receipt import ExtractedPartnerDraft


class BusinessClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_user_header_and_query_params(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["x-user-id"], "user-1")
            self.assertEqual(request.url.path, "/expenses")
            self.assertEqual(request.url.params["limit"], "20")
            self.assertEqual(request.url.params["offset"], "0")
            return httpx.Response(200, json=[])

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.list_expenses("user-1", ExpenseFilters(), limit=20, offset=0)

        self.assertEqual(result, [])

    async def test_company_exists_uses_business_validation_endpoint(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["x-user-id"], "user-1")
            self.assertEqual(request.url.path, "/companies/company-1/exists")
            return httpx.Response(200, json={"exists": True})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.company_exists("user-1", "company-1")

        self.assertTrue(result)

    async def test_converts_http_error_detail_to_business_client_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(409, json={"detail": "Partner already exists."})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)

            with self.assertRaises(BusinessClientError) as raised:
                await client.list_expenses("user-1", ExpenseFilters(), limit=20, offset=0)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.message, "Partner already exists.")

    async def test_find_or_create_updates_matched_partner_with_confirmed_vendor_details(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.method == "GET" and request.url.path == "/partners":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "partner-1",
                            "user_id": "user-1",
                            "company_id": "company-1",
                            "kind": "client",
                            "name": "Vendor Ltd",
                            "registration_number": "123",
                            "vat_number": None,
                            "city": "Sofia",
                            "country": "Bulgaria",
                            "address": "Old address",
                            "accountable_person": "Old Person",
                            "email": None,
                            "phone": None,
                            "notes": None,
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                )
            if request.method == "PATCH" and request.url.path == "/partners/partner-1":
                self.assertEqual(request.url.params["company_id"], "company-1")
                body = request.read().decode("utf-8")
                self.assertIn('"kind":"both"', body)
                self.assertIn('"address":"New address"', body)
                self.assertIn('"accountable_person":"New Person"', body)
                self.assertIn('"email":"vendor@example.com"', body)
                return httpx.Response(
                    200,
                    json={
                        "id": "partner-1",
                        "user_id": "user-1",
                        "company_id": "company-1",
                        "kind": "both",
                        "name": "Vendor Ltd",
                        "registration_number": "123",
                        "vat_number": None,
                        "city": "Sofia",
                        "country": "Bulgaria",
                        "address": "New address",
                        "accountable_person": "New Person",
                        "email": "vendor@example.com",
                        "phone": None,
                        "notes": None,
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-02T00:00:00Z",
                    },
                )
            return httpx.Response(500, json={"detail": "Unexpected request"})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.find_or_create_supplier_partner(
                user_id="user-1",
                company_id="company-1",
                vendor=ExtractedPartnerDraft(
                    name="Vendor Ltd",
                    registration_number="123",
                    vat_number=None,
                    city="   ",
                    country="",
                    address="New address",
                    accountable_person="New Person",
                    email="vendor@example.com",
                    phone=None,
                    confidence=0.9,
                    warnings=[],
                ),
            )

        self.assertEqual(result.status, "matched")
        self.assertIsNotNone(result.partner)
        self.assertEqual(result.partner.kind, "both")
        self.assertEqual(result.partner.address, "New address")
        self.assertEqual(result.partner.accountable_person, "New Person")
        self.assertEqual(result.partner.email, "vendor@example.com")
        self.assertEqual([request.method for request in requests], ["GET", "PATCH"])

    async def test_find_or_create_skips_patch_when_vendor_has_no_nonempty_updates(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.method == "GET" and request.url.path == "/partners":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "partner-1",
                            "user_id": "user-1",
                            "company_id": "company-1",
                            "kind": "supplier",
                            "name": "Vendor Ltd",
                            "registration_number": "123",
                            "vat_number": None,
                            "city": "Sofia",
                            "country": "Bulgaria",
                            "address": "Existing address",
                            "accountable_person": "Existing Person",
                            "email": None,
                            "phone": None,
                            "notes": None,
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                )
            return httpx.Response(500, json={"detail": "Unexpected request"})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.find_or_create_supplier_partner(
                user_id="user-1",
                company_id="company-1",
                vendor=ExtractedPartnerDraft(
                    name="   ",
                    registration_number="123",
                    vat_number=None,
                    city="",
                    country="",
                    address="",
                    accountable_person="",
                    email=None,
                    phone=None,
                    confidence=0.9,
                    warnings=[],
                ),
            )

        self.assertEqual(result.status, "matched")
        self.assertIsNotNone(result.partner)
        self.assertEqual(result.partner.address, "Existing address")
        self.assertEqual([request.method for request in requests], ["GET"])

    async def test_list_inventory_items_sends_company_filter(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["x-user-id"], "user-1")
            self.assertEqual(request.url.path, "/inventory/items")
            self.assertEqual(request.url.params["company_id"], "company-1")
            self.assertEqual(request.url.params["limit"], "50")
            return httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "returned_count": 1,
                    "offset": 0,
                    "limit": 50,
                    "truncated": False,
                    "next_offset": None,
                    "items": [
                        {
                            "id": "item-1",
                            "user_id": "user-1",
                            "company_id": "company-1",
                            "sku": "SKU-001",
                            "name": "Widget",
                            "unit": "pcs",
                            "aliases": [],
                            "is_active": True,
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.list_inventory_items("user-1", company_id="company-1")

        self.assertEqual(result.total_count, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].sku, "SKU-001")

    async def test_list_inventory_categories_uses_categories_endpoint(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["x-user-id"], "user-1")
            self.assertEqual(request.url.path, "/inventory/categories")
            self.assertEqual(request.url.params["company_id"], "company-1")
            return httpx.Response(
                200,
                json={
                    "total_category_count": 2,
                    "uncategorized_item_count": 1,
                    "categories": [
                        {"category": "beverages", "item_count": 4, "active_item_count": 3},
                        {"category": "snacks", "item_count": 1, "active_item_count": 1},
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.list_inventory_categories("user-1", company_id="company-1")

        self.assertEqual(result.total_category_count, 2)
        self.assertEqual(result.uncategorized_item_count, 1)
        self.assertEqual([row.category for row in result.categories], ["beverages", "snacks"])

    async def test_search_inventory_posts_search_request(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/search")
            self.assertEqual(request.method, "POST")
            data = json.loads(request.read())
            self.assertEqual(data["query"], "iphones")
            self.assertEqual(data["company_id"], "company-1")
            return httpx.Response(
                200,
                json={
                    "matches": [
                        {
                            "item_id": "item-1",
                            "name": "iPhone 15",
                            "sku": "IP15",
                            "unit": "pcs",
                            "confidence": 0.95,
                            "match_reason": "text",
                            "available_quantity": "10",
                        }
                    ],
                    "total_available_quantity": "10",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.search_inventory(
                "user-1",
                InventorySearchRequest(company_id="company-1", query="iphones"),
            )

        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.matches[0].name, "iPhone 15")

    async def test_create_inventory_item_sends_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/items")
            self.assertEqual(request.method, "POST")
            payload = json.loads(request.read())
            self.assertEqual(payload["company_id"], "company-1")
            self.assertEqual(payload["sku"], "SKU-NEW")
            return httpx.Response(
                200,
                json={
                    "id": "item-new",
                    "user_id": "user-1",
                    "company_id": "company-1",
                    "sku": "SKU-NEW",
                    "name": "New Item",
                    "unit": "pcs",
                    "aliases": [],
                    "is_active": True,
                    "created_at": "2026-05-01T00:00:00Z",
                    "updated_at": "2026-05-01T00:00:00Z",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.create_inventory_item(
                "user-1",
                InventoryItemCreate(company_id="company-1", sku="SKU-NEW", name="New Item", unit="pcs"),
            )

        self.assertEqual(result.sku, "SKU-NEW")

    async def test_create_stock_movement_sends_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/movements")
            self.assertEqual(request.method, "POST")
            payload = json.loads(request.read())
            self.assertEqual(payload["movement_type"], "receipt")
            self.assertEqual(payload["quantity_delta"], "10")
            return httpx.Response(
                200,
                json={
                    "id": "move-1",
                    "user_id": "user-1",
                    "company_id": "company-1",
                    "item_id": "item-1",
                    "location_id": "loc-1",
                    "movement_type": "receipt",
                    "quantity_delta": "10",
                    "reason": "restock",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.create_stock_movement(
                "user-1",
                StockMovementCreate(
                    company_id="company-1",
                    item_id="item-1",
                    location_id="loc-1",
                    movement_type="receipt",
                    quantity_delta="10",
                    reason="restock",
                ),
            )

        self.assertEqual(result.movement_type, "receipt")

    async def test_get_stock_levels_with_reorder_filter(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/levels")
            self.assertEqual(request.url.params["company_id"], "company-1")
            self.assertEqual(request.url.params["below_reorder_point"], "true")
            self.assertEqual(request.url.params["limit"], "50")
            self.assertEqual(request.url.params["offset"], "0")
            self.assertEqual(request.url.params["sort_direction"], "desc")
            return httpx.Response(
                200,
                json={
                    "total_stock_level_count": 1,
                    "unique_item_count": 1,
                    "returned_count": 1,
                    "offset": 0,
                    "limit": 50,
                    "truncated": False,
                    "next_offset": None,
                    "levels": [
                        {
                            "item_id": "item-1",
                            "item_name": "Widget",
                            "item_sku": "SKU-001",
                            "location_id": "loc-1",
                            "location_name": "Main",
                            "available_quantity": "3",
                            "unit": "pcs",
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.get_stock_levels(
                "user-1",
                company_id="company-1",
                below_reorder_point=True,
            )

        self.assertEqual(result.total_stock_level_count, 1)
        self.assertEqual(result.levels[0].item_name, "Widget")

    async def test_get_import_preview(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/import-previews/preview-1")
            self.assertEqual(request.method, "GET")
            return httpx.Response(
                200,
                json={
                    "id": "preview-1",
                    "user_id": "user-1",
                    "company_id": "company-1",
                    "source_type": "supplier_invoice",
                    "status": "draft",
                    "lines": [
                        {
                            "candidate": {"name": "Widget", "sku": "SKU-001"},
                            "matched_item_id": "item-1",
                            "location_id": "loc-1",
                            "receipt_quantity": "5",
                            "warnings": [],
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.get_import_preview("user-1", preview_id="preview-1")

        self.assertEqual(result.id, "preview-1")
        self.assertEqual(result.status, "draft")

    async def test_confirm_import_preview(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/import-previews/preview-1/confirm")
            self.assertEqual(request.method, "POST")
            return httpx.Response(
                200,
                json={
                    "preview_id": "preview-1",
                    "items_created": 2,
                    "items_updated": 1,
                    "movements_created": 3,
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.confirm_import_preview("user-1", preview_id="preview-1")

        self.assertEqual(result.items_created, 2)
        self.assertEqual(result.movements_created, 3)

    async def test_get_inventory_overview(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/reports/overview")
            self.assertEqual(request.url.params["company_id"], "company-1")
            return httpx.Response(
                200,
                json={
                    "total_item_count": 10,
                    "active_item_count": 8,
                    "inactive_item_count": 2,
                    "category_count": 4,
                    "location_count": 3,
                    "low_stock_count": 2,
                    "negative_stock_count": 1,
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.get_inventory_overview("user-1", company_id="company-1")

        self.assertEqual(result.total_item_count, 10)
        self.assertEqual(result.negative_stock_count, 1)

    async def test_get_inventory_item_details(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/inventory/items/item-1/details")
            self.assertEqual(request.url.params["company_id"], "company-1")
            return httpx.Response(
                200,
                json={
                    "item": {
                        "id": "item-1",
                        "user_id": "user-1",
                        "company_id": "company-1",
                        "sku": "SKU-001",
                        "name": "Widget",
                        "unit": "pcs",
                        "aliases": [],
                        "available_in_stock": "12",
                        "is_active": True,
                    },
                    "stock_levels": [
                        {
                            "item_id": "item-1",
                            "item_name": "Widget",
                            "item_sku": "SKU-001",
                            "location_id": "loc-1",
                            "location_name": "Main",
                            "available_quantity": "12",
                            "unit": "pcs",
                        }
                    ],
                    "recent_movements": [],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://business:8005",
        ) as http:
            client = BusinessClient(http)
            result = await client.get_inventory_item_details(
                "user-1",
                company_id="company-1",
                item_id="item-1",
            )

        self.assertEqual(result.item.id, "item-1")
        self.assertEqual(result.stock_levels[0].location_name, "Main")


if __name__ == "__main__":
    unittest.main()
