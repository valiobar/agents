import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/shared/api/errors";
import { renderWithProviders } from "@/test/test-utils";
import { makeSalesInvoiceInventoryReview } from "@/test/sales-invoice-fixtures";

import { SalesInvoiceInventoryConfirmation } from "./sales-invoice-inventory-confirmation";

describe("SalesInvoiceInventoryConfirmation", () => {
  it("submits selected item/location and edited line values", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const review = makeSalesInvoiceInventoryReview();
    const ambiguousReview = {
      ...review,
      lines: review.lines.map((line) => ({
        ...line,
        selected_item_id: null,
        selected_location_id: null,
        available_quantity: null,
      })),
    };

    renderWithProviders(
      <SalesInvoiceInventoryConfirmation
        review={ambiguousReview}
        onCancel={() => undefined}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByText(/review sales invoice inventory lines/i)).toBeInTheDocument();
    expect(screen.getAllByText("Widget A").length).toBeGreaterThan(0);

    await user.clear(screen.getByLabelText(/description/i));
    await user.type(screen.getByLabelText(/description/i), "Edited Widget");
    await user.clear(screen.getByLabelText(/^quantity$/i));
    await user.type(screen.getByLabelText(/^quantity$/i), "3");
    await user.clear(screen.getByLabelText(/unit price/i));
    await user.type(screen.getByLabelText(/unit price/i), "12.50");
    await user.clear(screen.getByLabelText(/vat rate/i));
    await user.type(screen.getByLabelText(/vat rate/i), "9");

    expect(screen.getByText("37.50")).toBeInTheDocument();
    expect(screen.getByText("3.38")).toBeInTheDocument();
    expect(screen.getByText("40.88")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /continue to invoice draft/i }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        selected_partner_id: "partner-1",
        lines: [
          expect.objectContaining({
            description: "Edited Widget",
            quantity: "3",
            unit_price: "12.50",
            vat_rate: "0.09",
            inventory_item_id: "item-1",
            inventory_location_id: "loc-1",
          }),
        ],
      }),
    );
  });

  it("shows api error message when inventory confirmation fails", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockRejectedValue(new ApiError(500, "Unable to prepare draft", null));

    renderWithProviders(
      <SalesInvoiceInventoryConfirmation
        review={makeSalesInvoiceInventoryReview()}
        onCancel={() => undefined}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole("button", { name: /continue to invoice draft/i }));
    expect(await screen.findByText("Unable to prepare draft")).toBeInTheDocument();
  });

  it("disables actions while confirming", () => {
    renderWithProviders(
      <SalesInvoiceInventoryConfirmation
        review={makeSalesInvoiceInventoryReview()}
        confirming
        onCancel={() => undefined}
        onConfirm={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: /preparing invoice draft/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
    expect(screen.getByLabelText(/description/i)).toBeDisabled();
  });
});
