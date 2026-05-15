"use client";

import { useEffect, useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";

import {
  createSalesInvoiceInventoryPreviewPayloadSchema,
  normalizeVatRateInput,
  type CreateSalesInvoiceInventoryPreviewInput,
} from "@/features/send-message/model/sales-invoice-workflow-schema";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

interface SalesInvoiceRequestDialogProps {
  open: boolean;
  disabled?: boolean;
  initialPayload?: CreateSalesInvoiceInventoryPreviewInput["payload"] | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: CreateSalesInvoiceInventoryPreviewInput["payload"]) => Promise<void> | void;
}

type SalesInvoiceRequestValues = CreateSalesInvoiceInventoryPreviewInput["payload"];

const CURRENCY_OPTIONS = ["EUR", "BGN", "USD"] as const;

function createDefaultValues(): SalesInvoiceRequestValues {
  return {
    partner_query: "",
    recipient: null,
    issue_date: null,
    tax_event_date: null,
    due_date: null,
    currency: "EUR",
    notes: null,
    lines: [{ description: "", query: "", quantity: "1", unit_label: "pcs", unit_price: null, vat_rate: "0.20", category: null }],
  };
}

export function SalesInvoiceRequestDialog({
  open,
  disabled,
  initialPayload,
  onOpenChange,
  onSubmit,
}: Readonly<SalesInvoiceRequestDialogProps>) {
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<SalesInvoiceRequestValues>({
    resolver: zodResolver(createSalesInvoiceInventoryPreviewPayloadSchema),
    defaultValues: useMemo(() => createDefaultValues(), []),
    mode: "onSubmit",
  });
  const lines = useFieldArray({
    control: form.control,
    name: "lines",
  });

  const isDisabled = Boolean(disabled || submitting);

  useEffect(() => {
    if (!open) return;
    if (!initialPayload) return;
    form.reset({
      ...createDefaultValues(),
      ...initialPayload,
    });
  }, [form, initialPayload, open]);

  async function handleSubmit(values: SalesInvoiceRequestValues) {
    setSubmitting(true);
    try {
      const normalized: SalesInvoiceRequestValues = {
        ...values,
        partner_query: values.partner_query?.trim() ? values.partner_query.trim() : null,
        notes: values.notes?.trim() ? values.notes.trim() : null,
        lines: values.lines.map((line) => ({
          ...line,
          vat_rate: normalizeVatRateInput(line.vat_rate),
        })),
      };
      await onSubmit(normalized);
      onOpenChange(false);
      form.reset(createDefaultValues());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create inventory-backed sales invoice</DialogTitle>
          <DialogDescription>
            Provide customer and product lines. You will review inventory matches before the invoice draft is created.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form className="space-y-4" onSubmit={form.handleSubmit(handleSubmit)}>
            <div className="grid gap-3 md:grid-cols-2">
              <FormField
                control={form.control}
                name="partner_query"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Customer</FormLabel>
                    <FormControl>
                      <Input placeholder="Acme Ltd" {...field} value={field.value ?? ""} disabled={isDisabled} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="currency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Currency</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange} disabled={isDisabled}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {CURRENCY_OPTIONS.map((currency) => (
                          <SelectItem key={currency} value={currency}>
                            {currency}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="space-y-3">
              <p className="text-sm font-medium">Invoice lines</p>
              {lines.fields.map((field, index) => (
                <div key={field.id} className="grid gap-3 rounded-md border p-3 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name={`lines.${index}.description`}
                    render={({ field: lineField }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <Input placeholder="Widget A" {...lineField} disabled={isDisabled} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`lines.${index}.query`}
                    render={({ field: lineField }) => (
                      <FormItem>
                        <FormLabel>Inventory query</FormLabel>
                        <FormControl>
                          <Input placeholder="SKU-001" {...lineField} disabled={isDisabled} />
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
                        <FormLabel>Quantity</FormLabel>
                        <FormControl>
                          <Input inputMode="decimal" {...lineField} disabled={isDisabled} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                disabled={isDisabled}
                onClick={() =>
                  lines.append({
                    description: "",
                    query: "",
                    quantity: "1",
                    unit_label: "pcs",
                    unit_price: null,
                    vat_rate: "0.20",
                    category: null,
                  })
                }
              >
                Add line
              </Button>
            </div>
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes</FormLabel>
                  <FormControl>
                    <Textarea {...field} value={field.value ?? ""} disabled={isDisabled} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isDisabled}>
                Cancel
              </Button>
              <Button type="submit" disabled={isDisabled}>
                {submitting ? "Preparing review..." : "Review inventory-backed invoice"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
