"use client";

import { Fragment, useEffect, useMemo, useState } from "react";

import type { ExpenseDraftFormValues } from "@/features/send-message/model/receipt-expense-schema";
import type { ImportPreviewLine, InventoryImportPreview } from "@/entities/inventory/model/types";
import { cn } from "@/shared/lib/cn";
import { ApiError } from "@/shared/api/errors";
import { Alert } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Spinner } from "@/shared/ui/spinner";

export interface SupplierInvoiceInventoryConfirmationProps {
  draft: ExpenseDraftFormValues;
  preview: InventoryImportPreview;
  disabled?: boolean;
  updatingLines?: boolean;
  confirming?: boolean;
  onCancel: () => void;
  onConfirmWithLines: (
    lines: ImportPreviewLine[],
    draft: ExpenseDraftFormValues,
  ) => void | Promise<void>;
}

export function SupplierInvoiceInventoryConfirmation({
  draft,
  preview,
  disabled,
  updatingLines = false,
  confirming = false,
  onCancel,
  onConfirmWithLines,
}: Readonly<SupplierInvoiceInventoryConfirmationProps>) {
  const [error, setError] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [editableLines, setEditableLines] = useState<ImportPreviewLine[]>(preview.lines);
  const [selectedLineIndex, setSelectedLineIndex] = useState<number | null>(
    preview.lines.length > 0 ? 0 : null,
  );
  const [editorDraft, setEditorDraft] = useState<ImportPreviewLine | null>(() => {
    if (preview.lines.length === 0) {
      return null;
    }
    return toEditorLine(preview.lines[0]);
  });
  const isDisabled = Boolean(disabled || updatingLines || confirming);
  const selectedLine = selectedLineIndex === null ? null : editableLines[selectedLineIndex] ?? null;

  useEffect(() => {
    setEditableLines(preview.lines);
    setSelectedLineIndex(preview.lines.length > 0 ? 0 : null);
    setEditorDraft(preview.lines.length > 0 ? toEditorLine(preview.lines[0]) : null);
    setEditorError(null);
  }, [preview.id, preview.updated_at, preview.lines]);

  useEffect(() => {
    if (selectedLineIndex === null) {
      setEditorDraft(null);
      return;
    }
    const nextLine = editableLines[selectedLineIndex] ?? null;
    setEditorDraft(nextLine ? toEditorLine(nextLine) : null);
    setEditorError(null);
  }, [editableLines, selectedLineIndex]);

  const editorValidationError = useMemo(() => {
    if (!editorDraft) {
      return null;
    }

    if (!editorDraft.location_id.trim()) {
      return "Location is required.";
    }

    const quantity = Number(editorDraft.receipt_quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      return "Receipt quantity must be a positive number.";
    }

    if (!editorDraft.matched_item_id) {
      const proposed = editorDraft.proposed_item ?? buildDefaultProposedItem(editorDraft, preview.company_id);
      if (!proposed.name.trim()) {
        return "Item name is required for unmatched lines.";
      }
      if (!proposed.unit.trim()) {
        return "Unit is required for unmatched lines.";
      }
    }

    return null;
  }, [editorDraft, preview.company_id]);

  const hasUnsavedChanges = useMemo(() => {
    if (!selectedLine || !editorDraft) {
      return false;
    }
    return !areLinesEqual(selectedLine, editorDraft);
  }, [editorDraft, selectedLine]);

  function buildDefaultProposedItem(line: ImportPreviewLine, companyId: string) {
    return {
      company_id: companyId,
      sku: line.candidate.sku ?? "",
      name: line.candidate.description,
      description: line.candidate.description,
      barcode: line.candidate.barcode,
      unit: line.candidate.unit ?? "pcs",
      selling_price: line.candidate.unit_price,
    };
  }

  function toEditorLine(line: ImportPreviewLine): ImportPreviewLine {
    const clonedLine: ImportPreviewLine = {
      ...line,
      candidate: { ...line.candidate },
      proposed_item: line.proposed_item ? { ...line.proposed_item } : null,
      warnings: [...line.warnings],
    };
    return clonedLine;
  }

  function areLinesEqual(left: ImportPreviewLine, right: ImportPreviewLine): boolean {
    return JSON.stringify(left) === JSON.stringify(right);
  }

  function updateEditorDraft(updater: (line: ImportPreviewLine) => ImportPreviewLine) {
    setEditorDraft((currentLine) => {
      if (!currentLine) {
        return currentLine;
      }
      return updater(currentLine);
    });
    setEditorError(null);
  }

  function trySelectRow(nextIndex: number) {
    if (nextIndex === selectedLineIndex) {
      return;
    }
    if (hasUnsavedChanges) {
      setEditorError("Apply or discard current line changes before switching lines.");
      return;
    }
    setSelectedLineIndex(nextIndex);
  }

  function applySelectedLineEdits(): boolean {
    if (selectedLineIndex === null || !editorDraft) {
      return true;
    }
    if (editorValidationError) {
      setEditorError(editorValidationError);
      return false;
    }
    setEditableLines((currentLines) =>
      currentLines.map((line, index) => (index === selectedLineIndex ? editorDraft : line)),
    );
    setEditorError(null);
    return true;
  }

  function discardSelectedLineEdits() {
    if (!selectedLine) {
      return;
    }
    setEditorDraft(toEditorLine(selectedLine));
    setEditorError(null);
  }

  async function handleConfirm() {
    setError(null);
    setEditorError(null);

    if (hasUnsavedChanges) {
      setEditorError("Apply or discard current line changes before confirming inventory.");
      return;
    }

    if (editorValidationError) {
      setEditorError(editorValidationError);
      return;
    }

    try {
      await onConfirmWithLines(editableLines, draft);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to confirm inventory import. Please try again.");
    }
  }

  let confirmButtonLabel = "Confirm inventory";
  if (confirming) {
    confirmButtonLabel = "Confirming inventory...";
  } else if (updatingLines) {
    confirmButtonLabel = "Saving lines...";
  }

  return (
    <Card className="mx-3 mb-3 mt-3 flex max-h-[min(60vh,34rem)] flex-col overflow-hidden shadow-none">
      <CardHeader className="space-y-0.5 px-4 py-3">
        <div className="text-sm font-medium">Review inventory import</div>
        <div className="text-xs text-muted-foreground">
          Confirm inventory lines first. Expense details will be reviewed next.
        </div>
      </CardHeader>
      <CardContent className="space-y-3 overflow-y-auto px-4 pb-0 pt-0">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Preview {preview.id.slice(-8)}</span>
          <Badge variant="outline">{preview.status}</Badge>
          <span>Lines: {preview.lines.length}</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-2">Description</th>
                <th className="pb-2">SKU</th>
                <th className="pb-2 text-right">Qty</th>
                <th className="pb-2">Match</th>
                <th className="pb-2">Warnings</th>
              </tr>
            </thead>
            <tbody>
              {editableLines.map((line, index) => {
                let matchBadge = (
                  <Badge variant="outline" className="border-destructive/40 text-destructive">
                    Unmatched
                  </Badge>
                );
                if (line.matched_item_id) {
                  matchBadge = <Badge>Matched</Badge>;
                } else if (line.proposed_item) {
                  matchBadge = <Badge variant="outline">New item</Badge>;
                }

                return (
                  <Fragment key={`${preview.id}:${index}`}>
                    <tr
                      className={cn(
                        "cursor-pointer border-b transition-colors",
                        selectedLineIndex === index ? "bg-muted/40" : "hover:bg-muted/20",
                      )}
                      onClick={() => trySelectRow(index)}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter" && event.key !== " ") {
                          return;
                        }
                        event.preventDefault();
                        trySelectRow(index);
                      }}
                      tabIndex={0}
                    >
                      <td className="py-2">{line.candidate.description}</td>
                      <td className="py-2 font-mono">{line.candidate.sku ?? "-"}</td>
                      <td className="py-2 text-right font-mono">{line.receipt_quantity}</td>
                      <td className="py-2">{matchBadge}</td>
                      <td className="py-2">
                        {line.warnings.length > 0 ? (
                          <span className="text-xs text-destructive">{line.warnings.join("; ")}</span>
                        ) : (
                          <span className="text-xs text-muted-foreground">None</span>
                        )}
                      </td>
                    </tr>
                    {selectedLineIndex === index && editorDraft ? (
                      <tr className="border-b">
                        <td colSpan={5} className="p-0">
                          <div className="space-y-3 bg-muted/20 px-3 py-3">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm font-medium">Editing line {index + 1}</p>
                              {editorDraft.matched_item_id ? (
                                <Badge>Matched item movement</Badge>
                              ) : (
                                <Badge variant="outline">Unmatched item details</Badge>
                              )}
                            </div>

                            {editorDraft.matched_item_id ? (
                              <div className="grid gap-3 md:grid-cols-2">
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Item ID</p>
                                  <Input aria-label="Matched item ID" value={editorDraft.matched_item_id} readOnly />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Location ID</p>
                                  <Input
                                    aria-label="Matched line location ID"
                                    value={editorDraft.location_id}
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => ({
                                        ...currentLine,
                                        location_id: event.target.value,
                                      }))
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Receipt quantity</p>
                                  <Input
                                    aria-label="Matched line receipt quantity"
                                    value={editorDraft.receipt_quantity}
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => ({
                                        ...currentLine,
                                        receipt_quantity: event.target.value,
                                      }))
                                    }
                                  />
                                </div>
                              </div>
                            ) : (
                              <div className="grid gap-3 md:grid-cols-2">
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Item name</p>
                                  <Input
                                    aria-label="Unmatched line item name"
                                    value={
                                      (editorDraft.proposed_item ?? buildDefaultProposedItem(editorDraft, preview.company_id))
                                        .name
                                    }
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => {
                                        const base =
                                          currentLine.proposed_item ??
                                          buildDefaultProposedItem(currentLine, preview.company_id);
                                        return {
                                          ...currentLine,
                                          proposed_item: { ...base, name: event.target.value },
                                        };
                                      })
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">SKU</p>
                                  <Input
                                    aria-label="Unmatched line SKU"
                                    value={
                                      (editorDraft.proposed_item ?? buildDefaultProposedItem(editorDraft, preview.company_id))
                                        .sku
                                    }
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => {
                                        const base =
                                          currentLine.proposed_item ??
                                          buildDefaultProposedItem(currentLine, preview.company_id);
                                        return {
                                          ...currentLine,
                                          proposed_item: { ...base, sku: event.target.value },
                                        };
                                      })
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Unit</p>
                                  <Input
                                    aria-label="Unmatched line unit"
                                    value={
                                      (editorDraft.proposed_item ?? buildDefaultProposedItem(editorDraft, preview.company_id))
                                        .unit
                                    }
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => {
                                        const base =
                                          currentLine.proposed_item ??
                                          buildDefaultProposedItem(currentLine, preview.company_id);
                                        return {
                                          ...currentLine,
                                          proposed_item: { ...base, unit: event.target.value },
                                        };
                                      })
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Barcode</p>
                                  <Input
                                    aria-label="Unmatched line barcode"
                                    value={
                                      (editorDraft.proposed_item ?? buildDefaultProposedItem(editorDraft, preview.company_id))
                                        .barcode ?? ""
                                    }
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => {
                                        const base =
                                          currentLine.proposed_item ??
                                          buildDefaultProposedItem(currentLine, preview.company_id);
                                        return {
                                          ...currentLine,
                                          proposed_item: {
                                            ...base,
                                            barcode: event.target.value.trim() ? event.target.value : null,
                                          },
                                        };
                                      })
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Selling price</p>
                                  <Input
                                    aria-label="Unmatched line selling price"
                                    value={
                                      (editorDraft.proposed_item ?? buildDefaultProposedItem(editorDraft, preview.company_id))
                                        .selling_price ?? ""
                                    }
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => {
                                        const base =
                                          currentLine.proposed_item ??
                                          buildDefaultProposedItem(currentLine, preview.company_id);
                                        return {
                                          ...currentLine,
                                          proposed_item: {
                                            ...base,
                                            selling_price: event.target.value.trim() ? event.target.value : null,
                                          },
                                        };
                                      })
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Location ID</p>
                                  <Input
                                    aria-label="Unmatched line location ID"
                                    value={editorDraft.location_id}
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => ({
                                        ...currentLine,
                                        location_id: event.target.value,
                                      }))
                                    }
                                  />
                                </div>
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground">Receipt quantity</p>
                                  <Input
                                    aria-label="Unmatched line receipt quantity"
                                    value={editorDraft.receipt_quantity}
                                    onChange={(event) =>
                                      updateEditorDraft((currentLine) => ({
                                        ...currentLine,
                                        receipt_quantity: event.target.value,
                                      }))
                                    }
                                  />
                                </div>
                              </div>
                            )}

                            <div className="flex items-center justify-end gap-2">
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={isDisabled || !hasUnsavedChanges}
                                onClick={discardSelectedLineEdits}
                              >
                                Discard changes
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                disabled={isDisabled || !hasUnsavedChanges}
                                onClick={applySelectedLineEdits}
                              >
                                Apply changes
                              </Button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {editorError ? <Alert variant="destructive">{editorError}</Alert> : null}
        {hasUnsavedChanges ? (
          <p className="text-xs text-muted-foreground">Apply or discard selected line changes before confirming.</p>
        ) : null}

        {error ? <Alert variant="destructive">{error}</Alert> : null}
      </CardContent>
      <CardFooter className="sticky bottom-0 mt-3 bg-card/95 px-4 pb-3 pt-3 backdrop-blur">
        <div className="flex w-full items-center justify-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={isDisabled}>
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={isDisabled || hasUnsavedChanges || Boolean(editorValidationError)}
            onClick={() => void handleConfirm()}
          >
            {confirming || updatingLines ? <Spinner className="mr-2 h-3 w-3" /> : null}
            {confirmButtonLabel}
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
