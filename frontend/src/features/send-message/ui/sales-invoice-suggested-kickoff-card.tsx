"use client";

import type { SalesInvoiceWorkflowSuggestion } from "@/features/send-message/model/chat-suggestion-schema";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";

interface SalesInvoiceSuggestedKickoffCardProps {
  suggestion: SalesInvoiceWorkflowSuggestion;
  disabled?: boolean;
  onStart: () => void;
  onDismiss: () => void;
}

export function SalesInvoiceSuggestedKickoffCard({
  suggestion,
  disabled,
  onStart,
  onDismiss,
}: Readonly<SalesInvoiceSuggestedKickoffCardProps>) {
  return (
    <div className="mx-3 mb-3 mt-3">
      <Alert>
        <div className="space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-medium">Suggested workflow: inventory-backed sales invoice</p>
            <p className="text-xs text-muted-foreground">{suggestion.reason}</p>
            <p className="text-xs text-muted-foreground">
              Confidence: {Math.round(suggestion.confidence * 100)}%
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onDismiss} disabled={disabled}>
              Not now
            </Button>
            <Button type="button" onClick={onStart} disabled={disabled}>
              Review inventory-backed invoice
            </Button>
          </div>
        </div>
      </Alert>
    </div>
  );
}
