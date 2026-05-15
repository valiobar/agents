from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from fastapi import HTTPException, status

from app.clients.business import BusinessClient, BusinessClientError
from app.repositories.agent_repo import AgentRepository


@dataclass(frozen=True)
class WorkflowContext:
    user_id: str
    agent_id: str
    company_id: str
    business_client: BusinessClient


TResponse = TypeVar("TResponse")


class AgentWorkflow(Protocol[TResponse]):
    async def run(self, context: WorkflowContext) -> TResponse:
        ...


def map_business_client_error(exc: BusinessClientError) -> HTTPException:
    if exc.status_code and 400 <= exc.status_code < 500:
        return HTTPException(status_code=exc.status_code, detail=exc.message)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message)


async def require_company_scoped_agent(
    *,
    user_id: str,
    agent_id: str,
    agent_repo: AgentRepository,
    business_client: BusinessClient,
    workflow_name: str,
) -> str:
    agent = await agent_repo.get_by_id(user_id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if not agent.company_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{workflow_name} requires a company-scoped agent",
        )
    try:
        exists = await business_client.company_exists(user_id, agent.company_id)
    except BusinessClientError as exc:
        raise map_business_client_error(exc) from exc
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return agent.company_id
