# Agent Service Analysis

## 1. Overview

This analysis reviews the Phase 3 Agent Service: how user-created agents are stored, how chat streaming works, how the Accountant Agent runtime is assembled, and how the documented `rag_search` and `calculator` tools are wired.

Key files and docs reviewed:

- `docs/architecture/overview.md`
- `docs/architecture/dependency-graph.md`
- `docs/services/agent/README.md`
- `docs/services/agent/architecture.md`
- `docs/services/agent/data-flow.md`
- `docs/services/agent/dependency-graph.md`
- `docs/data-models/agent.md`
- `docs/api/README.md`
- `services/agent/app/main.py`
- `services/agent/app/dependencies.py`
- `services/agent/app/routes/agents.py`
- `services/agent/app/routes/conversations.py`
- `services/agent/app/services/agent_service.py`
- `services/agent/app/services/chat_service.py`
- `services/agent/app/services/conversation_service.py`
- `services/agent/app/repositories/agent_repo.py`
- `services/agent/app/repositories/conversation_repo.py`
- `services/agent/app/models/agent.py`
- `services/agent/app/models/chat.py`
- `services/agent/app/models/conversation.py`
- `services/agent/app/runtime/base_agent.py`
- `services/agent/app/runtime/accountant.py`
- `services/agent/app/runtime/registry.py`
- `services/agent/app/runtime/providers/*`
- `services/agent/app/tools/rag.py`
- `services/agent/app/tools/calculator.py`
- `services/agent/app/utils/db.py`
- `docker-compose.yml`

The service is mostly aligned with the documented Phase 3 architecture: it uses async FastAPI routes, Motor for MongoDB, Pydantic models, user-scoped repository queries, provider and strategy patterns, and an SSE chat endpoint. The main functional risk is in the LangChain runtime: tools are bound to the model, but there is no tool-execution loop, so `rag_search` and `calculator` may be advertised to the model without actually being executed.

## 2. Architecture Context

The Agent Service is an internal FastAPI microservice on port `8002`. Client traffic should enter through the API Gateway on port `8000`; the gateway validates JWTs, rate limits through Redis, and injects `x-user-id`. The Agent Service trusts that header and does not decode JWTs directly.

The intended internal dependency direction is:

```text
routes -> services -> repositories -> MongoDB
                 \-> runtime -> tools -> Knowledge Base Service
```

Current Phase 3 responsibilities:

- Agent CRUD for `agent_type: "accountant"`.
- MongoDB-backed `agents` and `conversations` collections.
- Conversation history reads.
- SSE chat streaming via `POST /agents/{agent_id}/chat`.
- Provider selection for OpenAI, Anthropic, DeepSeek, and Ollama.
- Accountant Agent runtime.
- Phase 3 tools: `rag_search` and `calculator`.

Explicitly planned for Phase 4:

- Invoice and expense REST APIs.
- Structured financial query/write tools.
- Orchestrator-driven multi-agent workflows.

### How Agent Creation Works

1. Client calls `POST /agents` through the gateway with a bearer token.
2. Gateway validates the token and forwards the request with `x-user-id`.
3. `routes/agents.py` validates the request body as `AgentCreate`.
4. `AgentService.create_agent()` normalizes default provider/model config.
5. `AgentRepository.create()` inserts the document into MongoDB with `user_id`, `created_at`, and `updated_at`.
6. The route returns `AgentResponse`.

Example:

```bash
curl -X POST http://localhost:8010/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Accountant",
    "agent_type": "accountant",
    "config": {
      "provider": "openai",
      "temperature": 0.2
    }
  }'
```

Expected response shape:

```json
{
  "id": "665f1f77c9e0f7a8093bb711",
  "name": "My Accountant",
  "description": null,
  "agent_type": "accountant",
  "config": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "system_prompt_override": null
  },
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:00:00Z"
}
```

### How Chat Streaming Works

