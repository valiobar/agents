"use client";

import { useSession } from "next-auth/react";

import { useExpenses } from "@/entities/expense/api/queries";
import { CategoryBadge } from "@/entities/expense/ui/category-badge";
import type { ExpenseCategory } from "@/entities/expense/model/types";
import { useExpenseFiltersStore } from "@/shared/store/expense-filters-store";
import { formatCurrency, formatDate } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";

const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
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

const CATEGORIES: ExpenseCategory[] = [
  "office",
  "travel",
  "meals",
  "software",
  "rent",
  "utilities",
  "professional_services",
  "tax",
  "payroll",
  "other",
];
const ANY_CATEGORY = "any";

export function ExpenseTable() {
  const { data: session } = useSession();

  const {
    category,
    dateRange,
    counterparty,
    deductible,
    amountMin,
    amountMax,
    setCategory,
    setDateRange,
    setCounterparty,
    setDeductible,
    setAmountMin,
    setAmountMax,
    reset,
  } = useExpenseFiltersStore();

  const expenses = useExpenses(session?.accessToken, {
    category: category ?? undefined,
    date_from: dateRange?.from || undefined,
    date_to: dateRange?.to || undefined,
    counterparty: counterparty || undefined,
    deductible: deductible === "all" ? undefined : deductible === "deductible",
    amount_min: amountMin || undefined,
    amount_max: amountMax || undefined,
    limit: 50,
    offset: 0,
  });

  const content = (() => {
    if (expenses.isLoading) {
      return (
        <div className="flex items-center justify-center py-10">
          <Spinner />
        </div>
      );
    }

    if (expenses.isError) {
      return (
        <EmptyState
          title="Unable to load expenses"
          description="Please try again in a moment."
          action={
            <Button type="button" variant="outline" onClick={() => expenses.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }

    if (!expenses.data?.length) {
      return (
        <EmptyState title="No expenses yet" description="Record your first expense to see it listed here." />
      );
    }

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Counterparty</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Deductible</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {expenses.data.map((exp) => (
            <TableRow key={exp.id}>
              <TableCell className="font-medium">{exp.counterparty}</TableCell>
              <TableCell>
                <CategoryBadge category={exp.category} />
              </TableCell>
              <TableCell>{formatDate(exp.expense_date)}</TableCell>
              <TableCell>{formatCurrency(exp.amount, exp.currency)}</TableCell>
              <TableCell>
                {exp.deductible ? (
                  <span className="text-sm">
                    Yes ({formatCurrency(exp.deductible_amount, exp.currency)})
                  </span>
                ) : (
                  <span className="text-sm text-muted-foreground">No</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  })();

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Category</p>
            <Select
              value={category ?? ANY_CATEGORY}
              onValueChange={(v) =>
                setCategory(v === ANY_CATEGORY ? null : (v as ExpenseCategory))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY_CATEGORY}>Any</SelectItem>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {CATEGORY_LABELS[c]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">From</p>
            <Input
              type="date"
              value={dateRange?.from ?? ""}
              onChange={(e) =>
                setDateRange(
                  e.target.value
                    ? { from: e.target.value, to: dateRange?.to ?? e.target.value }
                    : null,
                )
              }
            />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">To</p>
            <Input
              type="date"
              value={dateRange?.to ?? ""}
              onChange={(e) =>
                setDateRange(
                  e.target.value
                    ? { from: dateRange?.from ?? e.target.value, to: e.target.value }
                    : null,
                )
              }
            />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Counterparty</p>
            <Input
              placeholder="Search…"
              value={counterparty}
              onChange={(e) => setCounterparty(e.target.value)}
            />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Deductible</p>
            <Select value={deductible} onValueChange={(v) => setDeductible(v as typeof deductible)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="deductible">Deductible</SelectItem>
                <SelectItem value="non_deductible">Non-deductible</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Amount</p>
            <div className="flex gap-2">
              <Input
                placeholder="Min"
                inputMode="decimal"
                value={amountMin}
                onChange={(e) => setAmountMin(e.target.value)}
              />
              <Input
                placeholder="Max"
                inputMode="decimal"
                value={amountMax}
                onChange={(e) => setAmountMax(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={reset}>
            Reset
          </Button>
        </div>
      </div>

      {content}
    </div>
  );
}

