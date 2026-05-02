"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/shared/api/errors";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";
import { Textarea } from "@/shared/ui/textarea";

import { expenseDraftConfirmationSchema, type ExpenseDraftFormValues } from "../model/receipt-expense-schema";

export interface ExpenseDraftConfirmationProps {
  draft: ExpenseDraftFormValues;
  disabled?: boolean;
  confirming?: boolean;
  confirmed?: boolean;
  onCancel: () => void;
  onConfirm: (values: ExpenseDraftFormValues) => void | Promise<void>;
}

const CURRENCIES: Array<ExpenseDraftFormValues["currency"]> = ["EUR", "BGN", "USD"];

const CATEGORY_LABELS: Record<ExpenseDraftFormValues["category"], string> = {
  office: "Office",
  travel: "Travel",
  meals: "Meals",
  software: "Software",
  rent: "Rent",
  utilities: "Utilities",
  professional_services: "Professional services",
  tax: "Tax",
  payroll: "Payroll",
  other: "Other",
};

const FIELD_CLASS = "space-y-1";
const LABEL_CLASS = "text-xs";
const CONTROL_CLASS = "h-8 text-sm";
const TEXTAREA_CLASS = "min-h-[56px] text-sm";
const DOCUMENT_TYPE_CONFIDENCE_THRESHOLD = 0.75;

function emptyVendorPartner(counterparty: string): NonNullable<ExpenseDraftFormValues["vendor_partner"]> {
  return {
    name: counterparty,
    registration_number: null,
    vat_number: null,
    city: null,
    country: "Bulgaria",
    address: null,
    accountable_person: null,
    email: null,
    phone: null,
    confidence: 0,
    warnings: ["Supplier details were added manually after changing the document type."],
  };
}

