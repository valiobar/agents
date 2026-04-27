export type ChatStreamEvent =
  | { event: "conversation"; data: { conversation_id: string } }
  | { event: "start"; data: { conversation_id: string } }
  | { event: "token"; data: { content: string } }
  | { event: "done"; data: { conversation_id: string } }
  | { event: "error"; data: { message: string } };

type SSEFrame = {
  event?: string;
  data?: string;
};

function parseSSEFrame(raw: string): SSEFrame {
  const lines = raw.split("\n");
  const frame: SSEFrame = {};
  for (const line of lines) {
    if (line.startsWith("event:")) frame.event = line.slice("event:".length).trim();
    if (line.startsWith("data:")) frame.data = line.slice("data:".length).trim();
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
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const rawFrame of frames) {
      const { event, data } = parseSSEFrame(rawFrame);
      if (!event || !data) continue;
      yield { event, data: JSON.parse(data) } as ChatStreamEvent;
    }
  }

  const { event, data } = parseSSEFrame(buffer);
  if (event && data) {
    yield { event, data: JSON.parse(data) } as ChatStreamEvent;
  }
}

