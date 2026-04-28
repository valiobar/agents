from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.business import BusinessClient, BusinessClientError
from app.models.financial import ExpenseFilters


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


if __name__ == "__main__":
    unittest.main()
