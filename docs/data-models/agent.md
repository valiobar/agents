# Agent Service Data Models

The Agent Service owns the `agents` and `conversations` MongoDB collections. Ownership is scoped by the gateway-authenticated `user_id` that arrives as `x-user-id`.

Agent records may reference a Business-owned `company_id`, but company, partner, invoice, expense, financial summary, and invoice counter models live in `business.md`. Agent validates company assignment through Business and uses Business over internal HTTP when tools need business-domain data.

## `agents` Collection

Stores user-created agent instances and provider/runtime configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. Every query filters by this field. |
| `name` | string | Yes | User-visible agent name, 1-120 characters. |
| `description` | string or null | No | Optional user-visible description, max 1000 characters. |
| `agent_type` | string | Yes | Phase 3 supports only `accountant`. |
| `company_id` | string or null | No | Optional Business-owned company assignment. Financial/partner tools require this for writes. |
| `config` | object | Yes | Provider, model, temperature, and optional system prompt override. |
| `config.provider` | string | Yes | `openai`, `anthropic`, `deepseek`, or `ollama`. |
| `config.model` | string or null | No | Provider model override. Service fills provider defaults on create when omitted. |
| `config.temperature` | number | Yes | LLM temperature, 0.0-2.0. Default is `0.2`. |
| `config.system_prompt_override` | string or null | No | Optional custom prompt, max 4000 characters. |
| `created_at` | datetime | Yes | Creation timestamp. |
| `updated_at` | datetime | Yes | Last update timestamp. |

Example document:

```json
{
  "_id": {"$oid": "665f1f77c9e0f7a8093bb711"},
  "user_id": "665f1f77c9e0f7a8093bb700",
  "name": "My Accountant",
  "description": null,
  "agent_type": "accountant",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "config": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "system_prompt_override": null
  },
  "created_at": {"$date": "2026-04-26T10:00:00Z"},
  "updated_at": {"$date": "2026-04-26T10:00:00Z"}
}
```

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, created_at DESC)` | List a user's agents newest first. |
| `(user_id ASC, company_id ASC, created_at DESC)` | Filter a user's agents by company. |
| `(user_id ASC, name ASC)` | Support user-scoped name filtering/sorting and future uniqueness checks. |

## `conversations` Collection

Stores persisted chat history for one user, one agent, and the agent's company scope at the time the conversation was created.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | MongoDB primary key. Public API exposes this as `id`. |
| `user_id` | string | Yes | Gateway-authenticated owner id. |
| `agent_id` | string | Yes | Public string id of the owning agent. |
| `company_id` | string or null | No | Business-owned company scope for this chat. The frontend loads history by `agent_id + company_id`; missing legacy values behave like `null`. |
| `title` | string or null | No | First message prefix when a conversation is created from chat. |
| `messages` | array | Yes | Ordered conversation messages. |
| `messages[].role` | string | Yes | `user`, `assistant`, `system`, or `tool`. Persisted Phase 3 chat writes `user` and `assistant`. |
| `messages[].content` | string | Yes | Message content. |
| `messages[].created_at` | datetime | Yes | Message creation timestamp. |
| `messages[].metadata` | object | Yes | Optional primitive metadata. Defaults to `{}`. |
| `created_at` | datetime | Yes | Conversation creation timestamp. |
| `updated_at` | datetime | Yes | Last message/update timestamp. |

Example document:

```json
{
  "_id": {"$oid": "665f1f77c9e0f7a8093bb722"},
  "user_id": "665f1f77c9e0f7a8093bb700",
  "agent_id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "title": "Calculate 20% VAT on 100 and explain it.",
  "messages": [
    {
      "role": "user",
      "content": "Calculate 20% VAT on 100 and explain it.",
      "created_at": {"$date": "2026-04-26T10:01:00Z"},
      "metadata": {}
    },
    {
      "role": "assistant",
      "content": "20% VAT on 100 is 20.",
      "created_at": {"$date": "2026-04-26T10:01:04Z"},
      "metadata": {}
    }
  ],
  "created_at": {"$date": "2026-04-26T10:01:00Z"},
  "updated_at": {"$date": "2026-04-26T10:01:04Z"}
}
```

Indexes created on startup:

| Index | Purpose |
|-------|---------|
| `(user_id ASC, agent_id ASC, updated_at DESC)` | List recent conversations for a user's agent. |
| `(user_id ASC, agent_id ASC, company_id ASC, updated_at DESC)` | Load the latest conversation for one agent/company scope. |
| `(user_id ASC, created_at DESC)` | User-scoped conversation lookup/listing support. |

## API Shapes

`AgentResponse`:

```json
{
  "id": "665f1f77c9e0f7a8093bb711",
  "name": "My Accountant",
  "description": null,
  "agent_type": "accountant",
  "company_id": "665f1f77c9e0f7a8093bb701",
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

`ConversationResponse`:

```json
{
  "id": "665f1f77c9e0f7a8093bb722",
  "agent_id": "665f1f77c9e0f7a8093bb711",
  "company_id": "665f1f77c9e0f7a8093bb701",
  "title": "Calculate 20% VAT on 100 and explain it.",
  "messages": [
    {
      "role": "user",
      "content": "Calculate 20% VAT on 100 and explain it.",
      "created_at": "2026-04-26T10:01:00Z",
      "metadata": {}
    }
  ],
  "created_at": "2026-04-26T10:01:00Z",
  "updated_at": "2026-04-26T10:01:04Z"
}
```

`AgentUpdate` PATCH payloads use explicit nullable semantics. Omitted fields are left unchanged, while fields sent as JSON `null` clear nullable values such as `description` and `config.system_prompt_override`. When `config` is provided, it is treated as the replacement Agent Service config object rather than a partial nested merge.

Example clearing nullable fields:

```json
{
  "description": null,
  "config": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "system_prompt_override": null
  }
}
```

`ChatRequest`:

```json
{
  "message": "Calculate 20% VAT on 100 and explain it.",
  "conversation_id": null
}
```

SSE `ChatEvent` data is serialized as `event: <name>` plus JSON `data`, for example:

```text
event: token
data: {"content":"20% VAT on 100 is 20."}
```
