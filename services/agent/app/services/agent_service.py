from __future__ import annotations

from typing import cast

from fastapi import HTTPException, status

from app.config import Settings, settings
from app.models.agent import AgentConfig, AgentCreate, AgentInDB, AgentUpdate, ProviderName
from app.repositories.agent_repo import AgentRepository
from app.repositories.company_repo import CompanyRepository

_AGENT_NOT_FOUND_DETAIL = "Agent not found"
_VALID_PROVIDERS = frozenset({"openai", "anthropic", "deepseek", "ollama"})


def _coerce_provider(name: str) -> ProviderName:
    if name in _VALID_PROVIDERS:
        return cast(ProviderName, name)
    return "openai"


def _default_model_for_provider(provider: ProviderName, s: Settings) -> str:
    return {
        "openai": s.openai_chat_model,
        "anthropic": s.anthropic_chat_model,
        "deepseek": s.deepseek_chat_model,
        "ollama": s.ollama_chat_model,
    }[provider]


def _normalize_create_config(payload: AgentCreate, s: Settings) -> AgentConfig:
    cfg = payload.config.model_copy(deep=True)
    if "provider" not in payload.config.model_fields_set:
        cfg = cfg.model_copy(update={"provider": _coerce_provider(s.default_provider)})
    if cfg.model is None:
        cfg = cfg.model_copy(update={"model": _default_model_for_provider(cfg.provider, s)})
    return cfg


class AgentService:
    def __init__(self, repo: AgentRepository, company_repo: CompanyRepository) -> None:
        self.repo = repo
        self.company_repo = company_repo

    async def _validate_company(self, user_id: str, company_id: str | None) -> None:
        if company_id is None:
            return
        if await self.company_repo.get_by_id(user_id, company_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    async def create_agent(self, user_id: str, payload: AgentCreate) -> AgentInDB:
        await self._validate_company(user_id, payload.company_id)
        normalized = payload.model_copy(update={"config": _normalize_create_config(payload, settings)})
        return await self.repo.create(user_id, normalized)

    async def list_agents(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        *,
        company_id: str | None = None,
    ) -> list[AgentInDB]:
        if company_id is not None:
            await self._validate_company(user_id, company_id)
        return await self.repo.list_by_user(user_id, limit, offset, company_id=company_id)

    async def get_agent(self, user_id: str, agent_id: str) -> AgentInDB:
        agent = await self.repo.get_by_id(user_id, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_AGENT_NOT_FOUND_DETAIL,
            )
        return agent

    async def update_agent(self, user_id: str, agent_id: str, payload: AgentUpdate) -> AgentInDB:
        if "company_id" in payload.model_fields_set:
            await self._validate_company(user_id, payload.company_id)
        agent = await self.repo.update(user_id, agent_id, payload)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_AGENT_NOT_FOUND_DETAIL,
            )
        return agent

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        deleted = await self.repo.delete(user_id, agent_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_AGENT_NOT_FOUND_DETAIL,
            )
