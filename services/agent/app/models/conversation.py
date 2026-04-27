from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant", "system", "tool"]


class MessageSchema(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)
    created_at: datetime
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ConversationInDB(BaseModel):
    id: str
    user_id: str
    agent_id: str
    company_id: str | None = None
    title: str | None = None
    messages: list[MessageSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    company_id: str | None = None
    title: str | None
    messages: list[MessageSchema]
    created_at: datetime
    updated_at: datetime
