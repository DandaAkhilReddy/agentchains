/// <reference types="vitest/globals" />
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ProtectedRoute } from "../components/layout/ProtectedRoute";
import { useAuthStore } from "../store/authStore";
import type { User } from "firebase/auth";

// Mock Navigate to a simple div so we can detect redirects
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    Navigate: vi.fn(({ to, replace }: { to: string; replace?: boolean }) => (
      <div data-testid="navigate" data-to={to} data-replace={String(replace)}>
        Navigate Mock
      </div>
    )),
  };
});

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, loading: false });
  });

  it("shows spinner when loading is true", () => {
    useAuthStore.setState({ user: null, loading: true });

    const { container } = render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeTruthy();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("spinner has correct CSS classes", () => {
    useAuthStore.setState({ user: null, loading: true });

    const { container } = render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    const spinner = container.querySelector(".animate-spin")!;
    expect(spinner.className).toContain("rounded-full");
    expect(spinner.className).toContain("h-8");
    expect(spinner.className).toContain("w-8");
    expect(spinner.className).toContain("border-b-2");
    expect(spinner.className).toContain("border-blue-600");
  });

  it("redirects to /login when user is null and loading is false", () => {
    useAuthStore.setState({ user: null, loading: false });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    const navigate = screen.getByTestId("navigate");
    expect(navigate).toBeInTheDocument();
    expect(navigate.getAttribute("data-to")).toBe("/login");
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("Navigate has replace prop", () => {
    useAuthStore.setState({ user: null, loading: false });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    const navigate = screen.getByTestId("navigate");
    expect(navigate.getAttribute("data-replace")).toBe("true");
  });

  it("renders children when user exists and loading is false", () => {
    const mockUser = { uid: "test-uid", email: "test@example.com" } as User;
    useAuthStore.setState({ user: mockUser, loading: false });

    const { container } = render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
    expect(container.querySelector(".animate-spin")).toBeNull();
  });
});
