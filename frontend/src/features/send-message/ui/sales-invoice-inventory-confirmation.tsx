"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";

import type { ConfirmSalesInvoiceInventoryPayload, SalesInvoiceInventoryReview } from "@/features/send-message/model/sales-invoice-workflow-schema";
import {
  confirmSalesInvoiceInventoryPayloadSchema,
  createSalesInvoiceInventoryPreviewPayloadSchema,
  normalizeVatRateInput,
} from "@/features/send-message/model/sales-invoice-workflow-schema";
import { ApiError } from "@/shared/api/errors";
import { Alert } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardFooter, CardHeader } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";

import { InventoryReviewWarnings, WorkflowReviewActions } from "./inventory-review-primitives";

interface SalesInvoiceInventoryConfirmationProps {
  review: SalesInvoiceInventoryReview;
  disabled?: boolean;
  confirming?: boolean;
  onCancel: () => void;
  onConfirm: (values: ConfirmSalesInvoiceInventoryPayload) => void | Promise<void>;
}

function toFormValues(review: SalesInvoiceInventoryReview): ConfirmSalesInvoiceInventoryPayload {
  return {
    source_preview: {
      partner_query: review.partner_query,
      recipient: review.recipient,
      currency: "EUR",
      lines: review.lines.map((line) => line.requested),
    },
    selected_partner_id: review.partner_candidates[0]?.partner.id ?? null,
    recipient: review.recipient,
    lines: review.lines.map((line) => {
      const inventoryItemId = line.selected_item_id ?? line.candidates[0]?.item_id ?? "";
      const defaultStockLevel = line.stock_levels.find((stockLevel) => stockLevel.item_id === inventoryItemId) ?? null;
      return {
        line_index: line.line_index,
        description: line.requested.description,
        quantity: line.requested.quantity,
        unit_label: line.requested.unit_label ?? line.candidates[0]?.unit ?? "pcs",
        unit_price: line.requested.unit_price ?? line.candidates[0]?.selling_price ?? "0.00",
        vat_rate: normalizeVatRateInput(line.requested.vat_rate) ?? "0.20",
        category: line.requested.category ?? null,
        inventory_item_id: inventoryItemId,
        inventory_location_id: line.selected_location_id ?? defaultStockLevel?.location_id ?? "",
        stock_quantity: line.available_quantity ?? defaultStockLevel?.available_quantity ?? null,
      };
    }),
  };
}