1. Client calls `POST /agents/{agent_id}/chat` with `Accept: text/event-stream`.
2. The gateway forwards the request with `x-user-id`.
3. `ChatService.stream_chat()` loads the user-scoped agent.
4. If `conversation_id` is provided, it loads the user-scoped conversation and verifies it belongs to the agent.
5. If `conversation_id` is omitted, it creates a new empty conversation and emits `event: conversation`.
6. The service builds the configured provider model through `LLMProviderFactory`.
7. The runtime registry resolves `accountant` to `AccountantAgent`.
8. The runtime converts recent persisted messages into LangChain messages.
9. Tokens are streamed as `event: token`.
10. On success, the user message and assistant message are appended to MongoDB.
11. The stream ends with `event: done`.

Example:

```bash
curl -N -X POST "http://localhost:8010/agents/$AGENT_ID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"message":"Calculate 20% VAT on 100 and explain it."}'
```

Expected SSE shape:

```text
event: conversation
data: {"conversation_id":"665f1f77c9e0f7a8093bb722"}

event: start
data: {"conversation_id":"665f1f77c9e0f7a8093bb722"}

event: token
data: {"content":"20% VAT on 100 is 20."}

event: done
data: {"conversation_id":"665f1f77c9e0f7a8093bb722"}
```

### How Conversation History Works

The service persists only successful user/assistant turns. The conversation is created before runtime setup when no `conversation_id` is provided, but messages are appended only after streaming succeeds.

Example history lookup:

```bash
curl "http://localhost:8010/conversations/$CONVERSATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### How RAG Is Intended To Work

The Accountant Agent creates a user-scoped `rag_search` tool. That tool calls the Knowledge Base Service over internal HTTP:

```http
POST http://knowledge:8003/retrieve
x-user-id: <user_id>
Content-Type: application/json
```

Payload shape:

```json
{
  "query": "VAT registration threshold",
  "user_id": "665f1f77c9e0f7a8093bb700",
  "top_k": 5,
  "include_global_tax": true,
  "include_user_documents": true
}
```

The Agent Service does not call ChromaDB directly, which matches the documented service boundary.

### How Calculator Is Intended To Work

The calculator tool accepts a simple arithmetic expression and evaluates it through a restricted Python AST walker using `Decimal`. It supports numeric constants, unary minus, addition, subtraction, multiplication, division, and exponentiation. It rejects function calls, names, strings, booleans, complex numbers, and unsupported operators.

Example tool input:

```text
100 * 0.20
```

Expected tool output:

```text
20.0
```

## 3. Findings

### Finding 1 - Tools are bound to the model but never executed

**Type:** Bug / Architecture violation  
**Severity:** High  
**Effort:** Medium

**Problem:** The runtime calls `self.llm.bind_tools(self.get_tools())`, then streams directly from `model.astream(messages)`. Binding tools only tells the model what tools are available. It does not, by itself, execute tool calls and feed tool results back into the model. The current code streams text chunks but does not inspect tool call chunks, call `rag_search` or `calculator`, append `ToolMessage`s, or continue the model loop after tool execution.

**Impact:** The documented Phase 3 tools may not actually work during chat. A model can request `rag_search` or `calculator`, but the Python tool functions will not be invoked by this runtime loop. This weakens the core Accountant Agent behavior: tax/document answers may not use the Knowledge Base, and arithmetic may be produced by the model instead of the safe calculator.

**Evidence:**

```python
# services/agent/app/runtime/base_agent.py:58-64
async def run(self, message: str, history: list[MessageSchema]) -> AsyncIterator[str]:
    model = self.llm.bind_tools(self.get_tools())
    messages = self._to_langchain_messages(history, message)
    async for chunk in model.astream(messages):
        text = _stringify_chunk_content(getattr(chunk, "content", None))
        if text:
            yield text
```

```python
# services/agent/app/runtime/accountant.py:21-25
def get_tools(self) -> list[BaseTool]:
    return [
        build_rag_search_tool(self.user_id),
        calculator,
    ]
