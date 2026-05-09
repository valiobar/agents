import { describe, expect, it, beforeEach, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";

import { renderWithProviders } from "@/test/test-utils";

import { CreateAgentForm } from "./create-agent-form";

const { mockMutateAsync } = vi.hoisted(() => ({
  mockMutateAsync: vi.fn(),
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: { accessToken: "token-1" } }),
}));

vi.mock("@/entities/company/api/queries", () => ({
  useCompanies: () => ({ isLoading: false, data: [] }),
}));

vi.mock("../api/mutations", () => ({
  useCreateAgent: () => ({
    mutateAsync: (input: unknown) => mockMutateAsync(input),
    isPending: false,
  }),
}));

describe("CreateAgentForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMutateAsync.mockResolvedValue({ id: "agent-1" });
  });

  it("renders Router as an available agent type", () => {
    renderWithProviders(<CreateAgentForm />);
    expect(screen.getByRole("button", { name: /router/i })).toBeInTheDocument();
  });

  it("submits router as selected agent type", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateAgentForm />);

    await user.click(screen.getByRole("button", { name: /router/i }));
    await user.type(screen.getByLabelText(/name/i), "Ops Router");
    await user.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Ops Router",
          agent_type: "router",
        }),
      );
    });
  });
});
