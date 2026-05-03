from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from app.config import settings
from app.models.agent import AgentInDB
from app.models.conversation import MessageSchema
from app.runtime.hooks import AgentRunChunk, AgentRunEvent, AgentRunInput, AgentRunResult
from app.runtime.loop_logging import AgentLoopLogger, LLMTraceState, event_data, stringify_chunk_content
from app.runtime.tool_context import ToolContext
from app.runtime.usage import LLMUsageEvent


def _stream_text_from_event(event: dict[str, Any]) -> str:
    if event.get("event") != "on_chat_model_stream":
        return ""
    chunk = event_data(event).get("chunk")
    return stringify_chunk_content(getattr(chunk, "content", None))


def _final_output_from_event(event: dict[str, Any]) -> str:
    if event.get("event") != "on_chain_end" or event.get("name") != "AgentExecutor":
        return ""
    output = event_data(event).get("output", {})
    if not isinstance(output, dict):
        return ""
    return str(output.get("output") or "")


class BaseAgent(ABC):
    """Strategy contract for agent runtimes (no FastAPI or MongoDB imports)."""

    def __init__(self, agent: AgentInDB, llm: BaseChatModel, user_id: str, tool_context: ToolContext) -> None:
        self.agent = agent
        self.llm = llm
        self.user_id = user_id
        self.tool_context = tool_context
        self._usage_events: list[LLMUsageEvent] = []

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        raise NotImplementedError

    @abstractmethod
    def get_system_prompt(self) -> str:
        raise NotImplementedError

    async def prepare_run_input(self, run_input: AgentRunInput) -> AgentRunInput | None:
        return run_input

    async def prepare_tools(self, tools: list[BaseTool], run_input: AgentRunInput) -> list[BaseTool] | None:
        return tools

    async def on_run_start(self, run_input: AgentRunInput, tools: list[BaseTool]) -> None:
        return None

    async def on_event(self, event: AgentRunEvent) -> AgentRunEvent | None:
        return event

    async def on_chunk(self, chunk: AgentRunChunk) -> AgentRunChunk | None:
        return chunk

    async def on_run_end(self, result: AgentRunResult) -> AgentRunResult | None:
        return result

    async def on_run_error(self, exc: Exception, run_input: AgentRunInput | None) -> None:
        return None

    def consume_usage_events(self) -> list[LLMUsageEvent]:
        events = self._usage_events
        self._usage_events = []
        return events

    async def _apply_prepare_run_input(self, run_input: AgentRunInput) -> AgentRunInput:
        updated = await self.prepare_run_input(run_input)
        return updated if updated is not None else run_input

    async def _apply_prepare_tools(self, tools: list[BaseTool], run_input: AgentRunInput) -> list[BaseTool]:
        updated = await self.prepare_tools(tools, run_input)
        return updated if updated is not None else tools

    async def _apply_on_event(self, event: AgentRunEvent) -> AgentRunEvent:
        updated = await self.on_event(event)
        return updated if updated is not None else event

    async def _apply_on_chunk(self, chunk: AgentRunChunk) -> AgentRunChunk:
        updated = await self.on_chunk(chunk)
        return updated if updated is not None else chunk

    async def _apply_on_run_end(self, result: AgentRunResult) -> AgentRunResult:
        updated = await self.on_run_end(result)
        return updated if updated is not None else result

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
        run_input: AgentRunInput | None = None
        loop_logger: AgentLoopLogger | None = None
        llm_state = LLMTraceState()

        try:
            run_input = await self._apply_prepare_run_input(AgentRunInput(message=message, history=history))
            tools = await self._apply_prepare_tools(self.get_tools(), run_input)

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
                max_iterations=settings.max_agent_iterations,
            )
            loop_logger = AgentLoopLogger(agent=self.agent, user_id=self.user_id, llm=self.llm)
            loop_logger.run_start(run_input.message, len(run_input.history), [tool.name for tool in tools])
            loop_logger.executor_ready()
            await self.on_run_start(run_input, tools)

            emitted_text = False
            output_chars = 0
            final_output = ""

            async for raw_event in executor.astream_events(
                {
                    "input": run_input.message,
                    "chat_history": self._to_chat_history(run_input.history),
                },
                version="v2",
            ):
                loop_logger.track_event(raw_event, llm_state)

                event = await self._apply_on_event(AgentRunEvent.from_raw(raw_event, run_input.metadata))
                text = _stream_text_from_event(event.raw)
                if text:
                    chunk = await self._apply_on_chunk(
                        AgentRunChunk(text=text, event=event, metadata=run_input.metadata)
                    )
                    if chunk.text:
                        emitted_text = True
                        output_chars += len(chunk.text)
                        yield chunk.text
                    continue

                final_output = _final_output_from_event(event.raw) or final_output

            result = await self._apply_on_run_end(
                AgentRunResult(
                    emitted_text=emitted_text,
                    final_output=final_output,
                    output_chars=output_chars,
                    usage_events=list(loop_logger.usage_events),
                    metadata=run_input.metadata,
                )
            )
            self._usage_events.extend(result.usage_events)

            if not result.emitted_text and result.final_output:
                yield result.final_output
        except Exception as exc:
            await self.on_run_error(exc, run_input)
            raise
        finally:
            if loop_logger is not None:
                loop_logger.cancel_heartbeat(llm_state)
