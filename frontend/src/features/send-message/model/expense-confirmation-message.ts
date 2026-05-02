import type { ExpenseCategory } from "@/entities/expense/model/types";

import type { ConfirmExtractedExpenseResponse } from "./receipt-expense-schema";

const CATEGORY_LABELS = {
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
} as const satisfies Record<ExpenseCategory, string>;

function formatOptionalLocation(city?: string | null, country?: string | null): string | null {
  const parts = [city, country].filter((value): value is string => Boolean(value?.trim?.() ?? value));
  return parts.length > 0 ? parts.join(", ") : null;
}

export function buildExpenseConfirmationMessage(response: ConfirmExtractedExpenseResponse): string {
  const { expense, vendor_partner } = response;

  const lines = [
    `Expense added: ${expense.counterparty}`,
    `Amount: ${expense.amount} ${expense.currency}`,
    `Date: ${expense.expense_date}`,
    `Category: ${CATEGORY_LABELS[expense.category] ?? expense.category}`,
  ];

  if (expense.source_document_type) {
    lines.push(`Source document: ${expense.source_document_type}`);
  }

  if (expense.source_document_number) {
    lines.push(`Document number: ${expense.source_document_number}`);
  }

  if (expense.deductible_amount && expense.deductible_amount !== expense.amount) {
    lines.push(`Deductible amount: ${expense.deductible_amount} ${expense.currency}`);
  }

  if (!vendor_partner || vendor_partner.status === "skipped") {
    lines.push("Supplier partner: not created for this document.");
    return lines.join("\n");
  }

  const partner = vendor_partner.partner;
  if (!partner) {
    lines.push("Supplier partner: no partner returned.");
    return lines.join("\n");
  }

  lines.push(
    vendor_partner.status === "created"
      ? `Supplier partner created: ${partner.name}`
      : `Supplier partner matched: ${partner.name}`,
  );

  if (partner.registration_number?.trim?.()) {
    lines.push(`Registration number: ${partner.registration_number}`);
  }

  if (partner.vat_number?.trim?.()) {
    lines.push(`VAT number: ${partner.vat_number}`);
  }

  const location = formatOptionalLocation(partner.city, partner.country);
  if (location) {
    lines.push(`Location: ${location}`);
  }

  for (const warning of vendor_partner.warnings) {
    lines.push(`Note: ${warning}`);
  }

  return lines.join("\n");
}

