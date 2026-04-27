"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/shared/api/errors";
import { formatCurrency } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

import { useRecordExpense } from "../api/mutations";
import { expenseCategorySchema, recordExpenseSchema, type RecordExpenseInput } from "../model/schema";

export interface RecordExpenseFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

const CURRENCIES: Array<RecordExpenseInput["currency"]> = ["EUR", "BGN", "USD"];

const CATEGORY_LABELS: Record<RecordExpenseInput["category"], string> = {
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

export function RecordExpenseForm({ onSuccess, onCancel }: Readonly<RecordExpenseFormProps>) {
  const { data: session } = useSession();
  const recordExpense = useRecordExpense(session?.accessToken);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<RecordExpenseInput>({
    resolver: zodResolver(recordExpenseSchema),
    defaultValues: {
      counterparty: "",
      expense_date: new Date().toISOString().slice(0, 10),
      amount: "0",
      currency: "EUR",
      category: "office",
      description: null,
      deductible: true,
      deductible_rate: "1.0",
      source_document_type: null,
      source_document_id: null,
    },
    mode: "onSubmit",
  });

  const deductible = form.watch("deductible");
  const amount = form.watch("amount");
  const currency = form.watch("currency");
  const deductibleRate = form.watch("deductible_rate");

  const deductibleAmount = useMemo(() => {
    const a = Number(amount);
    const r = Number(deductibleRate);
    if (!Number.isFinite(a) || !Number.isFinite(r)) return 0;
    return deductible ? a * r : 0;
  }, [amount, deductibleRate, deductible]);

  async function onSubmit(values: RecordExpenseInput) {
    setError(null);
    try {
      await recordExpense.mutateAsync(values);
      form.reset();
      onSuccess?.();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        return;
      }
      setError("Unable to record expense. Please try again.");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="counterparty"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Counterparty</FormLabel>
              <FormControl>
                <Input placeholder="Office Store" autoComplete="off" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="expense_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Expense date</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
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
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
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
              <FormItem>
                <FormLabel>Amount</FormLabel>
                <FormControl>
                  <Input inputMode="decimal" autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="category"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Category</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {expenseCategorySchema.options.map((c) => (
                      <SelectItem key={c} value={c}>
                        {CATEGORY_LABELS[c]}
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
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Optional. e.g. Printer paper"
                  className="min-h-[96px]"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value || null)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="rounded-lg border p-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="deductible"
              render={({ field }) => (
                <FormItem className="space-y-2">
                  <FormLabel>Deductible</FormLabel>
                  <FormControl>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={Boolean(field.value)}
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
                <FormItem>
                  <FormLabel>Deductible rate</FormLabel>
                  <FormControl>
                    <Input inputMode="decimal" autoComplete="off" {...field} disabled={!deductible} />
                  </FormControl>
                  <p className="text-xs text-muted-foreground">
                    Deductible amount preview:{" "}
                    <span className="font-medium">{formatCurrency(deductibleAmount, currency)}</span>
                  </p>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="source_document_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Source document type</FormLabel>
                <Select
                  value={field.value ?? ""}
                  onValueChange={(v) => field.onChange(v ? v : null)}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Optional" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="invoice">Invoice</SelectItem>
                    <SelectItem value="receipt">Receipt</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="source_document_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Source document ID</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Optional"
                    autoComplete="off"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex items-center justify-end gap-2">
          {onCancel ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                form.reset();
                setError(null);
                onCancel();
              }}
              disabled={recordExpense.isPending}
            >
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={recordExpense.isPending}>
            {recordExpense.isPending ? "Saving…" : "Record expense"}
          </Button>
        </div>
      </form>
    </Form>
  );
}

