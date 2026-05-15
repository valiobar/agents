import type { Invoice, InvoiceCreate, InvoicePartyInput } from "@/entities/invoice/model/types";
import type {
  SalesInvoiceCreatedResponse,
  SalesInvoiceInventoryReview,
  SalesInvoiceReview,
} from "@/features/send-message/model/sales-invoice-workflow-schema";

export const salesInvoiceRecipient: InvoicePartyInput = {
  name: "Acme Ltd",
  registration_number: "123456789",
  vat_number: null,
  city: "Sofia",
  country: "Bulgaria",
  address: "1 Client St",
  accountable_person: "Maria Petrova",
  logo_data_url: null,
};

export function makeSalesInvoiceInventoryReview(
  overrides: Partial<SalesInvoiceInventoryReview> = {},
): SalesInvoiceInventoryReview {
  return {
    type: "sales_invoice_inventory_review",
    company_id: "company-1",
    partner_query: "Acme",
    recipient: null,
    partner_candidates: [
      {
        partner: {
          id: "partner-1",
          user_id: "user-1",
          company_id: "company-1",
          kind: "client",
          name: "Acme Ltd",
          registration_number: "123456789",
          vat_number: null,
          city: "Sofia",
          country: "Bulgaria",
          address: "1 Client St",
          accountable_person: "Maria Petrova",
          email: null,
          phone: null,
          notes: null,
          created_at: "2026-05-01T00:00:00Z",
          updated_at: "2026-05-01T00:00:00Z",
        },
        match_type: "name_prefix",
        score: 0.93,
        match_reasons: ["name prefix"],
      },
    ],
    lines: [
      {
        line_index: 0,
        requested: {
          description: "Widget A",
          query: "SKU-001",
          quantity: "2",
          unit_label: "pcs",
          unit_price: "10.00",
          vat_rate: "0.20",
          category: "hardware",
        },
        selected_item_id: "item-1",
        selected_location_id: "loc-1",
        candidates: [
          {
            item_id: "item-1",
            name: "Widget A",
            description: "Stock widget",
            sku: "SKU-001",
            category: "hardware",
            unit: "pcs",
            selling_price: "10.00",
            confidence: 0.98,
            match_reason: "sku",
            available_quantity: "5",
          },
        ],
        stock_levels: [
          {
            item_id: "item-1",
            item_name: "Widget A",
            item_sku: "SKU-001",
            location_id: "loc-1",
            location_name: "Main warehouse",
            available_quantity: "5",
            unit: "pcs",
          },
        ],
        available_quantity: "5",
        warnings: [],
      },
    ],
    warnings: [],
    ...overrides,
  };
}

export function makeSalesInvoiceDraft(overrides: Partial<InvoiceCreate> = {}): InvoiceCreate {
  return {
    company_id: "company-1",
    partner_id: "partner-1",
    recipient: null,
    counterparty: "Acme Ltd",
    issue_date: "2026-05-15",
    tax_event_date: "2026-05-15",
    due_date: "2026-05-30",
    currency: "EUR",
    status: "draft",
    notes: "Initial note",
    items: [
      {
        description: "Widget A",
        quantity: "2",
        unit_label: "pcs",
        unit_price: "10.00",
        vat_rate: "0.20",
        category: "hardware",
        inventory_item_id: "item-1",
        inventory_location_id: "loc-1",
        stock_quantity: "5",
      },
    ],
    ...overrides,
  };
}

export function makeSalesInvoiceReview(overrides: Partial<SalesInvoiceReview> = {}): SalesInvoiceReview {
  return {
    type: "sales_invoice_review",
    company_id: "company-1",
    invoice_draft: makeSalesInvoiceDraft(),
    inventory_warnings: [],
    partner_warnings: [],
    ...overrides,
  };
}

export function makeSalesInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: "invoice-1",
    user_id: "user-1",
    company_id: "company-1",
    partner_id: "partner-1",
    invoice_number: "INV-2026-001",
    counterparty: "Acme Ltd",
    supplier_snapshot: null,
    recipient_snapshot: { ...salesInvoiceRecipient, email: null, phone: null },
    issue_date: "2026-05-15",
    tax_event_date: "2026-05-15",
    due_date: "2026-05-30",
    place_of_supply: null,
    payment_method: null,
    bank_name: null,
    bank_bic: null,
    bank_iban: null,
    amount_in_words: null,
    currency: "EUR",
    items: [
      {
        description: "Widget A",
        quantity: "2",
        unit_label: "pcs",
        unit_price: "10.00",
        vat_rate: "0.20",
        category: "hardware",
        subtotal: "20.00",
        vat_amount: "4.00",
        total: "24.00",
      },
    ],
    subtotal: "20.00",
    vat_total: "4.00",
    total: "24.00",
    status: "draft",
    vat_reason: null,
    recipient_name: "Acme Ltd",
    compiler_name: null,
    original_label: null,
    notes: "Initial note",
    created_at: "2026-05-15T00:00:00Z",
    updated_at: "2026-05-15T00:00:00Z",
    ...overrides,
  };
}

export function makeSalesInvoiceCreated(
  overrides: Partial<SalesInvoiceCreatedResponse> = {},
): SalesInvoiceCreatedResponse {
  return {
    type: "sales_invoice_created",
    invoice: makeSalesInvoice(),
    warnings: [],
    ...overrides,
  };
}
