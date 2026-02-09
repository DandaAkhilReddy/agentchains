/// <reference types="vitest/globals" />
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ProtectedRoute } from "../components/layout/ProtectedRoute";
import { useAuthStore } from "../store/authStore";

// Auth is paused — ProtectedRoute always renders children

describe("ProtectedRoute (auth paused)", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, loading: false });
  });

  it("always renders children regardless of auth state", () => {
    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("renders children even when loading is true", () => {
    useAuthStore.setState({ user: null, loading: true });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("renders children even when user is null", () => {
    useAuthStore.setState({ user: null, loading: false });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("does not redirect to /login", () => {
    useAuthStore.setState({ user: null, loading: false });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
  });

  it("does not show a spinner", () => {
    useAuthStore.setState({ user: null, loading: true });

    const { container } = render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(container.querySelector(".animate-spin")).toBeNull();
  });
});
