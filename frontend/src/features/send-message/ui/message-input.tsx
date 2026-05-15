"use client";

import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/shared/ui/button";
import { Spinner } from "@/shared/ui/spinner";
import { Textarea } from "@/shared/ui/textarea";

export function MessageInput({
  disabled,
  focusRequestKey,
  receiptUploadDisabled,
  receiptUploadLoading,
  salesInvoiceRequestDisabled,
  onSend,
  onReceiptSelected,
  onSalesInvoiceRequest,
}: Readonly<{
  disabled?: boolean;
  focusRequestKey?: string;
  receiptUploadDisabled?: boolean;
  receiptUploadLoading?: boolean;
  salesInvoiceRequestDisabled?: boolean;
  onSend: (message: string) => void | Promise<void>;
  onReceiptSelected?: (file: File) => void | Promise<void>;
  onSalesInvoiceRequest?: () => void | Promise<void>;
}>) {
  const [value, setValue] = useState("");
  const trimmed = useMemo(() => value.trim(), [value]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const lastFocusRequestKeyRef = useRef(focusRequestKey);
  const pendingFocusRef = useRef(false);

  useLayoutEffect(() => {
    if (focusRequestKey !== lastFocusRequestKeyRef.current) {
      lastFocusRequestKeyRef.current = focusRequestKey;
      pendingFocusRef.current = Boolean(focusRequestKey);
    }
    if (disabled || !pendingFocusRef.current) return;

    pendingFocusRef.current = false;
    textareaRef.current?.focus();
    globalThis.setTimeout(() => textareaRef.current?.focus(), 0);
  }, [disabled, focusRequestKey]);

  const submit = useCallback(async () => {
    if (disabled) return;
    if (!trimmed) return;
    const message = trimmed;
    pendingFocusRef.current = true;
    setValue("");
    textareaRef.current?.focus();
    await onSend(message);
  }, [disabled, onSend, trimmed]);

  const uploadLabel = receiptUploadLoading ? "Processing document..." : "Attach document";

  return (
    <div className="border-t bg-background p-3">
      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          hidden
          accept="application/pdf,image/png,image/jpeg,image/webp"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file && onReceiptSelected) {
              void onReceiptSelected(file);
            }
            event.currentTarget.value = "";
          }}
        />
        <Button
          type="button"
          variant="outline"
          disabled={disabled || receiptUploadDisabled || !onReceiptSelected}
          onClick={() => fileInputRef.current?.click()}
        >
          {receiptUploadLoading ? <Spinner className="mr-2" /> : null}
          {uploadLabel}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={disabled || salesInvoiceRequestDisabled || !onSalesInvoiceRequest}
          onClick={() => void onSalesInvoiceRequest?.()}
        >
          Create inventory-backed sales invoice
        </Button>
        <Textarea
          ref={textareaRef}
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