```

**Recommendation:** Replace the direct `astream()` loop with a real tool-calling loop. Options:

- Use LangChain's tool-calling agent utilities or LangGraph.
- Or implement a small manual loop:
  1. Send messages to the model with tools bound.
  2. Detect tool calls in the AI response.
  3. Execute the matching `BaseTool`.
  4. Append tool results as `ToolMessage`s.
  5. Call the model again until a final assistant response is produced.

Streaming should still emit user-facing final tokens, and optionally internal tool-progress events if the frontend needs them later.

### Finding 2 - Failed chat setup can create empty conversations

**Type:** Bug / Inconsistency  
**Severity:** Medium  
**Effort:** Low

**Problem:** When a chat request omits `conversation_id`, the service creates a conversation before provider setup and runtime construction. If provider setup fails, for example because `OPENAI_API_KEY` is missing, the service emits an SSE `error` and returns. The newly created conversation remains in MongoDB with no messages.

**Impact:** Users can accumulate empty conversations from failed chat attempts. This also makes conversation history misleading: a conversation ID was emitted, but no user or assistant message exists under it.

**Evidence:**

```python
# services/agent/app/services/chat_service.py:45-61
else:
    conversation = await self.conversation_repo.create(
        user_id=user_id,
        agent_id=agent.id,
        first_message=payload.message,
    )
    yield sse("conversation", {"conversation_id": conversation.id})

history = conversation.messages[-settings.max_history_messages :]

try:
    provider = LLMProviderFactory.create(agent.config.provider)
    llm = provider.create_chat_model(agent.config.model, agent.config.temperature)
    runtime = create_agent_runtime(agent, llm, user_id)
except Exception as exc:
    yield sse("error", {"message": str(exc)})
    return
