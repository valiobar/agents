import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";

import type { InventoryImportPreview } from "@/entities/inventory/model/types";
import type { ExpenseDraftFormValues } from "@/features/send-message/model/receipt-expense-schema";
import { ApiError } from "@/shared/api/errors";
import { renderWithProviders } from "@/test/test-utils";

import { SupplierInvoiceInventoryConfirmation } from "./supplier-invoice-inventory-confirmation";

const draft: ExpenseDraftFormValues = {
  counterparty: "Invoice Vendor",
  expense_date: "2026-04-26",
  amount: "42.00",
  currency: "EUR",
  category: "office",
  description: null,
  deductible: true,
  deductible_rate: "1.0",
  source_document_type: "invoice",
  source_document_id: "doc-2",
  source_document_number: "INV-42",
  vendor_partner: {
    name: "Invoice Vendor",
    registration_number: "123456789",
    vat_number: null,
    city: "Sofia",
    country: "Bulgaria",
    address: "1 Supplier St",
    accountable_person: "Ivan Ivanov",
    email: null,
    phone: null,
    confidence: 0.9,
    warnings: [],
  },
  items: null,
  confidence: 0.9,
  warnings: [],
};

const preview: InventoryImportPreview = {
  id: "preview-1",
  user_id: "u1",
  company_id: "company-1",
  document_id: "doc-2",
  source_type: "supplier_invoice_upload",
  status: "draft",
  lines: [
    {
      candidate: {
        description: "Widget",
        sku: "SKU-1",
        barcode: null,
        quantity: "3",
        unit: "pcs",
        unit_price: "14.00",
      },
      matched_item_id: null,
      proposed_item: null,
      location_id: "loc-1",
      receipt_quantity: "3",
      warnings: [],
    },
    {
      candidate: {
        description: "Matched Widget",
        sku: "SKU-2",
        barcode: "111",
        quantity: "2",
        unit: "pcs",
        unit_price: "10.00",
      },
      matched_item_id: "item-1",
      proposed_item: null,
      location_id: "loc-2",
      receipt_quantity: "2",
      warnings: [],
    },
  ],
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

describe("SupplierInvoiceInventoryConfirmation", () => {
  it("renders preview and confirms using preview lines with the same draft", async () => {
    const user = userEvent.setup();
    const onConfirmWithLines = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <SupplierInvoiceInventoryConfirmation
        draft={draft}
        preview={preview}
        onCancel={() => undefined}
        onConfirmWithLines={onConfirmWithLines}
      />,
    );

    expect(screen.getByText(/review inventory import/i)).toBeInTheDocument();
    expect(screen.getByText("Widget")).toBeInTheDocument();
    expect(screen.getByText("Matched Widget")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /confirm inventory/i }));
    expect(onConfirmWithLines).toHaveBeenCalledWith(preview.lines, draft);
  });

  it("switches editor mode between unmatched and matched rows", async () => {
    const user = userEvent.setup();
    const onConfirmWithLines = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <SupplierInvoiceInventoryConfirmation
        draft={draft}
        preview={preview}
        onCancel={() => undefined}
        onConfirmWithLines={onConfirmWithLines}
      />,
    );

    expect(screen.getByText(/unmatched item details/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/unmatched line item name/i)).toHaveValue("Widget");

    await user.click(screen.getByText("Matched Widget"));
    expect(screen.getByText(/matched item movement/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/matched item id/i)).toHaveValue("item-1");
  });

  it("applies row edits before confirming payload", async () => {
    const user = userEvent.setup();
    const onConfirmWithLines = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <SupplierInvoiceInventoryConfirmation
        draft={draft}
        preview={preview}
        onCancel={() => undefined}
        onConfirmWithLines={onConfirmWithLines}
      />,
    );

    const locationInput = screen.getByLabelText(/unmatched line location id/i);
    const quantityInput = screen.getByLabelText(/unmatched line receipt quantity/i);
    await user.clear(locationInput);
    await user.type(locationInput, "loc-main");
    await user.clear(quantityInput);
    await user.type(quantityInput, "4");
    await user.click(screen.getByRole("button", { name: /apply changes/i }));
    await user.click(screen.getByRole("button", { name: /confirm inventory/i }));

    expect(onConfirmWithLines).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          location_id: "loc-main",
          receipt_quantity: "4",
        }),
      ]),
      draft,
    );
  });

  it("blocks row switch with unsaved edits until user applies or discards", async () => {
    const user = userEvent.setup();
    const onConfirmWithLines = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <SupplierInvoiceInventoryConfirmation
        draft={draft}
        preview={preview}
        onCancel={() => undefined}
        onConfirmWithLines={onConfirmWithLines}
      />,
    );

    const locationInput = screen.getByLabelText(/unmatched line location id/i);
    await user.clear(locationInput);
    await user.type(locationInput, "temp-loc");
    await user.click(screen.getByText("Matched Widget"));

    expect(screen.getByText(/apply or discard current line changes before switching lines/i)).toBeInTheDocument();
    expect(screen.getByText(/editing line 1/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /discard changes/i }));
    await user.click(screen.getByText("Matched Widget"));
    expect(screen.getByText(/editing line 2/i)).toBeInTheDocument();
  });

  it("shows api error message when inventory confirmation fails", async () => {
    const user = userEvent.setup();
    const onConfirmWithLines = vi.fn().mockRejectedValue(new ApiError(500, "Unable to confirm", null));

    renderWithProviders(
      <SupplierInvoiceInventoryConfirmation
        draft={draft}
        preview={preview}
        onCancel={() => undefined}
        onConfirmWithLines={onConfirmWithLines}
      />,
    );

    await user.click(screen.getByRole("button", { name: /confirm inventory/i }));
    expect(await screen.findByText("Unable to confirm")).toBeInTheDocument();
  });
});
