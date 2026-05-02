import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import type { ExpenseDraftResponse } from "@/entities/expense/model/types";
import type { ConfirmExtractedExpenseResponse } from "@/features/send-message/model/receipt-expense-schema";
import { ApiError } from "@/shared/api/errors";
import { renderWithProviders } from "@/test/test-utils";

import { ChatWindow } from "./chat-window";

const {
  mockCreateExpenseDraft,
  mockConfirmExtractedExpense,
  mockAddNotification,
  mockEmptyConversations,
  mockConversationQuery,
} = vi.hoisted(() => ({
  mockCreateExpenseDraft: vi.fn(),
  mockConfirmExtractedExpense: vi.fn(),
  mockAddNotification: vi.fn(),
  mockEmptyConversations: [] as unknown[],
  mockConversationQuery: { data: null, isError: false },
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "token-1" } }),
}));

vi.mock("@/entities/conversation/api/queries", () => ({
  useConversations: () => ({ data: mockEmptyConversations, isError: false }),
  useConversation: () => mockConversationQuery,
}));

vi.mock("@/shared/store/chat-store", () => {
  const store = {
    getConversationId: () => null,
    setConversationId: vi.fn(),
    clearConversationId: vi.fn(),
  };
  return {
    useChatStore: (selector: (s: typeof store) => unknown) => selector(store),
  };
});

vi.mock("@/shared/store/notification-store", () => ({
  useNotificationStore: () => ({ addNotification: mockAddNotification }),
}));

vi.mock("@/features/send-message/api/stream-message", () => ({
  streamAgentMessage: async function* streamAgentMessage() {
    yield { event: "done", data: { conversation_id: "c1" } };
  },
}));

vi.mock("@/features/send-message/api/receipt-expense", () => ({
  createExpenseDraft: (input: unknown) => mockCreateExpenseDraft(input),
  confirmExtractedExpense: (input: unknown) => mockConfirmExtractedExpense(input),
}));

vi.mock("@/entities/conversation/ui/message-list", () => ({
  MessageList: ({ messages, streamingContent }: {
    messages: Array<{ content: string }>;
    streamingContent?: string;
  }) => (
    <div data-testid="message-list">
      {messages.map((message, index) => (
        <p key={index}>{message.content}</p>
      ))}
      {streamingContent ? <p>{streamingContent}</p> : null}
    </div>
  ),
}));

