from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.models.agent import AgentInDB, AgentType
from app.runtime.accountant import AccountantAgent
from app.runtime.base_agent import BaseAgent
from app.runtime.tool_context import ToolContext

AGENT_REGISTRY: dict[AgentType, type[BaseAgent]] = {
    "accountant": AccountantAgent,
}


def create_agent_runtime(
    agent: AgentInDB,
    llm: BaseChatModel,
    user_id: str,
    tool_context: ToolContext,
) -> BaseAgent:
    runtime_class = AGENT_REGISTRY.get(agent.agent_type)
    if runtime_class is None:
        raise ValueError(f"Unsupported agent type: {agent.agent_type}")
    return runtime_class(agent=agent, llm=llm, user_id=user_id, tool_context=tool_context)
