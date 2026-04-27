import { RecordExpenseDialog } from "@/features/record-expense/ui/record-expense-dialog";
import { ExpenseTable } from "@/widgets/expense-table/ui/expense-table";

export default function ExpensesPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Expenses</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Record expenses and keep your reporting up to date.
          </p>
        </div>
        <RecordExpenseDialog />
      </div>

      <ExpenseTable />
    </section>
  );
}

