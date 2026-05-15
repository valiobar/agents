from __future__ import annotations

from unittest import IsolatedAsyncioTestCase, TestCase

from fastapi import HTTPException, status

from app.clients.business import BusinessClientError
from app.services.workflows import map_business_client_error, require_company_scoped_agent


class _FakeAgentRepo:
    def __init__(self, company_id: str | None = "company-1", *, missing: bool = False) -> None:
        self.company_id = company_id
        self.missing = missing

    async def get_by_id(self, user_id: str, agent_id: str):
        if self.missing:
            return None
        return type("Agent", (), {"id": agent_id, "user_id": user_id, "company_id": self.company_id})()


class _FakeBusinessClient:
    def __init__(
        self,
        *,
        exists: bool = True,
        error: BusinessClientError | None = None,
    ) -> None:
        self.exists = exists
        self.error = error

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        if self.error:
            raise self.error
        return self.exists


class BusinessClientErrorMappingTests(TestCase):
    def test_maps_business_client_4xx_to_original_status(self) -> None:
        exc = map_business_client_error(BusinessClientError("Invalid request", status_code=409))

        self.assertEqual(exc.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(exc.detail, "Invalid request")

    def test_maps_business_client_5xx_to_service_unavailable(self) -> None:
        exc = map_business_client_error(BusinessClientError("Business failed", status_code=500))

        self.assertEqual(exc.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(exc.detail, "Business failed")

    def test_maps_business_client_transport_error_to_service_unavailable(self) -> None:
        exc = map_business_client_error(BusinessClientError("Business unavailable"))

        self.assertEqual(exc.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(exc.detail, "Business unavailable")


class CompanyScopedAgentGuardTests(IsolatedAsyncioTestCase):
    async def test_returns_company_id_for_company_scoped_agent(self) -> None:
        company_id = await require_company_scoped_agent(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=_FakeAgentRepo(company_id="company-1"),
            business_client=_FakeBusinessClient(),
            workflow_name="Example workflow",
        )

        self.assertEqual(company_id, "company-1")

    async def test_rejects_missing_agent(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            await require_company_scoped_agent(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=_FakeAgentRepo(missing=True),
                business_client=_FakeBusinessClient(),
                workflow_name="Example workflow",
            )

        self.assertEqual(exc.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(exc.exception.detail, "Agent not found")

    async def test_rejects_unassigned_agent(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            await require_company_scoped_agent(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=_FakeAgentRepo(company_id=None),
                business_client=_FakeBusinessClient(),
                workflow_name="Example workflow",
            )

        self.assertEqual(exc.exception.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(exc.exception.detail, "Example workflow requires a company-scoped agent")

    async def test_rejects_missing_company(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            await require_company_scoped_agent(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=_FakeAgentRepo(company_id="company-1"),
                business_client=_FakeBusinessClient(exists=False),
                workflow_name="Example workflow",
            )

        self.assertEqual(exc.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(exc.exception.detail, "Company not found")

    async def test_maps_business_client_4xx_errors(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            await require_company_scoped_agent(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=_FakeAgentRepo(company_id="company-1"),
                business_client=_FakeBusinessClient(
                    error=BusinessClientError("Forbidden", status_code=status.HTTP_403_FORBIDDEN)
                ),
                workflow_name="Example workflow",
            )

        self.assertEqual(exc.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(exc.exception.detail, "Forbidden")

    async def test_maps_business_client_5xx_errors(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            await require_company_scoped_agent(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=_FakeAgentRepo(company_id="company-1"),
                business_client=_FakeBusinessClient(error=BusinessClientError("Business failed", status_code=500)),
                workflow_name="Example workflow",
            )

        self.assertEqual(exc.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(exc.exception.detail, "Business failed")

    async def test_maps_business_client_transport_errors(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            await require_company_scoped_agent(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=_FakeAgentRepo(company_id="company-1"),
                business_client=_FakeBusinessClient(error=BusinessClientError("Business unavailable")),
                workflow_name="Example workflow",
            )

        self.assertEqual(exc.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(exc.exception.detail, "Business unavailable")
