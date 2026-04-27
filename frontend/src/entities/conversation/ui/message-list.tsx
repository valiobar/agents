"use client";

import type { Message } from "../model/types";
import { MessageBubble } from "./message-bubble";

export function MessageList({
  messages,
  streamingContent,
}: Readonly<{
  messages: Message[];
  streamingContent?: string;
}>) {
  return (
    <div className="flex flex-col gap-3">
      {messages.map((m, idx) => (
        // Messages don't have stable ids (yet); index is acceptable for read-only history rendering.
        <MessageBubble key={`${m.created_at}-${m.role}-${idx}`} message={m} />
      ))}
      {streamingContent ? (
        <MessageBubble
          message={{
            role: "assistant",
            content: streamingContent,
            created_at: new Date().toISOString(),
            metadata: {},
          }}
        />
      ) : null}
    </div>
  );
}

