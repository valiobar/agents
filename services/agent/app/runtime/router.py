"""Router graph types: routing decisions, SSE-safe metadata, LangGraph state, and classification."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.models.shared.agent import AgentInDB
from app.models.shared.conversation import MessageSchema
from app.runtime.base_agent import BaseAgent
from app.runtime.loop_logging import AgentLoopLogger, LLMTraceState, event_data, stringify_chunk_content
from app.runtime.tool_context import ToolContext
from app.runtime.usage import LLMUsageEvent

logger = logging.getLogger(__name__)

DEFAULT_ROUTER_SYSTEM_PROMPT = """You are the router for a small finance/operations agent platform.

Pick exactly one specialist:
- accountant: invoices, expenses, partners, VAT/tax, financial summaries, payments, bookkeeping.
- inventory: stock levels, items, locations, movements, import previews, reorder points, warehouses.
- general: greetings, platform help, unsupported topics.

Rules:
1. Use the latest message and recent history only.
2. Route affirmative replies to the same specialist that produced the previous draft.
3. Respect company scope. Do not invent business facts (invoice amounts, stock quantities, partner names, IDs, or documents that are not stated in the conversation).
4. If unsure between accountant and inventory, use the dominant nouns.
5. Never invent or assume company-specific data beyond the routing context identifiers provided.
"""

Route = Literal["accountant", "inventory", "general"]
CompanyScope = Literal["assigned", "unassigned"]


class RouterDecision(BaseModel):
    route: Route = Field(description="Specialist that should handle this user turn.")
    reason: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)


ROUTER_CLASSIFICATION_FALLBACK = RouterDecision(
    route="general",
    reason="Structured routing failed; defaulting to general specialist.",
    confidence=0.0,
)


class RouteMetadata(BaseModel):
    predicted_route: Route
    executed_route: Route
    reason: str
    confidence: float
    company_id: str | None = None
    company_scope: CompanyScope


class RouterGraphState(TypedDict, total=False):
    user_id: str
    company_id: str | None
    company_scope: CompanyScope
    message: str
    history: list[MessageSchema]
    predicted_route: Route
    route: Route
    route_reason: str
    confidence: float
    answer: str
    tokens: list[str]
    usage_events: list[LLMUsageEvent]
    error: str


class _RouterGraphRuntime(Protocol):
    agent: AgentInDB
    user_id: str
    llm: BaseChatModel
    fallback_llm: BaseChatModel
    accountant_runtime: BaseAgent | None
    inventory_runtime: BaseAgent | None

    def get_system_prompt(self) -> str:
        raise NotImplementedError

    def get_general_system_prompt(self) -> str:
        raise NotImplementedError


class DirectLLMUsageCollector:
    def __init__(self, *, agent: AgentInDB, user_id: str, llm: BaseChatModel) -> None:
        self.logger = AgentLoopLogger(agent=agent, user_id=user_id, llm=llm)
        self.state = LLMTraceState()

    def track(self, event: dict[str, Any]) -> None:
        self.logger.track_event(event, self.state)

    def consume(self) -> list[LLMUsageEvent]:
        self.logger.cancel_heartbeat(self.state)
        events = list(self.logger.usage_events)
        self.logger.usage_events = []
        return events


def _history_to_messages(history: list[MessageSchema], *, max_turns: int = 6) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in history[-max_turns:]:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        elif item.role == "assistant":
            messages.append(AIMessage(content=item.content))
        elif item.role == "system":
            messages.append(SystemMessage(content=item.content))
    return messages


async def invoke_structured_with_usage(
    runnable: Runnable[Any, Any],
    messages: list[BaseMessage],
    collector: DirectLLMUsageCollector,
) -> RouterDecision:
    result: RouterDecision | None = None
    async for event in runnable.astream_events(messages, version="v2"):
        collector.track(event)
        if event.get("event") == "on_chain_end":
            output = event_data(event).get("output")
            if isinstance(output, RouterDecision):
                result = output
            elif isinstance(output, dict):
                try:
                    result = RouterDecision.model_validate(output)
                except Exception:
                    continue
    if result is not None:
        return result

    value = await runnable.ainvoke(messages)
    return RouterDecision.model_validate(value)


async def _invoke_general_with_usage(
    llm: BaseChatModel,
    messages: list[BaseMessage],
    collector: DirectLLMUsageCollector,
) -> str:
    chunks: list[str] = []
    last_output: Any = None

    async for event in llm.astream_events(messages, version="v2"):
        collector.track(event)
        if event.get("event") == "on_chat_model_stream":
            chunk = event_data(event).get("chunk")
            text = stringify_chunk_content(getattr(chunk, "content", None))
            if text:
                chunks.append(text)
        elif event.get("event") == "on_chat_model_end":
            last_output = event_data(event).get("output")

    if last_output is not None:
        text = stringify_chunk_content(getattr(last_output, "content", None))
        if text:
            return text
        return str(last_output)

    if chunks:
        return "".join(chunks)

    fallback = await llm.ainvoke(messages)
    text = stringify_chunk_content(getattr(fallback, "content", None))
    return text or str(fallback)


def _available_route(router: _RouterGraphRuntime, predicted: Route) -> Route:
    if predicted == "accountant" and router.accountant_runtime is None:
        return "general"
    if predicted == "inventory" and router.inventory_runtime is None:
        return "general"
    return predicted


async def _run_subagent(child: BaseAgent, state: RouterGraphState) -> RouterGraphState:
    tokens = [token async for token in child.run(state["message"], state.get("history", []))]
    usage_events = list(state.get("usage_events", []))
    usage_events.extend(child.consume_usage_events())
    return {
        "tokens": tokens,
        "answer": "".join(tokens),
        "usage_events": usage_events,
    }


async def _run_general_response(router: _RouterGraphRuntime, state: RouterGraphState) -> RouterGraphState:
    messages: list[BaseMessage] = [
        SystemMessage(content=router.get_general_system_prompt()),
        *_history_to_messages(state.get("history", [])),
        HumanMessage(content=state["message"]),
    ]
    collector = DirectLLMUsageCollector(agent=router.agent, user_id=router.user_id, llm=router.fallback_llm)
    answer = await _invoke_general_with_usage(router.fallback_llm, messages, collector)
    usage_events = list(state.get("usage_events", []))
    usage_events.extend(collector.consume())
    return {
        "tokens": [answer],
        "answer": answer,
        "usage_events": usage_events,
    }


def _build_classification_messages(
    *,
    system_prompt: str,
    message: str,
    history: list[MessageSchema],
    user_id: str,
    company_id: str | None,
    company_scope: CompanyScope,
) -> list[BaseMessage]:
    user_block = (
        f"Authenticated user id: {user_id}\n"
        f"Company scope: {company_scope}\n"
        f"Company id: {company_id or '(none)'}\n\n"
        f"Recent history:\n{_format_history_snippet(history)}\n\n"
        f"Latest user message:\n{message.strip()}"
    )
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_block),
    ]


def _format_history_snippet(
    history: list[MessageSchema],
    *,
    max_turns: int = 6,
    max_chars: int = 240,
) -> str:
    if not history:
        return "(no prior turns)"
    lines: list[str] = []
    for msg in history[-max_turns:]:
        content = msg.content.strip().replace("\n", " ")
        if len(content) > max_chars:
            content = f"{content[:max_chars]} ..."
        lines.append(f"{msg.role.upper()}: {content}")
    return "\n".join(lines)


async def classify_route(
    *,
    llm: BaseChatModel,
    system_prompt: str,
    message: str,
    history: list[MessageSchema],
    user_id: str,
    company_id: str | None,
    company_scope: CompanyScope,
    collector: DirectLLMUsageCollector | None = None,
) -> RouterDecision:
    structured = llm.with_structured_output(RouterDecision)
    messages = _build_classification_messages(
        system_prompt=system_prompt,
        message=message,
        history=history,
        user_id=user_id,
        company_id=company_id,
        company_scope=company_scope,
    )

    try:
        if collector is None:
            decision = await structured.ainvoke(messages)
        else:
            decision = await invoke_structured_with_usage(structured, messages, collector)
    except Exception:
        logger.warning(
            "Router structured classification failed; using deterministic general fallback.",
            exc_info=True,
        )
        return ROUTER_CLASSIFICATION_FALLBACK.model_copy(deep=True)
    return decision


def build_router_graph(router: _RouterGraphRuntime):
    graph = StateGraph(RouterGraphState)

    async def router_node(state: RouterGraphState) -> RouterGraphState:
        collector = DirectLLMUsageCollector(agent=router.agent, user_id=router.user_id, llm=router.llm)
        decision = await classify_route(
            llm=router.llm,
            system_prompt=router.get_system_prompt(),
            message=state["message"],
            history=state.get("history", []),
            user_id=state.get("user_id", router.user_id),
            company_id=state.get("company_id", router.agent.company_id),
            company_scope=state.get("company_scope", "unassigned"),
            collector=collector,
        )

        executed = _available_route(router, decision.route)
        usage_events = list(state.get("usage_events", []))
        usage_events.extend(collector.consume())
        return {
            "predicted_route": decision.route,
            "route": executed,
            "route_reason": decision.reason,
            "confidence": decision.confidence,
            "usage_events": usage_events,
        }

    async def accountant_node(state: RouterGraphState) -> RouterGraphState:
        child = router.accountant_runtime
        if child is None:
            raise RuntimeError("Router accountant runtime is not configured.")
        return await _run_subagent(child, state)

    async def inventory_node(state: RouterGraphState) -> RouterGraphState:
        child = router.inventory_runtime
        if child is None:
            raise RuntimeError("Router inventory runtime is not configured.")
        return await _run_subagent(child, state)

    async def general_node(state: RouterGraphState) -> RouterGraphState:
        return await _run_general_response(router, state)

    graph.add_node("router", router_node)
    graph.add_node("accountant", accountant_node)
    graph.add_node("inventory", inventory_node)
    graph.add_node("general", general_node)
    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        lambda state: state.get("route", "general"),
        {"accountant": "accountant", "inventory": "inventory", "general": "general"},
    )
    graph.add_edge("accountant", END)
    graph.add_edge("inventory", END)
    graph.add_edge("general", END)
    return graph.compile()


DEFAULT_ROUTER_GENERAL_PROMPT = (
    "You are a concise helper for a small finance and operations business platform. "
    "Answer general questions only (greetings, platform help, scope clarifications). "
    "Do not invent invoices, expenses, partners, stock numbers, prices, or any other "
    "business data. If the user asks for specialist work, briefly explain that the "
    "request belongs to the accountant or inventory specialist."
)


class RouterAgent(BaseAgent):
    """Router runtime that classifies a chat turn and delegates to a specialist or general fallback.

    Execution is graph-based, not an `AgentExecutor` tool loop, so this class
    overrides `run()` and exposes no tools. `ChatService` injects child runtimes
    via `configure_children()` after registry construction.
    """

    def __init__(
        self,
        agent: AgentInDB,
        llm: BaseChatModel,
        user_id: str,
        tool_context: ToolContext,
    ) -> None:
        super().__init__(agent=agent, llm=llm, user_id=user_id, tool_context=tool_context)
        self.accountant_runtime: BaseAgent | None = None
        self.inventory_runtime: BaseAgent | None = None
        self.fallback_llm: BaseChatModel = llm
        self.route_metadata: RouteMetadata | None = None

    def configure_children(
        self,
        *,
        accountant_runtime: BaseAgent | None,
        inventory_runtime: BaseAgent | None,
        fallback_llm: BaseChatModel | None = None,
    ) -> None:
        self.accountant_runtime = accountant_runtime
        self.inventory_runtime = inventory_runtime
        self.fallback_llm = fallback_llm or self.llm

    def get_tools(self) -> list[BaseTool]:
        return []

    def get_system_prompt(self) -> str:
        override = self.agent.config.system_prompt_override
        if override:
            return (
                f"{DEFAULT_ROUTER_SYSTEM_PROMPT}\n\n"
                f"Additional routing instructions:\n{override}"
            )
        return DEFAULT_ROUTER_SYSTEM_PROMPT

    def get_general_system_prompt(self) -> str:
        return DEFAULT_ROUTER_GENERAL_PROMPT

    async def run(
        self,
        message: str,
        history: list[MessageSchema],
    ) -> AsyncIterator[str]:
        self.route_metadata = None
        company_scope: CompanyScope = "assigned" if self.agent.company_id else "unassigned"

        graph = build_router_graph(self)
        final_state: RouterGraphState = await graph.ainvoke(
            {
                "user_id": self.user_id,
                "company_id": self.agent.company_id,
                "company_scope": company_scope,
                "message": message,
                "history": history,
            }
        )

        self.route_metadata = RouteMetadata(
            predicted_route=final_state["predicted_route"],
            executed_route=final_state["route"],
            reason=final_state["route_reason"],
            confidence=final_state["confidence"],
            company_id=self.agent.company_id,
            company_scope=company_scope,
        )

        usage_events = final_state.get("usage_events") or []
        if usage_events:
            self._usage_events.extend(usage_events)

        for child in (self.accountant_runtime, self.inventory_runtime):
            if child is not None:
                self._usage_events.extend(child.consume_usage_events())
                self._ui_events.extend(child.consume_ui_events())

        for token in final_state.get("tokens", []):
            yield token
