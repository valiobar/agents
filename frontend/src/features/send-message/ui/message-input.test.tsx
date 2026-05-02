import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/test-utils";

import { MessageInput } from "./message-input";

describe("MessageInput", () => {
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

