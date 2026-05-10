import { describe, expect, it, beforeEach, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";

import type { Conversation } from "@/entities/conversation/model/types";
import type {
  ConfirmInventoryImportForExpenseResponse,
  DocumentIntakeResponse,
  ExpenseDraftResponse,
} from "@/entities/expense/model/types";
import type { ConfirmExtractedExpenseResponse } from "@/features/send-message/model/receipt-expense-schema";
import { ApiError } from "@/shared/api/errors";
import { renderWithProviders } from "@/test/test-utils";

import { ChatWindow } from "./chat-window";

const {
  mockCreateDocumentIntake,
  mockUpdateInventoryImportPreviewLines,
  mockConfirmInventoryImportForExpense,
  mockConfirmExtractedExpense,
  mockAddNotification,
  mockConversationsQueryData,
  mockConversationQuery,
  mockStreamAgentMessage,
  mockSetConversationId,
  mockClearConversationId,
  mockChatStoreState,
  mockGetSession,
  mockSignOut,
} = vi.hoisted(() => ({
  mockCreateDocumentIntake: vi.fn(),
  mockUpdateInventoryImportPreviewLines: vi.fn(),
  mockConfirmInventoryImportForExpense: vi.fn(),
  mockConfirmExtractedExpense: vi.fn(),
  mockAddNotification: vi.fn(),
  mockConversationsQueryData: [] as Conversation[],
  mockConversationQuery: { data: null as Conversation | null, isError: false },
  mockStreamAgentMessage: vi.fn(),
  mockSetConversationId: vi.fn(),
  mockClearConversationId: vi.fn(),
  mockChatStoreState: { conversationId: null as string | null },
  mockGetSession: vi.fn(),
  mockSignOut: vi.fn(),
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "token-1" } }),
  getSession: () => mockGetSession(),
  signOut: (...args: unknown[]) => mockSignOut(...args),
}));

vi.mock("@/entities/conversation/api/queries", () => ({
  useConversations: () => ({ data: mockConversationsQueryData, isError: false }),
  useConversation: () => mockConversationQuery,
}));

vi.mock("@/shared/store/chat-store", () => ({
  useChatStore: (
    selector: (s: {
      getConversationId: () => string | null;
      setConversationId: typeof mockSetConversationId;
      clearConversationId: typeof mockClearConversationId;
    }) => unknown,
  ) =>
    selector({
      getConversationId: () => mockChatStoreState.conversationId,
      setConversationId: mockSetConversationId,
      clearConversationId: mockClearConversationId,
    }),
}));

vi.mock("@/shared/store/notification-store", () => ({
  useNotificationStore: () => ({ addNotification: mockAddNotification }),
}));

vi.mock("@/features/send-message/api/stream-message", () => ({
  streamAgentMessage: (...args: unknown[]) => mockStreamAgentMessage(...args),
}));

vi.mock("@/features/send-message/api/receipt-expense", () => ({
  createDocumentIntake: (input: unknown) => mockCreateDocumentIntake(input),
  updateInventoryImportPreviewLines: (input: unknown) => mockUpdateInventoryImportPreviewLines(input),
  confirmInventoryImportForExpense: (input: unknown) => mockConfirmInventoryImportForExpense(input),
  confirmExtractedExpense: (input: unknown) => mockConfirmExtractedExpense(input),
}));

