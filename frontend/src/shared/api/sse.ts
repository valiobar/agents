export type RouteMetadata = {
  predicted_route: "accountant" | "inventory" | "general";
  executed_route: "accountant" | "inventory" | "general";
  reason: string;
  confidence: number;
  company_id: string | null;
  company_scope: "assigned" | "unassigned";
};

export type InventoryMovementDraftEvent = {
  movement_draft: {
    company_id: string;
    item_id: string;
    location_id: string;
    movement_type: "receipt" | "issue" | "adjustment" | "transfer_in" | "transfer_out" | "return";
    quantity_delta: string;
    reason?: string | null;
  };
};

export type ToolTracePayload = {
  tool_name: string;
  phase: "on_tool_start" | "on_tool_end" | "on_tool_error";
  args_preview: string;
  duration_ms: number | null;
  status: "started" | "ok" | "error";
  output_bytes: number;
};

export type ChatStreamEvent =
  | { event: "conversation"; data: { conversation_id: string } }
  | { event: "start"; data: { conversation_id: string } }
  | { event: "token"; data: { content: string } }
  | { event: "route"; data: RouteMetadata }
  | { event: "inventory_movement_draft"; data: InventoryMovementDraftEvent }
  | { event: "tool_trace"; data: ToolTracePayload }
  | { event: "done"; data: { conversation_id: string } }
  | { event: "error"; data: { message: string } };

const CHAT_STREAM_EVENT_NAMES = new Set<ChatStreamEvent["event"]>([
  "conversation",
  "start",
  "token",
  "route",
  "inventory_movement_draft",
  "tool_trace",
  "done",
  "error",
]);

type SSEFrame = {
  event?: string;
  data?: string;
};

function parseSSEFrame(raw: string): SSEFrame {
  const normalized = raw.replaceAll("\r", "");
  const lines = normalized.split("\n");
  const frame: SSEFrame = {};
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) frame.event = line.slice("event:".length).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice("data:".length).trimStart());
  }
  if (dataLines.length > 0) {
    frame.data = dataLines.join("\n");
  }
  return frame;
}

export async function* streamSSE(
  url: string,
  init: RequestInit,
): AsyncGenerator<ChatStreamEvent> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "text/event-stream");
  headers.set("ngrok-skip-browser-warning", "true");

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok || !response.body) {
    throw new Error(`SSE request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
 
    for (const rawFrame of frames) {
      const { event, data } = parseSSEFrame(rawFrame);
     
      if (!event || !data) continue;
      if (!CHAT_STREAM_EVENT_NAMES.has(event as ChatStreamEvent["event"])) continue;
      yield { event, data: JSON.parse(data) } as ChatStreamEvent;
    }
  }

  const { event, data } = parseSSEFrame(buffer);
  if (event && data && CHAT_STREAM_EVENT_NAMES.has(event as ChatStreamEvent["event"])) {
    yield { event, data: JSON.parse(data) } as ChatStreamEvent;
  }
}

