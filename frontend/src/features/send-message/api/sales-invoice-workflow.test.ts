import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/shared/api/client";
import { salesInvoiceWorkflowResponseSchema } from "@/features/send-message/model/sales-invoice-workflow-schema";
import {
  makeSalesInvoiceCreated,
  makeSalesInvoiceDraft,
  makeSalesInvoiceInventoryReview,
  makeSalesInvoiceReview,
} from "@/test/sales-invoice-fixtures";

import {
  confirmSalesInvoiceDraft,
  confirmSalesInvoiceInventoryReview,
  createSalesInvoiceInventoryPreview,
} from "./sales-invoice-workflow";

vi.mock("@/shared/api/client", () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

const postMock = vi.mocked(apiClient.post);

describe("sales invoice workflow API helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("parses all sales invoice workflow response variants", () => {
    expect(salesInvoiceWorkflowResponseSchema.parse(makeSalesInvoiceInventoryReview()).type).toBe(
      "sales_invoice_inventory_review",
    );
    expect(salesInvoiceWorkflowResponseSchema.parse(makeSalesInvoiceReview()).type).toBe("sales_invoice_review");
    expect(salesInvoiceWorkflowResponseSchema.parse(makeSalesInvoiceCreated()).type).toBe("sales_invoice_created");
  });

  it("posts preview payload to the sales inventory preview endpoint", async () => {
    const response = makeSalesInvoiceInventoryReview();
    postMock.mockResolvedValueOnce(response);

    const payload = {
      partner_query: "Acme",
      recipient: null,
      issue_date: null,
      tax_event_date: null,
      due_date: null,
      currency: "EUR" as const,
      notes: null,
      lines: [
        {
          description: "Widget A",
          query: "SKU-001",
          quantity: "2",
          unit_label: "pcs",
          unit_price: "10.00",
          vat_rate: "0.20",
          category: "hardware",
        },
      ],
    };

    await expect(
      createSalesInvoiceInventoryPreview({
        agentId: "agent-1",
        token: "token-1",
        payload,
      }),
    ).resolves.toBe(response);

    expect(postMock).toHaveBeenCalledWith(
      "/agents/agent-1/invoice-workflows/sales-inventory/preview",
      payload,
      { token: "token-1" },
    );
  });

  it("posts confirmed inventory selections to the inventory confirmation endpoint", async () => {
    const response = makeSalesInvoiceReview();
    postMock.mockResolvedValueOnce(response);

    const payload = {
      source_preview: {
        partner_query: "Acme",
        recipient: null,
        currency: "EUR" as const,
        lines: [
          {
            description: "Widget A",
            query: "SKU-001",
            quantity: "2",
            unit_label: "pcs",
            unit_price: "10.00",
            vat_rate: "0.20",
            category: "hardware",
          },
        ],
      },
      selected_partner_id: "partner-1",
      recipient: null,
      lines: [
        {
          line_index: 0,
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
    };

    await expect(
      confirmSalesInvoiceInventoryReview({
        agentId: "agent-1",
        token: "token-1",
        payload,
      }),
    ).resolves.toBe(response);

    expect(postMock).toHaveBeenCalledWith(
      "/agents/agent-1/invoice-workflows/sales-inventory/inventory/confirm",
      payload,
      { token: "token-1" },
    );
  });

  it("posts confirmed invoice draft with explicit confirmation flag", async () => {
    const response = makeSalesInvoiceCreated();
    const invoiceDraft = makeSalesInvoiceDraft();
    postMock.mockResolvedValueOnce(response);

    await expect(
      confirmSalesInvoiceDraft({
        agentId: "agent-1",
        token: "token-1",
        invoiceDraft,
      }),
    ).resolves.toBe(response);

    expect(postMock).toHaveBeenCalledWith(
      "/agents/agent-1/invoice-workflows/sales-inventory/invoice/confirm",
      { invoice_draft: invoiceDraft, confirmed: true },
      { token: "token-1" },
    );
  });
});
