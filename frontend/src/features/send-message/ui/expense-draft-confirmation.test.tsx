import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";

import type { ExpenseDraftFormValues } from "@/features/send-message/model/receipt-expense-schema";
import { renderWithProviders } from "@/test/test-utils";

import { ExpenseDraftConfirmation } from "./expense-draft-confirmation";

describe("ExpenseDraftConfirmation", () => {
  const baseDraft: ExpenseDraftFormValues = {
    counterparty: "Office Store",
    expense_date: "2026-04-26",
    amount: "24.00",
    currency: "EUR",
    category: "office",
    description: null,
    deductible: true,
    deductible_rate: "1.0",
    source_document_type: "receipt",
    source_document_id: "doc-1",
    source_document_number: "R-839201",
    vendor_partner: null,
    items: null,
    confidence: 0.9,
    warnings: [],
  };

  it("renders returned draft and confirms edited values (incl. document number)", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    renderWithProviders(
      <ExpenseDraftConfirmation draft={baseDraft} onCancel={() => undefined} onConfirm={onConfirm} />,
    );

    expect(screen.getByDisplayValue("Office Store")).toBeInTheDocument();
    expect(screen.getByDisplayValue("R-839201")).toBeInTheDocument();

    const amount = screen.getByLabelText(/amount/i);
    await user.clear(amount);
    await user.type(amount, "25.00");

    const docNumber = screen.getByLabelText(/document number/i);
    await user.clear(docNumber);
    await user.type(docNumber, "R-900000");

    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        amount: "25.00",
        source_document_number: "R-900000",
      }),
    );
  });

  it("invoice vendor partner fields render and only require a supplier name", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    const draft: ExpenseDraftFormValues = {
      counterparty: "Vendor LLC",
      expense_date: "2026-04-26",
      amount: "10.00",
      currency: "EUR",
      category: "office",
      description: null,
      deductible: true,
      deductible_rate: "1.0",
      source_document_type: "invoice",
      source_document_id: "doc-2",
      source_document_number: "INV-1",
      vendor_partner: {
        name: "Vendor LLC",
        registration_number: null,
        vat_number: null,
        city: null,
        country: "Bulgaria",
        address: null,
        accountable_person: null,
        email: null,
        phone: null,
        confidence: 0.6,
        warnings: [],
      },
      items: null,
      confidence: 0.8,
      warnings: [],
    };

    renderWithProviders(
      <ExpenseDraftConfirmation draft={draft} onCancel={() => undefined} onConfirm={onConfirm} />,
    );

    expect(screen.getByText(/vendor partner \(invoice\)/i)).toBeInTheDocument();
    const name = screen.getByLabelText(/^name$/i);
    expect(name).toBeInTheDocument();
    expect(screen.getByLabelText(/registration number/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/city/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/accountable person/i)).toBeInTheDocument();

    await user.clear(name);
    await user.type(name, "Edited Vendor LLC");
    expect(screen.getByDisplayValue("Edited Vendor LLC")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        vendor_partner: expect.objectContaining({
          name: "Edited Vendor LLC",
          registration_number: null,
        }),
      }),
    );
  });

  it("shows confirming loading state and disables actions", () => {
    renderWithProviders(
      <ExpenseDraftConfirmation
        draft={baseDraft}
        confirming
        onCancel={() => undefined}
        onConfirm={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: /recording expense/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
    expect(screen.getByLabelText(/amount/i)).toBeDisabled();
  });

  it("requires explicit document-type confirmation for low confidence drafts", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    renderWithProviders(
      <ExpenseDraftConfirmation
        draft={{ ...baseDraft, confidence: 0.5 }}
        onCancel={() => undefined}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByText(/low confidence for document type detection/i)).toBeInTheDocument();

    const submitButton = screen.getByRole("button", { name: /confirm expense/i });
    expect(submitButton).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /i confirm this document is a receipt/i }));
    expect(submitButton).toBeEnabled();

    await user.click(submitButton);
    expect(onConfirm).toHaveBeenCalled();
  });
});

