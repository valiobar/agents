from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
import logging
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from app.config import settings
from app.models.agent import AgentInDB
from app.models.conversation import MessageSchema
from app.runtime.tool_context import ToolContext

_MAX_AGENT_ITERATIONS = 150
_MAX_TOOL_LOG_CHARS = 500

logger = logging.getLogger(__name__)


def _stringify_chunk_content(content: str | list[str | dict] | None) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data", {})
    return data if isinstance(data, dict) else {}


def _stream_text_from_event(event: dict[str, Any]) -> str:
    if event.get("event") != "on_chat_model_stream":
        return ""
    chunk: Any = _event_data(event).get("chunk")
    return _stringify_chunk_content(getattr(chunk, "content", None))


def _final_output_from_event(event: dict[str, Any]) -> str:
    if event.get("event") != "on_chain_end" or event.get("name") != "AgentExecutor":
        return ""
    output = _event_data(event).get("output", {})
    if not isinstance(output, dict):
        return ""
    return str(output.get("output") or "")


def _preview_log_value(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else repr(value)
    if len(text) <= _MAX_TOOL_LOG_CHARS:
        return text
    return f"{text[:_MAX_TOOL_LOG_CHARS]}..."


def _tool_log_extra(event: dict[str, Any], agent: AgentInDB, user_id: str) -> dict[str, Any]:
    return {
        "agent_id": agent.id,
        "agent_type": agent.agent_type,
        "user_id": user_id,
        "run_id": event.get("run_id"),
        "tool_name": event.get("name"),
    }


def _log_tool_event(event: dict[str, Any], agent: AgentInDB, user_id: str) -> None:
    if not settings.is_development:
        return

    event_name = event.get("event")
    if event_name not in {"on_tool_start", "on_tool_end", "on_tool_error"}:
        return

    data = _event_data(event)
    extra = _tool_log_extra(event, agent, user_id)
    tool_name = extra["tool_name"]
    run_id = extra["run_id"]

    if event_name == "on_tool_start":
        tool_input = _preview_log_value(data.get("input"))
        logger.info(
            "langchain_tool_start tool=%s run_id=%s agent_id=%s agent_type=%s user_id=%s input=%s",
            tool_name,
            run_id,
            extra["agent_id"],
            extra["agent_type"],
            user_id,
            tool_input,
            extra={**extra, "tool_input": tool_input},
        )
        return

    if event_name == "on_tool_end":
        tool_output = _preview_log_value(data.get("output"))
        logger.info(
            "langchain_tool_end tool=%s run_id=%s agent_id=%s agent_type=%s user_id=%s output=%s",
            tool_name,
            run_id,
            extra["agent_id"],
            extra["agent_type"],
            user_id,
            tool_output,
            extra={**extra, "tool_output": tool_output},
        )
        return

    tool_error = _preview_log_value(data.get("error"))
    logger.warning(
        "langchain_tool_error tool=%s run_id=%s agent_id=%s agent_type=%s user_id=%s error=%s",
        tool_name,
        run_id,
        extra["agent_id"],
        extra["agent_type"],
        user_id,
        tool_error,
        extra={**extra, "tool_error": tool_error},
    )


class BaseAgent(ABC):
    """Strategy contract for agent runtimes (no FastAPI or MongoDB imports)."""

    def __init__(self, agent: AgentInDB, llm: BaseChatModel, user_id: str, tool_context: ToolContext) -> None:
        self.agent = agent
        self.llm = llm
        self.user_id = user_id
        self.tool_context = tool_context

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        raise NotImplementedError

    @abstractmethod
    def get_system_prompt(self) -> str:
        raise NotImplementedError

    def _to_chat_history(self, history: list[MessageSchema]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for item in history:
            if item.role == "user":
                messages.append(HumanMessage(content=item.content))
            elif item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            elif item.role == "system":
                messages.append(SystemMessage(content=item.content))
        return messages

    async def run(self, message: str, history: list[MessageSchema]) -> AsyncIterator[str]:
        tools = self.get_tools()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.get_system_prompt()),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=_MAX_AGENT_ITERATIONS,
        )

        emitted_text = False
        final_output = ""
        async for event in executor.astream_events(
            {
                "input": message,
                "chat_history": self._to_chat_history(history),
            },
            version="v2",
        ):
            _log_tool_event(event, self.agent, self.user_id)

            text = _stream_text_from_event(event)
            if text:
                emitted_text = True
                yield text
                continue

            final_output = _final_output_from_event(event) or final_output

        if not emitted_text and final_output:
            yield final_output
