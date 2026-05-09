"use client";

import { Check, X } from "lucide-react";

import type { ImportPreviewStatus } from "@/entities/inventory/model/types";
import { Button } from "@/shared/ui/button";

import { useCancelImportPreview, useConfirmImportPreview } from "../api/mutations";

export interface ImportPreviewActionsProps {
  previewId: string;
  status: ImportPreviewStatus;
  token: string;
}

export function ImportPreviewActions({
  previewId,
  status,
  token,
}: Readonly<ImportPreviewActionsProps>) {
  const confirmImportPreview = useConfirmImportPreview(previewId, token);
  const cancelImportPreview = useCancelImportPreview(previewId, token);
  const isDraft = status === "draft";
  const isMutating = confirmImportPreview.isPending || cancelImportPreview.isPending;

  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        disabled={!isDraft || isMutating}
        onClick={() => confirmImportPreview.mutate()}
      >
        <Check className="mr-1 h-3.5 w-3.5" />
        {confirmImportPreview.isPending ? "Confirming..." : "Confirm"}
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={!isDraft || isMutating}
        onClick={() => cancelImportPreview.mutate()}
      >
        <X className="mr-1 h-3.5 w-3.5" />
        {cancelImportPreview.isPending ? "Cancelling..." : "Cancel"}
      </Button>
    </div>
  );
}
