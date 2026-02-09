/// <reference types="vitest/globals" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { LoginPage } from "../components/auth/LoginPage";

// Mock useAuth hook
const mockLoginWithGoogle = vi.fn();
const mockLoginWithEmail = vi.fn();
const mockSignupWithEmail = vi.fn();
const mockResetPassword = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    loginWithGoogle: mockLoginWithGoogle,
    loginWithEmail: mockLoginWithEmail,
    signupWithEmail: mockSignupWithEmail,
    resetPassword: mockResetPassword,
    user: null,
    loading: false,
    logout: vi.fn(),
  }),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderLoginPage = () =>
    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    );

  describe("Initial Render", () => {
    it("renders sign-in form with email and password fields", () => {
      renderLoginPage();
      expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("••••••••")).toBeInTheDocument();
    });

    it("renders Google sign-in button", () => {
      renderLoginPage();
      expect(screen.getByText("auth.continueWithGoogle")).toBeInTheDocument();
    });

    it("renders sign-in and sign-up tabs", () => {
      renderLoginPage();
      // "auth.signIn" appears as both tab and submit button, so use getAllByText
      const signInElements = screen.getAllByText("auth.signIn");
      expect(signInElements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("auth.signUp")).toBeInTheDocument();
    });
  });

  describe("View Switching", () => {
    it("switches to sign-up view when Sign Up tab clicked", () => {
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.signUp"));
      expect(screen.getByPlaceholderText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("auth.createAccount")).toBeInTheDocument();
    });

    it("switches to forgot-password view when Forgot Password clicked", () => {
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.forgotPassword"));
      expect(screen.getByText("auth.resetPassword")).toBeInTheDocument();
      expect(screen.getByText("auth.sendResetLink")).toBeInTheDocument();
      expect(screen.getByText("auth.backToSignIn")).toBeInTheDocument();
    });

    it("switches back to sign-in from forgot-password", () => {
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.forgotPassword"));
      fireEvent.click(screen.getByText("auth.backToSignIn"));
      expect(screen.getByText("auth.forgotPassword")).toBeInTheDocument();
    });

    it("hides tab toggle in forgot-password view", () => {
      renderLoginPage();
      expect(screen.getByText("auth.signUp")).toBeInTheDocument();
      fireEvent.click(screen.getByText("auth.forgotPassword"));
      expect(screen.queryByText("auth.signUp")).not.toBeInTheDocument();
    });
  });

  describe("Google Sign-In", () => {
    it("calls loginWithGoogle when Google button clicked", async () => {
      mockLoginWithGoogle.mockResolvedValue(undefined);
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.continueWithGoogle"));
      await waitFor(() => {
        expect(mockLoginWithGoogle).toHaveBeenCalledTimes(1);
      });
    });

    it("navigates to home on successful Google login", async () => {
      mockLoginWithGoogle.mockResolvedValue(undefined);
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.continueWithGoogle"));
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/");
      });
    });

    it("displays error message on Google login failure", async () => {
      mockLoginWithGoogle.mockRejectedValue({ code: "auth/popup-closed-by-user" });
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.continueWithGoogle"));
      await waitFor(() => {
        expect(screen.getByText("Sign-in popup was closed. Try again.")).toBeInTheDocument();
      });
    });

    it("displays generic error for unknown error codes", async () => {
      mockLoginWithGoogle.mockRejectedValue({ code: "auth/unknown-error" });
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.continueWithGoogle"));
      await waitFor(() => {
        expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
      });
    });
  });

  describe("Email Sign-In Validation", () => {
    it("validates required email field", () => {
      renderLoginPage();
      // Submit with empty email by clicking the submit button (not the tab)
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.emailRequired")).toBeInTheDocument();
      expect(mockLoginWithEmail).not.toHaveBeenCalled();
    });

    it("validates password minimum length", () => {
      renderLoginPage();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "test@example.com" },
      });
      fireEvent.change(screen.getByPlaceholderText("••••••••"), {
        target: { value: "short" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.passwordMinLength")).toBeInTheDocument();
      expect(mockLoginWithEmail).not.toHaveBeenCalled();
    });

    it("submits form with valid credentials", async () => {
      mockLoginWithEmail.mockResolvedValue(undefined);
      renderLoginPage();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "test@example.com" },
      });
      fireEvent.change(screen.getByPlaceholderText("••••••••"), {
        target: { value: "password123" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(mockLoginWithEmail).toHaveBeenCalledWith("test@example.com", "password123");
      });
    });

    it("navigates to home on successful email sign-in", async () => {
      mockLoginWithEmail.mockResolvedValue(undefined);
      renderLoginPage();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "test@example.com" },
      });
      fireEvent.change(screen.getByPlaceholderText("••••••••"), {
        target: { value: "password123" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/");
      });
    });

    it("displays error on sign-in failure", async () => {
      mockLoginWithEmail.mockRejectedValue({ code: "auth/wrong-password" });
      renderLoginPage();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "test@example.com" },
      });
      fireEvent.change(screen.getByPlaceholderText("••••••••"), {
        target: { value: "wrongpass1" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(
          screen.getByText("Incorrect password. Try again or reset your password.")
        ).toBeInTheDocument();
      });
    });
  });

  describe("Email Sign-Up Validation", () => {
    const switchToSignUp = () => {
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.signUp"));
    };

    it("validates display name required", () => {
      switchToSignUp();
      // Fill email + password + confirm but leave name empty
      const inputs = screen.getAllByPlaceholderText("you@example.com");
      const emailInput = inputs[0]; // email field in sign-up
      const pwInputs = screen.getAllByPlaceholderText("••••••••");
      fireEvent.change(emailInput, { target: { value: "test@example.com" } });
      fireEvent.change(pwInputs[0], { target: { value: "password123" } });
      fireEvent.change(pwInputs[1], { target: { value: "password123" } });
      const form = emailInput.closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.nameRequired")).toBeInTheDocument();
      expect(mockSignupWithEmail).not.toHaveBeenCalled();
    });

    it("validates email required in sign-up", () => {
      switchToSignUp();
      fireEvent.change(screen.getByPlaceholderText("John Doe"), {
        target: { value: "John Doe" },
      });
      const form = screen.getByPlaceholderText("John Doe").closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.emailRequired")).toBeInTheDocument();
      expect(mockSignupWithEmail).not.toHaveBeenCalled();
    });

    it("validates password minimum length in sign-up", () => {
      switchToSignUp();
      fireEvent.change(screen.getByPlaceholderText("John Doe"), {
        target: { value: "John Doe" },
      });
      const emailInput = screen.getAllByPlaceholderText("you@example.com")[0];
      const pwInputs = screen.getAllByPlaceholderText("••••••••");
      fireEvent.change(emailInput, { target: { value: "test@example.com" } });
      fireEvent.change(pwInputs[0], { target: { value: "short" } });
      const form = emailInput.closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.passwordMinLength")).toBeInTheDocument();
      expect(mockSignupWithEmail).not.toHaveBeenCalled();
    });

    it("validates password match", () => {
      switchToSignUp();
      fireEvent.change(screen.getByPlaceholderText("John Doe"), {
        target: { value: "John Doe" },
      });
      const emailInput = screen.getAllByPlaceholderText("you@example.com")[0];
      const pwInputs = screen.getAllByPlaceholderText("••••••••");
      fireEvent.change(emailInput, { target: { value: "test@example.com" } });
      fireEvent.change(pwInputs[0], { target: { value: "password123" } });
      fireEvent.change(pwInputs[1], { target: { value: "password456" } });
      const form = emailInput.closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.passwordMismatch")).toBeInTheDocument();
      expect(mockSignupWithEmail).not.toHaveBeenCalled();
    });

    it("submits form with valid sign-up data", async () => {
      mockSignupWithEmail.mockResolvedValue(undefined);
      switchToSignUp();
      fireEvent.change(screen.getByPlaceholderText("John Doe"), {
        target: { value: "John Doe" },
      });
      const emailInput = screen.getAllByPlaceholderText("you@example.com")[0];
      const pwInputs = screen.getAllByPlaceholderText("••••••••");
      fireEvent.change(emailInput, { target: { value: "test@example.com" } });
      fireEvent.change(pwInputs[0], { target: { value: "password123" } });
      fireEvent.change(pwInputs[1], { target: { value: "password123" } });
      const form = emailInput.closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(mockSignupWithEmail).toHaveBeenCalledWith(
          "test@example.com",
          "password123",
          "John Doe"
        );
      });
    });

    it("navigates to home on successful sign-up", async () => {
      mockSignupWithEmail.mockResolvedValue(undefined);
      switchToSignUp();
      fireEvent.change(screen.getByPlaceholderText("John Doe"), {
        target: { value: "John Doe" },
      });
      const emailInput = screen.getAllByPlaceholderText("you@example.com")[0];
      const pwInputs = screen.getAllByPlaceholderText("••••••••");
      fireEvent.change(emailInput, { target: { value: "test@example.com" } });
      fireEvent.change(pwInputs[0], { target: { value: "password123" } });
      fireEvent.change(pwInputs[1], { target: { value: "password123" } });
      const form = emailInput.closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/");
      });
    });

    it("displays error on sign-up failure", async () => {
      mockSignupWithEmail.mockRejectedValue({ code: "auth/email-already-in-use" });
      switchToSignUp();
      fireEvent.change(screen.getByPlaceholderText("John Doe"), {
        target: { value: "John Doe" },
      });
      const emailInput = screen.getAllByPlaceholderText("you@example.com")[0];
      const pwInputs = screen.getAllByPlaceholderText("••••••••");
      fireEvent.change(emailInput, { target: { value: "existing@example.com" } });
      fireEvent.change(pwInputs[0], { target: { value: "password123" } });
      fireEvent.change(pwInputs[1], { target: { value: "password123" } });
      const form = emailInput.closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(
          screen.getByText("An account with this email already exists. Try signing in.")
        ).toBeInTheDocument();
      });
    });
  });

  describe("Password Reset", () => {
    const switchToForgotPassword = () => {
      renderLoginPage();
      fireEvent.click(screen.getByText("auth.forgotPassword"));
    };

    it("validates email required for password reset", () => {
      switchToForgotPassword();
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      expect(screen.getByText("auth.emailRequired")).toBeInTheDocument();
      expect(mockResetPassword).not.toHaveBeenCalled();
    });

    it("submits reset password request", async () => {
      mockResetPassword.mockResolvedValue(undefined);
      switchToForgotPassword();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "test@example.com" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(mockResetPassword).toHaveBeenCalledWith("test@example.com");
      });
    });

    it("displays success message after password reset", async () => {
      mockResetPassword.mockResolvedValue(undefined);
      switchToForgotPassword();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "test@example.com" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(screen.getByText("auth.resetSuccess")).toBeInTheDocument();
      });
    });

    it("displays error on password reset failure", async () => {
      mockResetPassword.mockRejectedValue({ code: "auth/user-not-found" });
      switchToForgotPassword();
      fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
        target: { value: "nonexistent@example.com" },
      });
      const form = screen.getByPlaceholderText("you@example.com").closest("form")!;
      fireEvent.submit(form);
      await waitFor(() => {
        expect(
          screen.getByText("No account found with this email. Try signing up.")
        ).toBeInTheDocument();
      });
    });
  });

  describe("Error Messages", () => {
    it("displays all mapped auth error codes", async () => {
      const errorCodes = [
        { code: "auth/invalid-email", message: "Please enter a valid email address." },
        { code: "auth/user-disabled", message: "This account has been disabled. Contact support." },
        { code: "auth/too-many-requests", message: "Too many attempts. Please try again later." },
        { code: "auth/popup-blocked", message: "Sign-in popup was blocked. Allow popups for this site." },
      ];

      for (const { code, message } of errorCodes) {
        vi.clearAllMocks();
        mockLoginWithGoogle.mockRejectedValue({ code });
        const { unmount } = renderLoginPage();
        fireEvent.click(screen.getByText("auth.continueWithGoogle"));
        await waitFor(() => {
          expect(screen.getByText(message)).toBeInTheDocument();
        });
        unmount();
      }
    });
  });
});