vi.mock("@/entities/conversation/ui/message-list", () => ({
  MessageList: ({ messages, streamingContent }: {
    messages: Array<{ content: string; created_at?: string; role?: string }>;
    streamingContent?: string;
  }) => (
    <div data-testid="message-list">
      {messages.map((message) => (
        <p key={`${message.role ?? "message"}:${message.created_at ?? ""}:${message.content}`}>{message.content}</p>
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

const receiptIntakeResponse: DocumentIntakeResponse = {
  ...receiptDraftResponse,
  type: "receipt_expense_review",
  classification: {
    document_type: "receipt",
    confidence: 0.9,
    warnings: [],
  },
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

const supplierInvoiceInventoryReviewResponse: DocumentIntakeResponse = {
  ...invoiceDraftResponse,
  type: "supplier_invoice_inventory_review",
  classification: {
    document_type: "supplier_invoice",
    confidence: 0.92,
    warnings: [],
  },
  inventory_import_preview: {
    id: "preview-1",
    user_id: "u1",
    company_id: "company-1",
    document_id: "doc-2",
    source_type: "supplier_invoice_upload",
    status: "draft",
    lines: [
      {
        candidate: {
          description: "Consulting line",
          sku: null,
          barcode: null,
          quantity: "1",
          unit: "pcs",
          unit_price: "42.00",
        },
        matched_item_id: null,
        proposed_item: null,
        location_id: "loc-1",
        receipt_quantity: "1",
        warnings: [],
      },
    ],
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
};

const supplierInvoiceExpenseReviewAfterInventory: ConfirmInventoryImportForExpenseResponse = {
  type: "supplier_invoice_expense_review",
  inventory_import_result: {
    preview_id: "preview-1",
    items_created: 1,
    items_updated: 0,
    movements_created: 1,
  },
  inventory_import_preview: {
    ...supplierInvoiceInventoryReviewResponse.inventory_import_preview,
    status: "confirmed",
  },
  draft: invoiceDraftResponse.draft,
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

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conversation-1",
    agent_id: "agent-1",
    company_id: "company-1",
    title: "Old conversation title",
    messages: [],
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    ...overrides,
  };
}

function getFileInput() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
  if (!input) throw new Error("Expected file input to exist");
  return input;
}

describe("ChatWindow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConversationsQueryData.length = 0;
    mockConversationQuery.data = null;
    mockConversationQuery.isError = false;
    mockChatStoreState.conversationId = null;
    mockGetSession.mockResolvedValue({ accessToken: "token-1" });

    mockSetConversationId.mockImplementation((_agentId, _companyId, conversationId) => {
      mockChatStoreState.conversationId = conversationId;
    });
    mockClearConversationId.mockImplementation(() => {
      mockChatStoreState.conversationId = null;
    });
    mockStreamAgentMessage.mockImplementation(async function* () {
      yield { event: "done", data: { conversation_id: "c1" } };
    });
  });

  it("starts with a new empty conversation on agent open", () => {
    mockConversationsQueryData.push(
      makeConversation({
        id: "old-1",
        messages: [{ role: "user", content: "old message", created_at: "2026-05-01T00:00:00Z", metadata: {} }],
      }),
    );
    mockChatStoreState.conversationId = null;

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);

    expect(within(screen.getByTestId("message-list")).queryByText("old message")).not.toBeInTheDocument();
    expect(screen.getByText(/start a new conversation/i)).toBeInTheDocument();
  });

  it("shows old conversations in a menu using the latest message as title", async () => {
    const user = userEvent.setup();

    mockConversationsQueryData.push(
      makeConversation({
        id: "old-1",
        messages: [
          { role: "user", content: "first message", created_at: "2026-05-01T00:00:00Z", metadata: {} },
          {
            role: "assistant",
            content: "latest assistant answer with details",
            created_at: "2026-05-01T00:01:00Z",
            metadata: {},
          },
        ],
      }),
    );

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.click(screen.getByText(/conversations/i));

    expect(screen.getByRole("button", { name: /latest assistant answer with details/i })).toBeInTheDocument();
  });

  it("reopens a selected old conversation from the menu", async () => {
    const user = userEvent.setup();

    mockConversationsQueryData.push(
      makeConversation({
        id: "old-1",
        title: "Old conversation title",
      }),
    );
    mockConversationQuery.data = makeConversation({
      id: "old-1",
      messages: [{ role: "user", content: "reopened history", created_at: "2026-05-01T00:02:00Z", metadata: {} }],
    });
    mockConversationQuery.isError = false;

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.click(screen.getByText(/conversations/i));
    await user.click(screen.getByRole("button", { name: /old conversation title/i }));

    expect(mockSetConversationId).toHaveBeenCalledWith("agent-1", "company-1", "old-1");
    expect(await screen.findByText("reopened history")).toBeInTheDocument();
  });

  it("shows thinking feedback before the first streamed token", async () => {
    const user = userEvent.setup();
    const firstTokenGate = deferred<void>();

    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield { event: "conversation", data: { conversation_id: "c1" } };
      await firstTokenGate.promise;
      yield { event: "token", data: { content: "partial" } };
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "hello{Enter}");

    expect(await screen.findByText(/agent is thinking/i)).toBeInTheDocument();

    await act(async () => {
      firstTokenGate.resolve(undefined);
    });
    await waitFor(() => {
      expect(screen.getByText("partial")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.queryByText(/agent is thinking/i)).not.toBeInTheDocument();
    });
  });

  it("renders streamed tokens before the done event completes", async () => {
    const user = userEvent.setup();
    const doneGate = deferred<void>();

    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield { event: "conversation", data: { conversation_id: "c1" } };
      yield { event: "token", data: { content: "partial" } };
      await doneGate.promise;
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "hello{Enter}");

    expect(await screen.findByText("partial")).toBeInTheDocument();
    await act(async () => {
      doneGate.resolve(undefined);
    });
  });

  it("ignores route events and still completes streamed response", async () => {
    const user = userEvent.setup();
    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield { event: "conversation", data: { conversation_id: "c1" } };
      yield {
        event: "route",
        data: {
          predicted_route: "general",
          executed_route: "general",
          reason: "greeting",
          confidence: 0.91,
          company_id: null,
          company_scope: "unassigned",
        },
      };
      yield { event: "token", data: { content: "Hello" } };
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId={null} />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "hi{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });
    expect(screen.queryByText("greeting")).not.toBeInTheDocument();
  });

  it("accepts tool trace events without rendering trace payload in messages", async () => {
    const user = userEvent.setup();
    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield { event: "conversation", data: { conversation_id: "c1" } };
      yield {
        event: "tool_trace",
        data: {
          tool_name: "search_inventory_stock",
          phase: "on_tool_end",
          args_preview: "{\"query\":\"iphone\"}",
          duration_ms: 25,
          status: "ok",
          output_bytes: 16,
        },
      };
      yield { event: "token", data: { content: "Hello" } };
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "hi{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });
    expect(screen.queryByText(/search_inventory_stock/)).not.toBeInTheDocument();
  });

  it("renders prefilled stock movement form from inventory draft event", async () => {
    const user = userEvent.setup();
    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield {
        event: "inventory_movement_draft",
        data: {
          movement_draft: {
            company_id: "company-1",
            item_id: "item-42",
            location_id: "loc-default",
            movement_type: "receipt",
            quantity_delta: "250",
            reason: "restock",
          },
        },
      };
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "add stock{Enter}");

    expect(await screen.findByText(/review stock movement draft/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("item-42")).toBeInTheDocument();
    expect(screen.getByDisplayValue("loc-default")).toBeInTheDocument();
    expect(screen.getByDisplayValue("250")).toBeInTheDocument();
  });

  it("refocuses the message input after a new assistant message is added", async () => {
    const user = userEvent.setup();
    const doneGate = deferred<void>();

    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield { event: "conversation", data: { conversation_id: "c1" } };
      yield { event: "token", data: { content: "partial" } };
      await doneGate.promise;
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    const textarea = screen.getByPlaceholderText(/message your agent/i);
    await user.type(textarea, "hello{Enter}");
    expect(await screen.findByText("partial")).toBeInTheDocument();

    const focusTarget = document.createElement("button");
    document.body.appendChild(focusTarget);
    focusTarget.focus();
    expect(focusTarget).toHaveFocus();

    await act(async () => {
      doneGate.resolve(undefined);
    });
    await waitFor(() => {
      expect(textarea).toHaveFocus();
    });
    focusTarget.remove();
  });

  it("scrolls when a new chat message is added", async () => {
    const user = userEvent.setup();
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView");

    mockStreamAgentMessage.mockImplementationOnce(async function* () {
      yield { event: "token", data: { content: "token" } };
      yield { event: "done", data: { conversation_id: "c1" } };
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "hello{Enter}");

    await waitFor(() => {
      expect(scrollSpy).toHaveBeenCalledWith({ behavior: "smooth", block: "end" });
    });
    scrollSpy.mockRestore();
  });

  it("upload is disabled when the agent has no company", () => {
    renderWithProviders(<ChatWindow agentId="agent-1" companyId={null} />);
    expect(screen.getByRole("button", { name: /attach document/i })).toBeDisabled();
  });

  it("renders returned draft and confirms edited values; clears draft and invalidates queries", async () => {
    const user = userEvent.setup();

    mockCreateDocumentIntake.mockResolvedValueOnce(receiptIntakeResponse);
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
      expect(mockCreateDocumentIntake).toHaveBeenCalledWith(
        expect.objectContaining({
          requestedType: "auto",
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

    mockCreateDocumentIntake.mockRejectedValueOnce(new ApiError(500, "Upload failed", null));

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), { target: { files: [file] } });

    await waitFor(() => {
      expect(mockAddNotification).toHaveBeenCalledWith("Upload failed", "error");
    });
  });

  it("successful invoice confirmation displays supplier partner details in message and toast", async () => {
    const user = userEvent.setup();

    mockCreateDocumentIntake.mockResolvedValueOnce({
      ...invoiceDraftResponse,
      type: "supplier_invoice_expense_review",
      classification: {
        document_type: "supplier_invoice",
        confidence: 0.9,
        warnings: [],
      },
    });
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
    const pendingDraft = deferred<DocumentIntakeResponse>();
    mockCreateDocumentIntake.mockReturnValueOnce(pendingDraft.promise);

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["receipt"], "receipt.pdf", { type: "application/pdf" })] },
    });

    expect(await screen.findByText(/reading document and preparing review/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /processing document/i })).toBeDisabled();

    pendingDraft.resolve(receiptIntakeResponse);
    expect(await screen.findByText(/review extracted expense/i)).toBeInTheDocument();
  });

  it("shows recording progress while confirmation is pending", async () => {
    const user = userEvent.setup();
    mockCreateDocumentIntake.mockResolvedValueOnce(receiptIntakeResponse);
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
    mockCreateDocumentIntake.mockResolvedValueOnce(receiptIntakeResponse);

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
    mockCreateDocumentIntake.mockResolvedValueOnce(receiptIntakeResponse);
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

  it("requires inventory approval before supplier invoice expense approval", async () => {
    const user = userEvent.setup();
    mockCreateDocumentIntake.mockResolvedValueOnce(supplierInvoiceInventoryReviewResponse);
    mockUpdateInventoryImportPreviewLines.mockResolvedValueOnce(
      supplierInvoiceInventoryReviewResponse.inventory_import_preview,
    );
    mockConfirmInventoryImportForExpense.mockResolvedValueOnce(supplierInvoiceExpenseReviewAfterInventory);
    mockConfirmExtractedExpense.mockResolvedValueOnce(invoiceConfirmationResponse);

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["invoice"], "invoice.pdf", { type: "application/pdf" })] },
    });

    expect(await screen.findByText(/review inventory import/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm inventory/i }));

    await waitFor(() => {
      expect(mockUpdateInventoryImportPreviewLines).toHaveBeenCalledWith(
        expect.objectContaining({
          previewId: "preview-1",
          token: "token-1",
          lines: expect.any(Array),
        }),
      );
      expect(mockConfirmInventoryImportForExpense).toHaveBeenCalledWith(
        expect.objectContaining({
          agentId: "agent-1",
          previewId: "preview-1",
          token: "token-1",
        }),
      );
      expect(mockUpdateInventoryImportPreviewLines.mock.invocationCallOrder[0]).toBeLessThan(
        mockConfirmInventoryImportForExpense.mock.invocationCallOrder[0],
      );
    });

    expect(await screen.findByText(/review extracted supplier invoice expense/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm expense/i }));

    await waitFor(() => {
      expect(mockAddNotification).toHaveBeenCalledWith(
        "Expense recorded: Invoice Vendor. Supplier partner created.",
        "success",
      );
    });
  });

  it("keeps user in inventory review when preview patch fails", async () => {
    const user = userEvent.setup();
    mockCreateDocumentIntake.mockResolvedValueOnce(supplierInvoiceInventoryReviewResponse);
    mockUpdateInventoryImportPreviewLines.mockRejectedValueOnce(
      new ApiError(500, "Unable to update lines", null),
    );

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["invoice"], "invoice.pdf", { type: "application/pdf" })] },
    });

    expect(await screen.findByText(/review inventory import/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm inventory/i }));

    expect(await screen.findByText(/unable to update lines/i)).toBeInTheDocument();
    expect(mockConfirmInventoryImportForExpense).not.toHaveBeenCalled();
    expect(screen.getByText(/review inventory import/i)).toBeInTheDocument();
  });

  it("keeps user in inventory review when confirm fails after successful patch", async () => {
    const user = userEvent.setup();
    mockCreateDocumentIntake.mockResolvedValueOnce(supplierInvoiceInventoryReviewResponse);
    mockUpdateInventoryImportPreviewLines.mockResolvedValueOnce(
      supplierInvoiceInventoryReviewResponse.inventory_import_preview,
    );
    mockConfirmInventoryImportForExpense.mockRejectedValueOnce(
      new ApiError(500, "Unable to confirm inventory", null),
    );

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    fireEvent.change(getFileInput(), {
      target: { files: [new File(["invoice"], "invoice.pdf", { type: "application/pdf" })] },
    });

    expect(await screen.findByText(/review inventory import/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm inventory/i }));

    expect(await screen.findByText(/unable to confirm inventory/i)).toBeInTheDocument();
    expect(mockUpdateInventoryImportPreviewLines).toHaveBeenCalledTimes(1);
    expect(mockConfirmInventoryImportForExpense).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/review inventory import/i)).toBeInTheDocument();
  });

  it("redirects to login when chat stream returns unauthorized", async () => {
    const user = userEvent.setup();
    mockStreamAgentMessage.mockReturnValueOnce({
      [Symbol.asyncIterator]: () => ({
        next: async () => {
          throw new Error("SSE request failed with status 401");
        },
      }),
    });

    renderWithProviders(<ChatWindow agentId="agent-1" companyId="company-1" />);
    await user.type(screen.getByPlaceholderText(/message your agent/i), "hello{Enter}");

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: "/login" });
    });
  });
});
