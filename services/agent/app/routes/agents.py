from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from starlette.responses import StreamingResponse

from app.dependencies import get_agent_service, get_chat_service, get_user_id
from app.models.agent import AgentCreate, AgentResponse, AgentUpdate
from app.models.chat import ChatRequest
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.create_agent(user_id, payload)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    company_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    agents = await service.list_agents(user_id, limit=limit, offset=offset, company_id=company_id)
    return [AgentResponse.model_validate(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.get_agent(user_id, agent_id)
    return AgentResponse.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.update_agent(user_id, agent_id, payload)
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    await service.delete_agent(user_id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{agent_id}/chat")
async def chat(
    agent_id: str,
    payload: ChatRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    return StreamingResponse(
        service.stream_chat(user_id, agent_id, payload),
        media_type="text/event-stream",
    )
