import type { SalesInvoiceCreatedResponse } from "./sales-invoice-workflow-schema";

export function buildSalesInvoiceConfirmationMessage(response: SalesInvoiceCreatedResponse): string {
  const counterparty =
    response.invoice.counterparty ??
    response.invoice.recipient_snapshot?.name ??
    "Unknown";

  const lines = [
    `Sales invoice created: ${response.invoice.invoice_number}`,
    `Counterparty: ${counterparty}`,
    `Total: ${response.invoice.total} ${response.invoice.currency}`,
    `Status: ${response.invoice.status}`,
  ];

  for (const warning of response.warnings) {
    lines.push(`Warning: ${warning}`);
  }

  return lines.join("\n");
}
