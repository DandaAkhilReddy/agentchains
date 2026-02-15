import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/test-utils";
import RoleLandingPage from "../RoleLandingPage";

describe("RoleLandingPage", () => {
  it("renders all role cards", () => {
    renderWithProviders(<RoleLandingPage onNavigate={vi.fn()} />);

    expect(screen.getByText("Agent Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Creator Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Admin Dashboard")).toBeInTheDocument();
  });

  it("navigates to agent dashboard when clicked", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderWithProviders(<RoleLandingPage onNavigate={onNavigate} />);

    await user.click(screen.getByRole("button", { name: /Agent Dashboard/i }));
    expect(onNavigate).toHaveBeenCalledWith("agentDashboard");
  });
});
