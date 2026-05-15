"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { invoiceCreateSchema, type InvoiceCreate } from "@/entities/invoice/model/types";
import type { SalesInvoiceReview } from "@/features/send-message/model/sales-invoice-workflow-schema";
import { ApiError } from "@/shared/api/errors";
import { Alert } from "@/shared/ui/alert";
import { Card, CardContent, CardFooter, CardHeader } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";
import { Textarea } from "@/shared/ui/textarea";

import { InventoryReviewWarnings, WorkflowReviewActions } from "./inventory-review-primitives";

interface SalesInvoiceDraftConfirmationProps {
  review: SalesInvoiceReview;
  disabled?: boolean;
  confirming?: boolean;
  confirmed?: boolean;
  onCancel: () => void;
  onConfirm: (invoiceDraft: InvoiceCreate) => void | Promise<void>;
}

const INVOICE_STATUS_OPTIONS: InvoiceCreate["status"][] = ["draft", "sent", "paid", "overdue", "cancelled"];
const CURRENCY_OPTIONS: InvoiceCreate["currency"][] = ["EUR", "BGN", "USD"];

export function SalesInvoiceDraftConfirmation({
  review,
  disabled,
  confirming = false,
  confirmed = false,
  onCancel,
  onConfirm,
}: Readonly<SalesInvoiceDraftConfirmationProps>) {
  const [error, setError] = useState<string | null>(null);
  const defaultValues = useMemo(() => review.invoice_draft, [review]);
  const form = useForm<InvoiceCreate>({
    resolver: zodResolver(invoiceCreateSchema),
    defaultValues,
    mode: "onSubmit",
  });
  const items = useFieldArray({
    control: form.control,
    name: "items",
  });
  const isDisabled = Boolean(disabled || confirming || confirmed);

  async function handleSubmit(values: InvoiceCreate) {
    setError(null);
    try {
      await onConfirm(values);
      form.reset(values);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to create sales invoice. Please try again.");
    }
  }

  return (
    <Card
      className={`mx-3 mb-3 mt-3 flex max-h-[min(60vh,34rem)] flex-col overflow-hidden shadow-none ${
        confirmed ? "border-green-200 dark:border-green-800" : ""
      }`}
    >
      <CardHeader className="space-y-0.5 px-4 py-3">
        <div className="text-sm font-medium">{confirmed ? "Sales invoice created" : "Review sales invoice draft"}</div>
        <div className="text-xs text-muted-foreground">Validate invoice details before creating the draft invoice.</div>
      </CardHeader>
      <CardContent className="space-y-3 overflow-y-auto px-4 pb-0 pt-0">
        <InventoryReviewWarnings warnings={[...review.inventory_warnings, ...review.partner_warnings]} />
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <FormField
                control={form.control}
                name="counterparty"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Counterparty</FormLabel>
                    <FormControl>
                      <Input
                        className="h-8 text-sm"
                        disabled={isDisabled}
                        value={field.value ?? ""}
                        onChange={(event) => field.onChange(event.target.value || null)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="partner_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Partner ID</FormLabel>
                    <FormControl>
                      <Input
                        className="h-8 text-sm"
                        disabled={isDisabled}
                        value={field.value ?? ""}
                        onChange={(event) => field.onChange(event.target.value || null)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="issue_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Issue date</FormLabel>
                    <FormControl>
                      <Input className="h-8 text-sm" type="date" disabled={isDisabled} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="tax_event_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Tax event date</FormLabel>
                    <FormControl>
                      <Input className="h-8 text-sm" type="date" disabled={isDisabled} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="due_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Due date</FormLabel>
                    <FormControl>
                      <Input
                        className="h-8 text-sm"
                        type="date"
                        disabled={isDisabled}
                        value={field.value ?? ""}
                        onChange={(event) => field.onChange(event.target.value || null)}
                      />
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
                    <FormLabel className="text-xs">Currency</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange} disabled={isDisabled}>
                      <FormControl>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue placeholder="Select currency" />
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
              <FormField
                control={form.control}
                name="status"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Status</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange} disabled={isDisabled}>
                      <FormControl>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue placeholder="Select status" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {INVOICE_STATUS_OPTIONS.map((status) => (
                          <SelectItem key={status} value={status}>
                            {status}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">Notes</FormLabel>
                  <FormControl>
                    <Textarea
                      className="min-h-[56px] text-sm"
                      disabled={isDisabled}
                      value={field.value ?? ""}
                      onChange={(event) => field.onChange(event.target.value || null)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="space-y-3 border-t pt-3">
              <p className="text-sm font-medium">Line items</p>
              {items.fields.map((item, index) => (
                <div key={item.id} className="grid gap-3 rounded-md border p-3 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name={`items.${index}.description`}
                    render={({ field }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel className="text-xs">Description</FormLabel>
                        <FormControl>
                          <Input className="h-8 text-sm" disabled={isDisabled} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`items.${index}.quantity`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">Quantity</FormLabel>
                        <FormControl>
                          <Input className="h-8 text-sm" disabled={isDisabled} inputMode="decimal" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`items.${index}.unit_label`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">Unit</FormLabel>
                        <FormControl>
                          <Input className="h-8 text-sm" disabled={isDisabled} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`items.${index}.unit_price`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">Unit price</FormLabel>
                        <FormControl>
                          <Input className="h-8 text-sm" disabled={isDisabled} inputMode="decimal" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`items.${index}.vat_rate`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">VAT rate</FormLabel>
                        <FormControl>
                          <Input className="h-8 text-sm" disabled={isDisabled} inputMode="decimal" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`items.${index}.category`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">Category</FormLabel>
                        <FormControl>
                          <Input
                            className="h-8 text-sm"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(event) => field.onChange(event.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              ))}
            </div>

            {error ? <Alert variant="destructive">{error}</Alert> : null}

            {confirmed ? null : (
              <CardFooter className="sticky bottom-0 -mx-4 bg-card/95 px-4 pb-3 pt-3 backdrop-blur">
                <div className="w-full">
                  <WorkflowReviewActions
                    confirmLabel={confirming ? "Creating sales invoice..." : "Create draft invoice"}
                    disabled={isDisabled}
                    onCancel={onCancel}
                  />
                  {confirming ? (
                    <div className="mt-2 flex items-center justify-end text-xs text-muted-foreground">
                      <Spinner className="mr-2 h-3 w-3" />
                      Finalizing invoice draft...
                    </div>
                  ) : null}
                </div>
              </CardFooter>
            )}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