export function ExpenseDraftConfirmation({
  draft,
  disabled,
  confirming = false,
  confirmed = false,
  onCancel,
  onConfirm,
}: Readonly<ExpenseDraftConfirmationProps>) {
  const [error, setError] = useState<string | null>(null);
  const [isDocumentTypeConfirmed, setIsDocumentTypeConfirmed] = useState(
    draft.confidence >= DOCUMENT_TYPE_CONFIDENCE_THRESHOLD,
  );

  const defaultValues = useMemo(() => draft, [draft]);

  const form = useForm<ExpenseDraftFormValues>({
    resolver: zodResolver(expenseDraftConfirmationSchema),
    defaultValues,
    mode: "onSubmit",
  });
  const isDisabled = Boolean(disabled || confirming || confirmed);

  const deductible = form.watch("deductible");
  const sourceDocumentType = form.watch("source_document_type");
  const requiresDocumentTypeConfirmation = draft.confidence < DOCUMENT_TYPE_CONFIDENCE_THRESHOLD;
  const canSubmit = !requiresDocumentTypeConfirmation || isDocumentTypeConfirmed;

  useEffect(() => {
    setIsDocumentTypeConfirmed(draft.confidence >= DOCUMENT_TYPE_CONFIDENCE_THRESHOLD);
  }, [draft]);

  async function handleSubmit(values: ExpenseDraftFormValues) {
    setError(null);
    try {
      await onConfirm(values);
      form.reset(values);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to confirm extracted expense. Please try again.");
    }
  }

  return (
    <Card className={`mx-3 mb-3 mt-3 flex max-h-[min(60vh,34rem)] flex-col overflow-hidden shadow-none ${confirmed ? "border-green-200 dark:border-green-800" : ""}`}>
      <CardHeader className="space-y-0.5 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          {confirmed ? "Expense recorded" : "Review extracted expense"}
          {confirmed ? (
            <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
              Confirmed
            </span>
          ) : null}
        </div>
        {confirmed ? null : (
          <div className="text-xs text-muted-foreground">Edit only what looks wrong, then confirm.</div>
        )}
      </CardHeader>
      <CardContent className="overflow-y-auto px-4 pb-0 pt-0">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="counterparty"
                render={({ field }) => (
                  <FormItem className={`sm:col-span-2 ${FIELD_CLASS}`}>
                    <FormLabel className={LABEL_CLASS}>Counterparty</FormLabel>
                    <FormControl>
                      <Input className={CONTROL_CLASS} autoComplete="off" disabled={isDisabled} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="source_document_type"
                render={({ field }) => (
                  <FormItem className={FIELD_CLASS}>
                    <FormLabel className={LABEL_CLASS}>Document type</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={(value) => {
                        const nextType = value as ExpenseDraftFormValues["source_document_type"];
                        field.onChange(nextType);
                        if (requiresDocumentTypeConfirmation) {
                          setIsDocumentTypeConfirmed(false);
                        }
                        if (nextType === "invoice" && !form.getValues("vendor_partner")) {
                          form.setValue("vendor_partner", emptyVendorPartner(form.getValues("counterparty")), {
                            shouldDirty: true,
                            shouldValidate: false,
                          });
                        }
                        if (nextType === "receipt") {
                          form.setValue("vendor_partner", null, {
                            shouldDirty: true,
                            shouldValidate: false,
                          });
                        }
                      }}
                      disabled={isDisabled}
                    >
                      <FormControl>
                        <SelectTrigger className={CONTROL_CLASS}>
                          <SelectValue placeholder="Select document type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="receipt">Receipt</SelectItem>
                        <SelectItem value="invoice">Invoice</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="expense_date"
                render={({ field }) => (
                  <FormItem className={FIELD_CLASS}>
                    <FormLabel className={LABEL_CLASS}>Date</FormLabel>
                    <FormControl>
                      <Input className={CONTROL_CLASS} type="date" disabled={isDisabled} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="currency"
                render={({ field }) => (
                  <FormItem className={FIELD_CLASS}>
                    <FormLabel className={LABEL_CLASS}>Currency</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange} disabled={isDisabled}>
                      <FormControl>
                        <SelectTrigger className={CONTROL_CLASS}>
                          <SelectValue placeholder="Select currency" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {CURRENCIES.map((c) => (
                          <SelectItem key={c} value={c}>
                            {c}
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
                name="amount"
                render={({ field }) => (
                  <FormItem className={FIELD_CLASS}>
                    <FormLabel className={LABEL_CLASS}>Amount</FormLabel>
                    <FormControl>
                      <Input
                        className={CONTROL_CLASS}
                        inputMode="decimal"
                        autoComplete="off"
                        disabled={isDisabled}
                        value={field.value ?? ""}
                        onChange={(e) => field.onChange(e.target.value || null)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem className={FIELD_CLASS}>
                    <FormLabel className={LABEL_CLASS}>Category</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange} disabled={isDisabled}>
                      <FormControl>
                        <SelectTrigger className={CONTROL_CLASS}>
                          <SelectValue placeholder="Select category" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
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
              name="source_document_number"
              render={({ field }) => (
                <FormItem className={FIELD_CLASS}>
                  <FormLabel className={LABEL_CLASS}>Document number</FormLabel>
                  <FormControl>
                    <Input
                      className={CONTROL_CLASS}
                      placeholder="Optional"
                      autoComplete="off"
                      disabled={isDisabled}
                      value={field.value ?? ""}
                      onChange={(e) => field.onChange(e.target.value || null)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem className={FIELD_CLASS}>
                  <FormLabel className={LABEL_CLASS}>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      className={TEXTAREA_CLASS}
                      disabled={isDisabled}
                      value={field.value ?? ""}
                      onChange={(e) => field.onChange(e.target.value || null)}
                      placeholder="Optional"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="border-t pt-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="deductible"
                  render={({ field }) => (
                    <FormItem className={FIELD_CLASS}>
                      <FormLabel className={LABEL_CLASS}>Deductible</FormLabel>
                      <FormControl>
                        <label className="flex h-8 items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={Boolean(field.value)}
                            disabled={isDisabled}
                            onChange={(e) => field.onChange(e.target.checked)}
                          />
                          <span>{field.value ? "Yes" : "No"}</span>
                        </label>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="deductible_rate"
                  render={({ field }) => (
                    <FormItem className={FIELD_CLASS}>
                      <FormLabel className={LABEL_CLASS}>Deductible rate</FormLabel>
                      <FormControl>
                        <Input
                          className={CONTROL_CLASS}
                          inputMode="decimal"
                          autoComplete="off"
                          disabled={isDisabled || !deductible}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>

            {sourceDocumentType === "invoice" ? (
              <div className="border-t pt-3">
                <div className="text-sm font-medium">Vendor partner (invoice)</div>
                <div className="text-xs text-muted-foreground">Supplier details from the invoice.</div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="vendor_partner.name"
                    render={({ field }) => (
                      <FormItem className={`sm:col-span-2 ${FIELD_CLASS}`}>
                        <FormLabel className={LABEL_CLASS}>Name</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="organization"
                            disabled={isDisabled}
                            {...field}
                            value={field.value ?? ""}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.registration_number"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>Registration number</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="off"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.vat_number"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>VAT number</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="off"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.city"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>City</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="address-level2"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.country"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>Country</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="country-name"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.address"
                    render={({ field }) => (
                      <FormItem className={`sm:col-span-2 ${FIELD_CLASS}`}>
                        <FormLabel className={LABEL_CLASS}>Address</FormLabel>
                        <FormControl>
                          <Textarea
                            className={TEXTAREA_CLASS}
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.accountable_person"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>Accountable person</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="name"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.email"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>Email</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            type="email"
                            autoComplete="email"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="vendor_partner.phone"
                    render={({ field }) => (
                      <FormItem className={FIELD_CLASS}>
                        <FormLabel className={LABEL_CLASS}>Phone</FormLabel>
                        <FormControl>
                          <Input
                            className={CONTROL_CLASS}
                            autoComplete="tel"
                            disabled={isDisabled}
                            value={field.value ?? ""}
                            onChange={(e) => field.onChange(e.target.value || null)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            ) : null}

            {requiresDocumentTypeConfirmation ? (
              <div className="border-t pt-3">
                <Alert>
                  <div className="space-y-2 text-xs">
                    <p>
                      Low confidence for document type detection ({Math.round(draft.confidence * 100)}%). Confirm
                      whether this is an <strong>{sourceDocumentType}</strong> before recording.
                    </p>
                    <label className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={isDocumentTypeConfirmed}
                        disabled={isDisabled}
                        onChange={(event) => setIsDocumentTypeConfirmed(event.target.checked)}
                      />
                      <span>I confirm this document is a {sourceDocumentType}.</span>
                    </label>
                  </div>
                </Alert>
              </div>
            ) : null}

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            {confirmed ? null : (
              <CardFooter className="sticky bottom-0 -mx-4 bg-card/95 px-4 pb-3 pt-3 backdrop-blur">
                <div className="flex w-full items-center justify-end gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={isDisabled}>
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={isDisabled || !canSubmit}>
                    {confirming ? <Spinner className="mr-2 h-3 w-3" /> : null}
                    {confirming ? "Recording expense..." : "Confirm expense"}
                  </Button>
                </div>
              </CardFooter>
            )}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

