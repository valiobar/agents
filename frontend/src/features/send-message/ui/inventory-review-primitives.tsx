"use client";

import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";

interface InventoryReviewWarningsProps {
  warnings: string[];
}

interface WorkflowReviewActionsProps {
  cancelLabel?: string;
  confirmLabel: string;
  disabled: boolean;
  onCancel: () => void;
}

export function InventoryReviewWarnings({ warnings }: Readonly<InventoryReviewWarningsProps>) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <Alert>
      <div className="space-y-1">
        <p className="text-sm font-medium">Please review before confirming</p>
        <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      </div>
    </Alert>
  );
}

export function WorkflowReviewActions({
  cancelLabel,
  confirmLabel,
  disabled,
  onCancel,
}: Readonly<WorkflowReviewActionsProps>) {
  return (
    <div className="flex justify-end gap-2">
      <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={disabled}>
        {cancelLabel ?? "Cancel"}
      </Button>
      <Button type="submit" size="sm" disabled={disabled}>
        {confirmLabel}
      </Button>
    </div>
  );
}
