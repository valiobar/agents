import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/shared/api/errors";
import { makeSalesInvoiceReview } from "@/test/sales-invoice-fixtures";
import { renderWithProviders } from "@/test/test-utils";

import { SalesInvoiceDraftConfirmation } from "./sales-invoice-draft-confirmation";

describe("SalesInvoiceDraftConfirmation", () => {
  it("submits edited invoice draft values", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <SalesInvoiceDraftConfirmation
        review={makeSalesInvoiceReview()}
        onCancel={() => undefined}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByText(/review sales invoice draft/i)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/counterparty/i));
    await user.type(screen.getByLabelText(/counterparty/i), "Edited Acme");
    await user.clear(screen.getByLabelText(/notes/i));
    await user.type(screen.getByLabelText(/notes/i), "Edited notes");
    await user.clear(screen.getByLabelText(/description/i));
    await user.type(screen.getByLabelText(/description/i), "Edited line");
    await user.clear(screen.getByLabelText(/^quantity$/i));
    await user.type(screen.getByLabelText(/^quantity$/i), "4");
    await user.clear(screen.getByLabelText(/unit price/i));
    await user.type(screen.getByLabelText(/unit price/i), "11.00");

    await user.click(screen.getByRole("button", { name: /create draft invoice/i }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        counterparty: "Edited Acme",
        notes: "Edited notes",
        items: [
          expect.objectContaining({
            description: "Edited line",
            quantity: "4",
            unit_price: "11.00",
            inventory_item_id: "item-1",
            inventory_location_id: "loc-1",
          }),
        ],
      }),
    );
  });

  it("shows api error message when invoice creation fails", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockRejectedValue(new ApiError(500, "Unable to create invoice", null));

    renderWithProviders(
      <SalesInvoiceDraftConfirmation
        review={makeSalesInvoiceReview()}
        onCancel={() => undefined}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole("button", { name: /create draft invoice/i }));
    expect(await screen.findByText("Unable to create invoice")).toBeInTheDocument();
  });

  it("renders confirmed state without confirmation actions", () => {
    renderWithProviders(
      <SalesInvoiceDraftConfirmation
        review={makeSalesInvoiceReview()}
        confirmed
        onCancel={() => undefined}
        onConfirm={() => undefined}
      />,
    );

    expect(screen.getByText(/sales invoice created/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create draft invoice/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/counterparty/i)).toBeDisabled();
  });
});
