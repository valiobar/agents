from __future__ import annotations

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.clients.business import BusinessClient
from app.clients.knowledge import KnowledgeClient
from app.config import settings
from app.repositories.agent_repo import AgentRepository
from app.repositories.conversation_repo import ConversationRepository
from app.runtime.tool_context import ToolContext
from app.services.agent_service import AgentService
from app.services.companybook_service import CompanyBookService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.receipt_service import ReceiptService
from app.utils.db import get_database


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-user-id header",
        )
    return x_user_id


def get_db() -> AsyncIOMotorDatabase:
    return get_database()


def get_agent_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> AgentRepository:
    return AgentRepository(db)


def get_conversation_repo(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConversationRepository:
    return ConversationRepository(db)


def get_companybook_service() -> CompanyBookService:
    return CompanyBookService(
        api_key=settings.companybook_api_key,
        base_url=settings.companybook_base_url,
        timeout=settings.companybook_timeout_seconds,
    )


def get_business_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.business_http


def get_business_client(http: httpx.AsyncClient = Depends(get_business_http)) -> BusinessClient:
    return BusinessClient(http)


def get_knowledge_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.knowledge_http


def get_knowledge_client(http: httpx.AsyncClient = Depends(get_knowledge_http)) -> KnowledgeClient:
    return KnowledgeClient(http)


def get_receipt_service(
    agent_repo: AgentRepository = Depends(get_agent_repo),
    knowledge_client: KnowledgeClient = Depends(get_knowledge_client),
    business_client: BusinessClient = Depends(get_business_client),
) -> ReceiptService:
    return ReceiptService(agent_repo, knowledge_client, business_client)


def get_agent_service(
    repo: AgentRepository = Depends(get_agent_repo),
    business_client: BusinessClient = Depends(get_business_client),
) -> AgentService:
    return AgentService(repo, business_client=business_client)


def get_tool_context(
    business_client: BusinessClient = Depends(get_business_client),
    companybook_service: CompanyBookService = Depends(get_companybook_service),
    knowledge_http: httpx.AsyncClient = Depends(get_knowledge_http),
) -> ToolContext:
    return ToolContext(
        business_client=business_client,
        companybook_service=companybook_service,
        knowledge_http=knowledge_http,
    )


def get_chat_service(
    agent_repo: AgentRepository = Depends(get_agent_repo),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    tool_context: ToolContext = Depends(get_tool_context),
) -> ChatService:
    return ChatService(agent_repo, conversation_repo, tool_context)


def get_conversation_service(
    repo: ConversationRepository = Depends(get_conversation_repo),
) -> ConversationService:
    return ConversationService(repo)