function asNumber(value: string | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoney(value: number): string {
  return value.toFixed(2);
}

function calculateTotals(lines: ConfirmSalesInvoiceInventoryPayload["lines"]) {
  return lines.reduce(
    (totals, line) => {
      const subtotal = asNumber(line.quantity) * asNumber(line.unit_price);
      const vat = subtotal * asNumber(normalizeVatRateInput(line.vat_rate));
      return {
        subtotal: totals.subtotal + subtotal,
        vat: totals.vat + vat,
        total: totals.total + subtotal + vat,
      };
    },
    { subtotal: 0, vat: 0, total: 0 },
  );
}

export function SalesInvoiceInventoryConfirmation({
  review,
  disabled,
  confirming = false,
  onCancel,
  onConfirm,
}: Readonly<SalesInvoiceInventoryConfirmationProps>) {
  const [error, setError] = useState<string | null>(null);
  const defaultValues = useMemo(() => toFormValues(review), [review]);
  const form = useForm<ConfirmSalesInvoiceInventoryPayload>({
    resolver: zodResolver(confirmSalesInvoiceInventoryPayloadSchema),
    defaultValues,
    mode: "onSubmit",
  });
  const lines = useFieldArray({
    control: form.control,
    name: "lines",
  });
  const watchedLines = useWatch({ control: form.control, name: "lines" }) ?? defaultValues.lines;
  const totals = useMemo(() => calculateTotals(watchedLines), [watchedLines]);

  const isDisabled = Boolean(disabled || confirming);

  function handleInventoryItemChange(
    index: number,
    lineReview: SalesInvoiceInventoryReview["lines"][number] | undefined,
    onChange: (value: string) => void,
    value: string,
  ) {
    onChange(value);
    const candidate = lineReview?.candidates.find((item) => item.item_id === value);
    const nextStockLevel = lineReview?.stock_levels.find((level) => level.item_id === value);
    form.setValue(`lines.${index}.unit_label`, candidate?.unit ?? "pcs");
    form.setValue(`lines.${index}.unit_price`, candidate?.selling_price ?? "0.00");
    form.setValue(`lines.${index}.inventory_location_id`, nextStockLevel?.location_id ?? "");
    form.setValue(`lines.${index}.stock_quantity`, nextStockLevel?.available_quantity ?? null);
  }

  function handleLocationChange(
    index: number,
    stockLevels: SalesInvoiceInventoryReview["lines"][number]["stock_levels"],
    onChange: (value: string) => void,
    value: string,
  ) {
    onChange(value);
    const stockLevel = stockLevels.find((level) => level.location_id === value);
    form.setValue(`lines.${index}.stock_quantity`, stockLevel?.available_quantity ?? null);
  }

  async function handleSubmit(values: ConfirmSalesInvoiceInventoryPayload) {
    setError(null);
    try {
      const normalized = {
        ...values,
        source_preview: createSalesInvoiceInventoryPreviewPayloadSchema.parse({
          ...values.source_preview,
          lines: values.source_preview.lines.map((line) => ({
            ...line,
            vat_rate: normalizeVatRateInput(line.vat_rate),
          })),
        }),
        lines: values.lines.map((line) => ({
          ...line,
          vat_rate: normalizeVatRateInput(line.vat_rate) ?? "0.20",
        })),
      };
      await onConfirm(normalized);
      form.reset(values);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to confirm inventory lines. Please try again.");
    }
  }

  return (
    <Card className="mx-3 mb-3 mt-3 flex max-h-[min(60vh,34rem)] flex-col overflow-hidden shadow-none">
      <CardHeader className="space-y-0.5 px-4 py-3">
        <div className="text-sm font-medium">Review sales invoice inventory lines</div>
        <div className="text-xs text-muted-foreground">Adjust selected items and locations before drafting the invoice.</div>
      </CardHeader>
      <CardContent className="space-y-3 overflow-y-auto px-4 pb-0 pt-0">
        <InventoryReviewWarnings warnings={review.warnings} />
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-3">
            {review.partner_candidates.length > 0 ? (
              <FormField
                control={form.control}
                name="selected_partner_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Customer match</FormLabel>
                    <Select
                      value={field.value ?? "__none__"}
                      onValueChange={(value) => field.onChange(value === "__none__" ? null : value)}
                      disabled={isDisabled}
                    >
                      <FormControl>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue placeholder="Select partner match" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="__none__">No partner match</SelectItem>
                        {review.partner_candidates.map((candidate) => (
                          <SelectItem key={candidate.partner.id} value={candidate.partner.id}>
                            {candidate.partner.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            <div className="space-y-3">
              {lines.fields.map((field, index) => {
                const lineReview = review.lines[index];
                const selectedItemId = watchedLines[index]?.inventory_item_id ?? "";
                const selectedCandidate = lineReview?.candidates.find((candidate) => candidate.item_id === selectedItemId);
                const stockLevels = (lineReview?.stock_levels ?? []).filter(
                  (stockLevel) => stockLevel.item_id === selectedItemId,
                );
                return (
                  <div key={field.id} className="space-y-3 rounded-md border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">Line {index + 1}</p>
                      <Badge variant="outline">{lineReview?.requested.description ?? "Item"}</Badge>
                    </div>
                    {lineReview?.warnings.length ? (
                      <Alert>
                        <ul className="list-disc space-y-1 pl-5 text-xs">
                          {lineReview.warnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      </Alert>
                    ) : null}
                    <div className="grid gap-3 md:grid-cols-2">
                      <FormField
                        control={form.control}
                        name={`lines.${index}.description`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Description</FormLabel>
                            <FormControl>
                              <Input className="h-8 text-sm" disabled={isDisabled} {...lineField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.category`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Category</FormLabel>
                            <FormControl>
                              <Input
                                className="h-8 text-sm"
                                disabled={isDisabled}
                                value={lineField.value ?? ""}
                                onChange={(event) => lineField.onChange(event.target.value || null)}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.quantity`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Quantity</FormLabel>
                            <FormControl>
                              <Input className="h-8 text-sm" disabled={isDisabled} inputMode="decimal" {...lineField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.unit_label`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Unit</FormLabel>
                            <FormControl>
                              <Input className="h-8 text-sm" disabled={isDisabled} {...lineField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.unit_price`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Unit price</FormLabel>
                            <FormControl>
                              <Input className="h-8 text-sm" disabled={isDisabled} inputMode="decimal" {...lineField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.vat_rate`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">VAT rate</FormLabel>
                            <FormControl>
                              <Input className="h-8 text-sm" disabled={isDisabled} inputMode="decimal" {...lineField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.inventory_item_id`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Inventory item</FormLabel>
                            <Select
                              value={lineField.value}
                              onValueChange={(value) => handleInventoryItemChange(index, lineReview, lineField.onChange, value)}
                              disabled={isDisabled}
                            >
                              <FormControl>
                                <SelectTrigger className="h-8 text-sm">
                                  <SelectValue placeholder="Select inventory item" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {(lineReview?.candidates ?? []).map((candidate) => (
                                  <SelectItem key={candidate.item_id} value={candidate.item_id}>
                                    {candidate.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`lines.${index}.inventory_location_id`}
                        render={({ field: lineField }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Location</FormLabel>
                            <Select
                              value={lineField.value}
                              onValueChange={(value) => handleLocationChange(index, stockLevels, lineField.onChange, value)}
                              disabled={isDisabled}
                            >
                              <FormControl>
                                <SelectTrigger className="h-8 text-sm">
                                  <SelectValue placeholder="Select location" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {stockLevels.map((stockLevel) => (
                                  <SelectItem key={stockLevel.location_id} value={stockLevel.location_id}>
                                    {stockLevel.location_name} ({stockLevel.available_quantity} {stockLevel.unit})
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {selectedCandidate && stockLevels.length === 0 ? (
                              <p className="text-xs text-muted-foreground">
                                No stock locations are available for {selectedCandidate.name}.
                              </p>
                            ) : null}
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="ml-auto grid max-w-sm grid-cols-2 gap-x-6 gap-y-1 rounded-md border bg-muted/30 p-3 text-sm">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="text-right font-medium">{formatMoney(totals.subtotal)}</span>
              <span className="text-muted-foreground">VAT</span>
              <span className="text-right font-medium">{formatMoney(totals.vat)}</span>
              <span className="text-muted-foreground">Total</span>
              <span className="text-right font-semibold">{formatMoney(totals.total)}</span>
            </div>

            {error ? <Alert variant="destructive">{error}</Alert> : null}
            <CardFooter className="sticky bottom-0 -mx-4 bg-card/95 px-4 pb-3 pt-3 backdrop-blur">
              <div className="w-full">
                <WorkflowReviewActions
                  confirmLabel={confirming ? "Preparing invoice draft..." : "Continue to invoice draft"}
                  disabled={isDisabled}
                  onCancel={onCancel}
                />
                {confirming ? (
                  <div className="mt-2 flex items-center justify-end text-xs text-muted-foreground">
                    <Spinner className="mr-2 h-3 w-3" />
                    Processing confirmed inventory selections...
                  </div>
                ) : null}
              </div>
            </CardFooter>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
