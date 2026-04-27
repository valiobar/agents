"use client";

import { cn } from "@/shared/lib/cn";

import type { Message } from "../model/types";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-2xl whitespace-pre-wrap rounded-lg px-3 py-2 text-sm", isUser ? "bg-primary text-primary-foreground" : "bg-muted")}>
        {message.content}
      </div>
    </div>
  );
}

