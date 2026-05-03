import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { renderWithProviders } from "@/test/test-utils";

import { MessageInput } from "./message-input";

describe("MessageInput", () => {
  it("clears the message and keeps textarea focused after Enter send", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();

    renderWithProviders(<MessageInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText(/message your agent/i);
    await user.click(textarea);
    await user.type(textarea, " hello agent {Enter}");

    expect(onSend).toHaveBeenCalledWith("hello agent");
    expect(textarea).toHaveValue("");
    expect(textarea).toHaveFocus();
  });

  it("restores textarea focus after the input is re-enabled following send", async () => {
    const user = userEvent.setup();
    let resolveSend!: () => void;
    const sendPromise = new Promise<void>((resolve) => {
      resolveSend = resolve;
    });
    const onSend = vi.fn(() => sendPromise);
    const { rerender } = render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText(/message your agent/i);
    await user.click(textarea);
    await user.type(textarea, "hello agent{Enter}");

    rerender(<MessageInput onSend={onSend} disabled />);
    const focusTarget = document.createElement("button");
    document.body.appendChild(focusTarget);
    focusTarget.focus();
    expect(focusTarget).toHaveFocus();

    rerender(<MessageInput onSend={onSend} />);
    await waitFor(() => {
      expect(textarea).toHaveFocus();
    });
    focusTarget.remove();
    await act(async () => {
      resolveSend();
      await sendPromise;
    });
  });

  it("attachment change calls onReceiptSelected", async () => {
    const onReceiptSelected = vi.fn();
    renderWithProviders(
      <MessageInput onSend={() => undefined} onReceiptSelected={onReceiptSelected} />,
    );

    const file = new File(["receipt"], "receipt.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
    if (!input) {
      throw new Error("Expected file input to exist");
    }

    fireEvent.change(input, { target: { files: [file] } });
    expect(onReceiptSelected).toHaveBeenCalledWith(file);
  });

  it("upload is disabled when receiptUploadDisabled is true", () => {
    renderWithProviders(
      <MessageInput onSend={() => undefined} receiptUploadDisabled onReceiptSelected={() => undefined} />,
    );

    expect(screen.getByRole("button", { name: /attach document/i })).toBeDisabled();
  });

  it("upload label changes while receiptUploadLoading is true", () => {
    renderWithProviders(
      <MessageInput
        onSend={() => undefined}
        receiptUploadLoading
        onReceiptSelected={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: /processing document/i })).toBeEnabled();
  });

  it("shows processing label and disabled state when both loading and upload disabled", () => {
    renderWithProviders(
      <MessageInput
        onSend={() => undefined}
        onReceiptSelected={() => undefined}
        receiptUploadLoading
        receiptUploadDisabled
      />,
    );

    expect(screen.getByRole("button", { name: /processing document/i })).toBeDisabled();
  });
});

