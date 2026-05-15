import { describe, expect, it } from "vitest";

import {
  makeSalesInvoiceCreated,
  makeSalesInvoiceInventoryReview,
  makeSalesInvoiceReview,
} from "@/test/sales-invoice-fixtures";

import { chatReducer, type ChatState } from "./chat-reducer";

const initialState: ChatState = {
  messages: [],
  streamingContent: "",
  status: "idle",
  error: null,
  documentReviewStatus: "idle",
  expenseDraft: null,
  inventoryImportPreview: null,
  unknownDocumentReview: null,
  documentReviewError: null,
  toolTraces: [],
  activeWorkflow: null,
  salesInvoiceStatus: "idle",
  salesInvoiceInventoryReview: null,
  salesInvoiceDraft: null,
  salesInvoiceCreated: null,
  salesInvoiceError: null,
  salesInvoiceSuggestion: null,
};

describe("chatReducer sales invoice workflow", () => {
  it("moves from inventory preview to invoice draft review", () => {
    const inventoryReview = makeSalesInvoiceInventoryReview();
    const invoiceReview = makeSalesInvoiceReview();

    const state = chatReducer(initialState, {
      type: "SALES_INVOICE_INVENTORY_READY",
      payload: inventoryReview,
    });

    const next = chatReducer(state, {
      type: "SALES_INVOICE_READY",
      payload: invoiceReview,
    });

    expect(next.salesInvoiceStatus).toBe("sales_invoice_ready");
    expect(next.salesInvoiceInventoryReview).toBe(inventoryReview);
    expect(next.salesInvoiceDraft?.invoice_draft.items).toHaveLength(1);
    expect(next.activeWorkflow).toEqual({
      workflow: "sales_invoice_inventory",
      step: "invoice_review",
      payload: invoiceReview,
      error: null,
    });
  });

  it("tracks loading, confirming, success, error, reset, and clear states", () => {
    const inventoryReview = makeSalesInvoiceInventoryReview();
    const invoiceReview = makeSalesInvoiceReview();
    const created = makeSalesInvoiceCreated();

    const loading = chatReducer(initialState, { type: "SALES_INVOICE_PREVIEW_LOADING" });
    expect(loading.salesInvoiceStatus).toBe("loading_sales_invoice_inventory");
    expect(loading.activeWorkflow?.step).toBe("loading_inventory");

    const previewReady = chatReducer(loading, {
      type: "SALES_INVOICE_INVENTORY_READY",
      payload: inventoryReview,
    });
    expect(previewReady.salesInvoiceStatus).toBe("sales_invoice_inventory_ready");
    expect(previewReady.activeWorkflow?.step).toBe("inventory_review");

    const confirmingInventory = chatReducer(previewReady, {
      type: "SALES_INVOICE_INVENTORY_CONFIRMING",
    });
    expect(confirmingInventory.salesInvoiceStatus).toBe("confirming_sales_invoice_inventory");
    expect(confirmingInventory.activeWorkflow?.payload).toBe(inventoryReview);

    const inventoryFailed = chatReducer(confirmingInventory, {
      type: "SALES_INVOICE_INVENTORY_CONFIRMATION_FAILED",
      payload: "Inventory failed",
    });
    expect(inventoryFailed.salesInvoiceStatus).toBe("sales_invoice_inventory_ready");
    expect(inventoryFailed.salesInvoiceError).toBe("Inventory failed");

    const draftReady = chatReducer(inventoryFailed, {
      type: "SALES_INVOICE_READY",
      payload: invoiceReview,
    });
    const confirmingInvoice = chatReducer(draftReady, { type: "SALES_INVOICE_CONFIRMING" });
    expect(confirmingInvoice.salesInvoiceStatus).toBe("confirming_sales_invoice");
    expect(confirmingInvoice.activeWorkflow?.payload).toBe(invoiceReview);

    const invoiceFailed = chatReducer(confirmingInvoice, {
      type: "SALES_INVOICE_CONFIRMATION_FAILED",
      payload: "Invoice failed",
    });
    expect(invoiceFailed.salesInvoiceStatus).toBe("sales_invoice_ready");
    expect(invoiceFailed.salesInvoiceError).toBe("Invoice failed");

    const confirmed = chatReducer(invoiceFailed, {
      type: "SALES_INVOICE_CONFIRMATION_SUCCEEDED",
      payload: created,
    });
    expect(confirmed.salesInvoiceStatus).toBe("sales_invoice_confirmed");
    expect(confirmed.salesInvoiceCreated).toBe(created);
    expect(confirmed.activeWorkflow?.step).toBe("created");

    const cleared = chatReducer(confirmed, { type: "SALES_INVOICE_CLEAR" });
    expect(cleared.salesInvoiceStatus).toBe("idle");
    expect(cleared.salesInvoiceDraft).toBeNull();
    expect(cleared.activeWorkflow).toBeNull();

    const reset = chatReducer(confirmed, { type: "RESET" });
    expect(reset).toMatchObject(initialState);

    const historyLoaded = chatReducer(confirmed, {
      type: "LOAD_HISTORY",
      payload: [{ role: "assistant", content: "old answer", created_at: "2026-05-01T00:00:00Z", metadata: {} }],
    });
    expect(historyLoaded.salesInvoiceStatus).toBe("idle");
    expect(historyLoaded.salesInvoiceCreated).toBeNull();
    expect(historyLoaded.activeWorkflow).toBeNull();
    expect(historyLoaded.messages).toHaveLength(1);
  });

  it("clears a confirmed sales invoice before a follow-up user message", () => {
    const confirmed = chatReducer(initialState, {
      type: "SALES_INVOICE_CONFIRMATION_SUCCEEDED",
      payload: makeSalesInvoiceCreated(),
    });

    const next = chatReducer(confirmed, {
      type: "SEND_MESSAGE",
      payload: "thanks",
    });

    expect(next.salesInvoiceStatus).toBe("idle");
    expect(next.salesInvoiceCreated).toBeNull();
    expect(next.messages.at(-1)?.content).toBe("thanks");
  });
});
