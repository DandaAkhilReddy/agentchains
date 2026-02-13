import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CreatorLoginPage from "../CreatorLoginPage";

describe("CreatorLoginPage", () => {
  const mockOnLogin = vi.fn();
  const mockOnRegister = vi.fn();

  const defaultProps = {
    onLogin: mockOnLogin,
    onRegister: mockOnRegister,
    loading: false,
    error: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders login form by default", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    expect(screen.getByText("Creator Login")).toBeInTheDocument();
    expect(screen.getByText("Sign in to manage your agents and earnings")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min. 8 characters")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Your Name")).not.toBeInTheDocument();
  });

  it("shows register form when toggled", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    const toggleButton = screen.getByText("Don't have an account? Sign up");
    fireEvent.click(toggleButton);

    expect(screen.getByRole("heading", { name: "Create Account" })).toBeInTheDocument();
    expect(screen.getByText("Join AgentChains and start earning")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Your Name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min. 8 characters")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("+91...")).toBeInTheDocument();
    expect(screen.getByText("Country")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("login form submission calls onLogin with email and password", async () => {
    mockOnLogin.mockResolvedValue(undefined);
    render(<CreatorLoginPage {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("you@example.com");
    const passwordInput = screen.getByPlaceholderText("Min. 8 characters");
    const submitButton = screen.getByRole("button", { name: /sign in/i });

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith("test@example.com", "password123");
      expect(mockOnLogin).toHaveBeenCalledTimes(1);
    });
  });

  it("register form submission calls onRegister with all required data", async () => {
    mockOnRegister.mockResolvedValue(undefined);
    render(<CreatorLoginPage {...defaultProps} />);

    // Switch to register mode
    const toggleButton = screen.getByText("Don't have an account? Sign up");
    fireEvent.click(toggleButton);

    fireEvent.change(screen.getByPlaceholderText("Your Name"), { target: { value: "John Doe" } });
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "john@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("Min. 8 characters"), { target: { value: "password123" } });
    fireEvent.change(screen.getByPlaceholderText("+91..."), { target: { value: "+919876543210" } });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "US" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockOnRegister).toHaveBeenCalledWith({
        email: "john@example.com",
        password: "password123",
        display_name: "John Doe",
        phone: "+919876543210",
        country: "US",
      });
      expect(mockOnRegister).toHaveBeenCalledTimes(1);
    });
  });

  it("shows loading state during submission", () => {
    render(<CreatorLoginPage {...defaultProps} loading={true} />);

    const submitButton = screen.getByRole("button", { name: /sign in/i });

    expect(submitButton).toBeDisabled();
  });

  it("shows error message on failure", () => {
    const errorMessage = "Invalid credentials. Please try again.";
    render(<CreatorLoginPage {...defaultProps} error={errorMessage} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it("form is disabled during loading", () => {
    render(<CreatorLoginPage {...defaultProps} loading={true} />);

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    expect(submitButton).toBeDisabled();
  });

  it("toggles between login and register modes correctly", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    // Initially in login mode
    expect(screen.getByText("Creator Login")).toBeInTheDocument();
    expect(screen.getByText("Don't have an account? Sign up")).toBeInTheDocument();

    // Switch to register
    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    expect(screen.getByRole("heading", { name: "Create Account" })).toBeInTheDocument();
    expect(screen.getByText("Already have an account? Sign in")).toBeInTheDocument();

    // Switch back to login
    fireEvent.click(screen.getByText("Already have an account? Sign in"));

    expect(screen.getByText("Creator Login")).toBeInTheDocument();
    expect(screen.getByText("Don't have an account? Sign up")).toBeInTheDocument();
  });

  it("email and password inputs are required in login mode", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    const emailInput = screen.getByPlaceholderText("you@example.com") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText("Min. 8 characters") as HTMLInputElement;

    expect(emailInput.required).toBe(true);
    expect(passwordInput.required).toBe(true);
  });

  it("display name, email, and password inputs are required in register mode", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    const displayNameInput = screen.getByPlaceholderText("Your Name") as HTMLInputElement;
    const emailInput = screen.getByPlaceholderText("you@example.com") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText("Min. 8 characters") as HTMLInputElement;
    const phoneInput = screen.getByPlaceholderText("+91...") as HTMLInputElement;

    expect(displayNameInput.required).toBe(true);
    expect(emailInput.required).toBe(true);
    expect(passwordInput.required).toBe(true);
    expect(phoneInput.required).toBe(false); // Phone is optional
  });

  it("password input has minimum length requirement", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    const passwordInput = screen.getByPlaceholderText("Min. 8 characters") as HTMLInputElement;

    expect(passwordInput.minLength).toBe(8);
  });

  it("displays welcome credit information", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    expect(screen.getByText(/\$0\.10 welcome credit!/i)).toBeInTheDocument();
    expect(screen.getByText(/Create your agents via OpenClaw/i)).toBeInTheDocument();
  });

  it("register form calls onRegister without optional phone when not provided", async () => {
    mockOnRegister.mockResolvedValue(undefined);
    render(<CreatorLoginPage {...defaultProps} />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    fireEvent.change(screen.getByPlaceholderText("Your Name"), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("Min. 8 characters"), { target: { value: "securepass123" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockOnRegister).toHaveBeenCalledWith({
        email: "jane@example.com",
        password: "securepass123",
        display_name: "Jane Doe",
        phone: undefined,
        country: "IN",
      });
    });
  });

  it("country selector defaults to India (IN)", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    const countrySelect = screen.getByRole("combobox") as HTMLSelectElement;
    expect(countrySelect.value).toBe("IN");
  });

  it("country selector includes multiple country options", () => {
    render(<CreatorLoginPage {...defaultProps} />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    expect(screen.getByRole("option", { name: "India" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "United States" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "United Kingdom" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Germany" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Japan" })).toBeInTheDocument();
  });

  it("does not show error when error is null", () => {
    render(<CreatorLoginPage {...defaultProps} error={null} />);

    const errorElements = document.querySelectorAll(".bg-red-500\\/10");
    expect(errorElements.length).toBe(0);
  });

  it("form submission with empty phone treats it as undefined", async () => {
    mockOnRegister.mockResolvedValue(undefined);
    render(<CreatorLoginPage {...defaultProps} />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    fireEvent.change(screen.getByPlaceholderText("Your Name"), { target: { value: "Test User" } });
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("Min. 8 characters"), { target: { value: "password123" } });
    fireEvent.change(screen.getByPlaceholderText("+91..."), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockOnRegister).toHaveBeenCalledWith({
        email: "test@example.com",
        password: "password123",
        display_name: "Test User",
        phone: undefined,
        country: "IN",
      });
    });
  });
});
