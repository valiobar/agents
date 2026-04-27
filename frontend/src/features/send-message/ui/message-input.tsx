"use client";

import { useCallback, useMemo, useState } from "react";

import { Button } from "@/shared/ui/button";
import { Textarea } from "@/shared/ui/textarea";

export function MessageInput({
  disabled,
  onSend,
}: Readonly<{
  disabled?: boolean;
  onSend: (message: string) => void | Promise<void>;
}>) {
  const [value, setValue] = useState("");
  const trimmed = useMemo(() => value.trim(), [value]);

  const submit = useCallback(async () => {
    if (disabled) return;
    if (!trimmed) return;
    setValue("");
    await onSend(trimmed);
  }, [disabled, onSend, trimmed]);

  return (
    <div className="border-t bg-background p-3">
      <div className="flex items-end gap-2">
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Message your agent…"
          disabled={disabled}
          className="min-h-[44px] resize-none"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
        />
        <Button onClick={() => void submit()} disabled={disabled || !trimmed}>
          Send
        </Button>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        Press Enter to send, Shift+Enter for a new line.
      </div>
    </div>
  );
}