```

**Recommendation:** Build the provider/runtime before creating a new conversation, or persist the user message immediately when the conversation is created and mark failed turns explicitly. The simpler Phase 3 fix is to move conversation creation after provider/runtime setup.

### Finding 3 - Successful `done` can be emitted even if message persistence fails

**Type:** Bug  
**Severity:** Medium  
**Effort:** Low

**Problem:** `ConversationRepository.append_messages()` can return `None` when the conversation ID is invalid or the conversation is missing. `ChatService.stream_chat()` ignores that return value and always emits `done`.

**Impact:** In a concurrent delete or unexpected persistence failure scenario, the client may receive a successful completion even though the conversation history was not saved. This creates a mismatch between the live chat UI and persisted history.

**Evidence:**

```python
# services/agent/app/services/chat_service.py:74-87
now = datetime.now(timezone.utc)
await self.conversation_repo.append_messages(
    user_id=user_id,
    conversation_id=conversation.id,
    messages=[
        MessageSchema(role="user", content=payload.message, created_at=now),
        MessageSchema(
            role="assistant",
            content="".join(assistant_parts),
            created_at=now,
        ),
    ],
)
yield sse("done", {"conversation_id": conversation.id})
```

```python
# services/agent/app/repositories/conversation_repo.py:54-67
async def append_messages(
    self, user_id: str, conversation_id: str, messages: list[MessageSchema]
) -> ConversationInDB | None:
    if not ObjectId.is_valid(conversation_id):
        return None
    doc = await self.collection.find_one_and_update(
        {"_id": ObjectId(conversation_id), "user_id": user_id},
        {
            "$push": {"messages": {"$each": [m.model_dump(mode="python") for m in messages]}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )
    return self._to_model(doc) if doc else None
```

**Recommendation:** Check the return value from `append_messages()`. If it is `None`, emit an SSE `error` instead of `done`, and log the persistence failure with `user_id`, `agent_id`, and `conversation_id`.

### Finding 4 - Agent update cannot clear nullable fields

**Type:** Bug / API contract inconsistency  
**Severity:** Medium  
**Effort:** Low

**Problem:** `AgentUpdate` allows nullable `description` and nullable config fields, but the repository drops all `None` values from the update payload. That means a client cannot clear `description` by sending `"description": null`. It also cannot clear `config.system_prompt_override` through a partial update if the full config contains `null`.

**Impact:** The API shape implies nullable fields can be reset, but persistence silently ignores the reset. Users can set a description or prompt override but may not be able to remove it through the documented update endpoint.

**Evidence:**

```python
# services/agent/app/models/agent.py:24-27
class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    config: AgentConfig | None = None
```

```python
# services/agent/app/repositories/agent_repo.py:54-58
update = {
    k: v
    for k, v in payload.model_dump(exclude_unset=True).items()
    if v is not None
}
```

**Recommendation:** Preserve explicitly provided `None` values. Use `payload.model_dump(exclude_unset=True)` without filtering `None`, or handle nullable fields intentionally. If `config` remains a full replacement object, document that behavior and normalize provider/model defaults in update paths too.

### Finding 5 - Invalid `DEFAULT_AGENT_PROVIDER` silently falls back to OpenAI

**Type:** Missing best practice / Configuration risk  
**Severity:** Low  
**Effort:** Low

**Problem:** User-provided providers are validated by Pydantic, but the environment variable `DEFAULT_AGENT_PROVIDER` is a plain string. If it is misspelled, `_coerce_provider()` silently changes it to `"openai"`.

**Impact:** A misconfigured deployment can unexpectedly create OpenAI-backed agents instead of failing fast. That can cause runtime errors when no OpenAI key is present, or unintended external API usage.

**Evidence:**

```python
# services/agent/app/config.py:20-23
default_provider: str = Field(
    default="openai",
    validation_alias="DEFAULT_AGENT_PROVIDER",
)
```

```python
# services/agent/app/services/agent_service.py:15-18
def _coerce_provider(name: str) -> ProviderName:
    if name in _VALID_PROVIDERS:
        return cast(ProviderName, name)
    return "openai"
```

**Recommendation:** Type `default_provider` as `ProviderName` in settings or raise a startup/configuration error for invalid values. Configuration mistakes should be visible before serving traffic.

### Finding 6 - No Agent Service tests are present

**Type:** Missing best practice  
**Severity:** Medium  
**Effort:** Medium

**Problem:** No test files were found under `services/agent`. The service has meaningful behavior in user scoping, SSE sequencing, provider failure handling, tool integration, and repository updates, but there is no automated coverage in the service directory.

**Impact:** Regressions in the central chat path can slip through easily. This is especially risky because streaming behavior, tool execution, and persistence are hard to verify manually and easy to break during Phase 4 financial-tool work.

**Evidence:** Searches for `test*.py` and `*test*.py` under `services/agent` returned no files.

**Recommendation:** Add focused tests before expanding the service:

- Unit tests for `AgentService` default config normalization.
- Repository tests with a test MongoDB or mocked Motor collection.
- SSE tests for new conversation, existing conversation, missing agent, missing provider key, and persistence failure.
- Runtime tests with a fake chat model that emits tool calls.
- Tool tests for calculator safety and RAG error formatting.

## 4. What Works Well (Positive Patterns)

### Pattern 1 - Routes stay thin and delegate business logic

**Pattern:** FastAPI routes only handle request/response concerns and dependency injection. They do not access MongoDB directly.

**Why it works:** This preserves the documented layered architecture and makes the service easier to test. Business rules stay in services, persistence stays in repositories.

**Evidence:**

```python
# services/agent/app/routes/agents.py:15-22
@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[AgentService, Depends(get_agent_service)],
):
    agent = await service.create_agent(user_id, payload)
    return AgentResponse.model_validate(agent)
```

**Where else to apply:** Keep this pattern for Phase 4 invoice and expense routes. Routes should validate request shape and call services; they should not query MongoDB or LangChain tools directly.

### Pattern 2 - User scoping is consistently enforced in repositories

**Pattern:** Reads, updates, deletes, and appends include `user_id` in MongoDB filters.

**Why it works:** The service does not rely only on route-level checks. Even if a caller guesses another user's ObjectId, repository queries prevent cross-user access.

**Evidence:**

```python
# services/agent/app/repositories/agent_repo.py:45-49
async def get_by_id(self, user_id: str, agent_id: str) -> AgentInDB | None:
    if not ObjectId.is_valid(agent_id):
        return None
    doc = await self.collection.find_one({"_id": ObjectId(agent_id), "user_id": user_id})
    return self._to_model(doc) if doc else None
```

```python
# services/agent/app/repositories/conversation_repo.py:59-67
doc = await self.collection.find_one_and_update(
    {"_id": ObjectId(conversation_id), "user_id": user_id},
    {
        "$push": {"messages": {"$each": [m.model_dump(mode="python") for m in messages]}},
        "$set": {"updated_at": datetime.now(timezone.utc)},
    },
    return_document=ReturnDocument.AFTER,
)
```

**Where else to apply:** Phase 4 invoice and expense repositories should use this exact ownership pattern for every read/write path, including tool-triggered writes.

### Pattern 3 - Startup creates indexes for implemented query paths

**Pattern:** The service creates indexes for user-scoped agent listing and conversation lookup/listing during FastAPI lifespan startup.

**Why it works:** The indexes match common filters and sorts, preventing slow user-scoped list operations as data grows.

**Evidence:**

```python
# services/agent/app/utils/db.py:9-18
async def connect_db() -> None:
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.db_name]
    await db["agents"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["agents"].create_index([("user_id", ASCENDING), ("name", ASCENDING)])
    await db["conversations"].create_index(
        [("user_id", ASCENDING), ("agent_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db["conversations"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
```

**Where else to apply:** Add indexes for Phase 4 invoice/expense filters before adding their routes and LangChain tools.

### Pattern 4 - RAG respects service boundaries

**Pattern:** The Agent Service calls Knowledge Base Service `POST /retrieve`; it does not access ChromaDB directly.

**Why it works:** This keeps vector-store ownership inside the Knowledge Base Service and avoids coupling Agent Service runtime code to ChromaDB details.

**Evidence:**

```python
# services/agent/app/tools/rag.py:45-51
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(
        f"{base}/retrieve",
        json=payload,
        headers={"x-user-id": user_id},
    )
```

**Where else to apply:** Future tools should call service-layer/domain APIs, not bypass ownership by reaching into another service's data store.

### Pattern 5 - Calculator avoids unsafe evaluation

**Pattern:** The calculator parses expressions with `ast.parse()` and evaluates only a restricted subset of numeric AST nodes.

**Why it works:** It avoids `eval()` while still providing deterministic arithmetic for simple accounting calculations.

**Evidence:**

```python
# services/agent/app/tools/calculator.py:30-51
def _eval_numeric(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, bool) or isinstance(val, complex):
            raise ValueError("Unsupported literal type")
        if isinstance(val, int | float):
            return Decimal(str(val))
        raise ValueError("Unsupported literal type")
    if isinstance(node, ast.BinOp):
        left = _eval_numeric(node.left)
        right = _eval_numeric(node.right)
        try:
            return _apply_bin(node.op, left, right)
        except ArithmeticError as exc:
            raise ValueError(str(exc)) from exc
```

**Where else to apply:** Keep this defensive style for any future financial calculation tools. Avoid model-generated database queries or Python execution.

## 5. Summary - Priority Matrix

| # | Concern | Severity | Effort |
|---|---------|----------|--------|
| 1 | Tools are bound to the model but never executed | **High** | Medium |
| 2 | Failed chat setup can create empty conversations | **Medium** | Low |
| 3 | `done` can be emitted even if persistence fails | **Medium** | Low |
| 4 | Agent update cannot clear nullable fields | **Medium** | Low |
| 5 | Invalid `DEFAULT_AGENT_PROVIDER` silently falls back to OpenAI | **Low** | Low |
| 6 | No Agent Service tests are present | **Medium** | Medium |

## 6. Suggested Implementation Order

1. Fix Finding 1 first. The service's documented Phase 3 value depends on working tool calls. Implement a real tool-execution loop and add tests with a fake model/tool.
2. Fix Findings 2 and 3 together in `ChatService`. Move new conversation creation until after runtime setup, and check `append_messages()` before emitting `done`.
3. Fix Finding 4 in `AgentRepository.update()`. Preserve explicitly provided `None` values, and add tests for clearing `description` and `system_prompt_override`.
4. Fix Finding 5 by validating `DEFAULT_AGENT_PROVIDER` at settings load or startup.
5. Address Finding 6 by adding focused tests around the corrected runtime, SSE, and repository behavior before Phase 4 invoice/expense tools are added.

