from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None


class ChatEvent(BaseModel):
    event: str
    data: dict[str, str | int | float | bool | None]