const receiptDraftResponse: ExpenseDraftResponse = {
  document: {
    id: "doc-1",
    company_id: "company-1",
    filename: "receipt.pdf",
    content_type: "application/pdf",
    size_bytes: 10,
    status: "ready",
    chunk_count: 0,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
  draft: {
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
  },
  extracted_text: null,
  provider: "mock",
  model: "mock",
  extracted_at: "2026-05-01T00:00:00Z",
};

const receiptConfirmationResponse: ConfirmExtractedExpenseResponse = {
  expense: {
    id: "exp-1",
    user_id: "u1",
    counterparty: "Office Store",
    expense_date: "2026-04-26",
    amount: "24.00",
    currency: "EUR",
    category: "office",
    description: null,
    deductible: true,
    deductible_rate: "1.0",
    deductible_amount: "24.00",
    source_document_type: "receipt",
    source_document_id: "doc-1",
    source_document_number: "R-839201",
    items: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
  vendor_partner: null,
};

const invoiceDraftResponse: ExpenseDraftResponse = {
  document: {
    id: "doc-2",
    company_id: "company-1",
    filename: "invoice.pdf",
    content_type: "application/pdf",
    size_bytes: 10,
    status: "ready",
    chunk_count: 0,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
  draft: {
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
  },
  extracted_text: null,
  provider: "mock",
  model: "mock",
  extracted_at: "2026-05-01T00:00:00Z",
};

const invoiceConfirmationResponse: ConfirmExtractedExpenseResponse = {
  expense: {
    id: "exp-2",
    user_id: "u1",
    counterparty: "Invoice Vendor",
    expense_date: "2026-04-26",
    amount: "42.00",
    currency: "EUR",
    category: "office",
    description: null,
    deductible: true,
    deductible_rate: "1.0",
    deductible_amount: "42.00",
    source_document_type: "invoice",
    source_document_id: "doc-2",
    source_document_number: "INV-42",
    items: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
  vendor_partner: {
    status: "created",
    partner: {
      id: "partner-1",
      user_id: "u1",
      company_id: "company-1",
      kind: "supplier",
      name: "Invoice Vendor",
      registration_number: "123456789",
      vat_number: null,
      city: "Sofia",
      country: "Bulgaria",
      address: "1 Supplier St",
      accountable_person: "Ivan Ivanov",
      email: null,
      phone: null,
      notes: null,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z",
    },
    warnings: [],
  },
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("ChatWindow", () => {
  function getFileInput() {
    const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
    if (!input) throw new Error("Expected file input to exist");
    return input;
  }

  it("upload is disabled when the agent has no company", () => {
    renderWithProviders(<ChatWindow agentId="agent-1" companyId={null} />);
    expect(screen.getByRole("button", { name: /attach document/i })).toBeDisabled();
  });

  it("renders returned draft and confirms edited values; clears draft and invalidates queries", async () => {
    const user = userEvent.setup();

    mockCreateExpenseDraft.mockResolvedValueOnce(receiptDraftResponse);
    mockConfirmExtractedExpense.mockResolvedValueOnce({
      expense: {
        ...receiptConfirmationResponse.expense,
        amount: "25.00",
        deductible_amount: "25.00",
      },
      vendor_partner: null,
    });

    const { queryClient } = renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const file = new File(["receipt"], "receipt.pdf", { type: "application/pdf" });
    fireEvent.change(getFileInput(), { target: { files: [file] } });

    await waitFor(() => {
      expect(mockCreateExpenseDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          sourceDocumentType: "auto",
        }),
      );
    });

    expect(await screen.findByText(/review extracted expense/i)).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Office Store")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("R-839201")).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/amount/i));
    await user.type(screen.getByLabelText(/amount/i), "25.00");
    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    await waitFor(() => {
      expect(mockConfirmExtractedExpense).toHaveBeenCalledWith(
        expect.objectContaining({
          agentId: "agent-1",
          token: "token-1",
          draft: expect.objectContaining({
            amount: "25.00",
            source_document_number: "R-839201",
          }),
        }),
      );
    });

    expect(invalidateSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText(/review extracted expense/i)).not.toBeInTheDocument();
    });
  });

  it("API error states show notifications", async () => {
    const file = new File(["receipt"], "receipt.pdf", { type: "application/pdf" });

    mockCreateExpenseDraft.mockRejectedValueOnce(new ApiError(500, "Upload failed", null));

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), { target: { files: [file] } });

    await waitFor(() => {
      expect(mockAddNotification).toHaveBeenCalledWith("Upload failed", "error");
    });
  });

  it("successful invoice confirmation displays supplier partner details in message and toast", async () => {
    const user = userEvent.setup();

    mockCreateExpenseDraft.mockResolvedValueOnce(invoiceDraftResponse);
    mockConfirmExtractedExpense.mockResolvedValueOnce(invoiceConfirmationResponse);

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["invoice"], "invoice.pdf", { type: "application/pdf" })] },
    });

    expect(await screen.findByText(/vendor partner \(invoice\)/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    await waitFor(() => {
      expect(mockAddNotification).toHaveBeenCalledWith(
        "Expense recorded: Invoice Vendor. Supplier partner created.",
        "success",
      );
    });

    const messageList = await screen.findByTestId("message-list");
    expect(messageList).toHaveTextContent(/expense added: invoice vendor/i);
    expect(messageList).toHaveTextContent(/supplier partner created: invoice vendor/i);
    expect(messageList).toHaveTextContent(/registration number: 123456789/i);
    expect(messageList).toHaveTextContent(/location: sofia, bulgaria/i);
  });

  it("shows extraction progress while document draft is pending", async () => {
    const pendingDraft = deferred<ExpenseDraftResponse>();
    mockCreateExpenseDraft.mockReturnValueOnce(pendingDraft.promise);

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["receipt"], "receipt.pdf", { type: "application/pdf" })] },
    });

    expect(await screen.findByText(/reading document and extracting expense details/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /processing document/i })).toBeDisabled();

    pendingDraft.resolve(receiptDraftResponse);
    expect(await screen.findByText(/review extracted expense/i)).toBeInTheDocument();
  });

  it("shows recording progress while confirmation is pending", async () => {
    const user = userEvent.setup();
    mockCreateExpenseDraft.mockResolvedValueOnce(receiptDraftResponse);
    const pendingConfirmation = deferred<ConfirmExtractedExpenseResponse>();
    mockConfirmExtractedExpense.mockReturnValueOnce(pendingConfirmation.promise);

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["receipt"], "receipt.pdf", { type: "application/pdf" })] },
    });

    await screen.findByText(/review extracted expense/i);
    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    expect(await screen.findByRole("button", { name: /recording expense/i })).toBeDisabled();

    pendingConfirmation.resolve(receiptConfirmationResponse);
    expect(await screen.findByText(/expense added: office store/i)).toBeInTheDocument();
  });

  it("receipt success message includes expense details and no-partner status", async () => {
    const user = userEvent.setup();
    mockCreateExpenseDraft.mockResolvedValueOnce(receiptDraftResponse);

    const responseWithDeductible: ConfirmExtractedExpenseResponse = {
      expense: {
        ...receiptConfirmationResponse.expense,
        deductible_rate: "0.5",
        deductible_amount: "12.00",
      },
      vendor_partner: null,
    };
    mockConfirmExtractedExpense.mockResolvedValueOnce(responseWithDeductible);

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["receipt"], "receipt.pdf", { type: "application/pdf" })] },
    });

    await screen.findByText(/review extracted expense/i);
    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    const messageList = await screen.findByTestId("message-list");
    expect(messageList).toHaveTextContent(/expense added: office store/i);
    expect(messageList).toHaveTextContent(/amount: 24\.00 eur/i);
    expect(messageList).toHaveTextContent(/date: 2026-04-26/i);
    expect(messageList).toHaveTextContent(/category: office/i);
    expect(messageList).toHaveTextContent(/document number: r-839201/i);
    expect(messageList).toHaveTextContent(/deductible amount: 12\.00 eur/i);
    expect(messageList).toHaveTextContent(/supplier partner: not created/i);
  });

  it("keeps the draft editable when confirmation fails", async () => {
    const user = userEvent.setup();
    mockCreateExpenseDraft.mockResolvedValueOnce(receiptDraftResponse);
    mockConfirmExtractedExpense.mockRejectedValueOnce(new ApiError(500, "Unable to save", null));

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["receipt"], "receipt.pdf", { type: "application/pdf" })] },
    });

    await screen.findByText(/review extracted expense/i);
    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    expect(await screen.findByText(/unable to save/i)).toBeInTheDocument();
    expect(screen.getByText(/review extracted expense/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm expense/i })).toBeEnabled();
  });
});
