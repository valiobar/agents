from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentType = Literal["accountant", "inventory", "router"]
ProviderName = Literal["openai", "anthropic", "deepseek", "ollama"]


class AgentConfig(BaseModel):
    provider: ProviderName = "openai"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    system_prompt_override: str | None = Field(default=None, max_length=4000)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    agent_type: AgentType = "accountant"
    company_id: str | None = None
    config: AgentConfig = Field(default_factory=AgentConfig)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    company_id: str | None = None
    config: AgentConfig | None = None


class AgentInDB(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None
    agent_type: AgentType
    company_id: str | None
    config: AgentConfig
    created_at: datetime
    updated_at: datetime


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    agent_type: AgentType
    company_id: str | None
    config: AgentConfig
    created_at: datetime
    updated_at: datetime
