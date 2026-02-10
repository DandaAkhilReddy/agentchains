/// <reference types="vitest/globals" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatBot } from "../components/chat/ChatBot";

// Mock api module
const mockPost = vi.fn();
vi.mock("../lib/api", () => ({
  default: {
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

// Mock crypto.randomUUID (not available in jsdom)
let uuidCounter = 0;
vi.stubGlobal("crypto", {
  ...globalThis.crypto,
  randomUUID: () => `test-uuid-${++uuidCounter}`,
});

// Mock scrollIntoView (not implemented in jsdom)
Element.prototype.scrollIntoView = vi.fn();

// Helper: wrap component with QueryClientProvider
function renderChatBot() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatBot />
    </QueryClientProvider>
  );
}

describe("ChatBot", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uuidCounter = 0;
  });

  // -------------------------------------------------------
  // 1. Renders chat toggle button
  // -------------------------------------------------------
  it("renders the chat toggle button", () => {
    renderChatBot();
    const toggleButton = screen.getByRole("button", { name: "chat.openChat" });
    expect(toggleButton).toBeInTheDocument();
  });

  // -------------------------------------------------------
  // 2. Opens chat panel on click
  // -------------------------------------------------------
  it("opens the chat panel when the toggle button is clicked", () => {
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));
    expect(screen.getByText("chat.title")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("chat.placeholder")).toBeInTheDocument();
  });

  // -------------------------------------------------------
  // 3. Closes chat panel on X click
  // -------------------------------------------------------
  it("closes the chat panel when the close button is clicked", () => {
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));
    expect(screen.getByText("chat.title")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "chat.closeChat" }));
    expect(screen.queryByText("chat.title")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "chat.openChat" })).toBeInTheDocument();
  });

  // -------------------------------------------------------
  // 4. Shows welcome message when opened
  // -------------------------------------------------------
  it("shows the welcome message when chat is opened", () => {
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));
    expect(screen.getByText("chat.welcome")).toBeInTheDocument();
    expect(screen.getByText("chat.welcomeDesc")).toBeInTheDocument();
  });

  // -------------------------------------------------------
  // 5. Shows 3 suggestion chips
  // -------------------------------------------------------
  it("shows 3 suggestion chips in the welcome view", () => {
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));
    expect(screen.getByText("chat.suggestion1")).toBeInTheDocument();
    expect(screen.getByText("chat.suggestion2")).toBeInTheDocument();
    expect(screen.getByText("chat.suggestion3")).toBeInTheDocument();
  });

  // -------------------------------------------------------
  // 6. Input field accepts text
  // -------------------------------------------------------
  it("allows typing into the input field", () => {
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));
    const input = screen.getByPlaceholderText("chat.placeholder") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "How do I reduce my EMI?" } });
    expect(input.value).toBe("How do I reduce my EMI?");
  });

  // -------------------------------------------------------
  // 7. Send button submits message
  // -------------------------------------------------------
  it("calls api.post when the send button is clicked with text", async () => {
    mockPost.mockResolvedValue({ data: { text: "AI reply" } });
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));

    const input = screen.getByPlaceholderText("chat.placeholder");
    fireEvent.change(input, { target: { value: "Hello" } });

    // The send button is the last button inside the input area
    const sendButtons = screen.getAllByRole("button");
    const sendButton = sendButtons[sendButtons.length - 1];
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/ai/chat", expect.objectContaining({
        message: "Hello",
      }));
    });
  });

  // -------------------------------------------------------
  // 8. User message appears in chat
  // -------------------------------------------------------
  it("displays the user message in the chat after sending", async () => {
    mockPost.mockResolvedValue({ data: { text: "Response" } });
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));

    const input = screen.getByPlaceholderText("chat.placeholder");
    fireEvent.change(input, { target: { value: "My question" } });

    const sendButtons = screen.getAllByRole("button");
    const sendButton = sendButtons[sendButtons.length - 1];
    fireEvent.click(sendButton);

    expect(screen.getByText("My question")).toBeInTheDocument();
    // The welcome message should disappear once there are messages
    expect(screen.queryByText("chat.welcome")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------
  // 9. Shows loading indicator during API call
  // -------------------------------------------------------
  it("shows a loading indicator while the API call is pending", async () => {
    // Never resolve so mutation stays pending
    mockPost.mockReturnValue(new Promise(() => {}));
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));

    const input = screen.getByPlaceholderText("chat.placeholder");
    fireEvent.change(input, { target: { value: "Test message" } });

    const sendButtons = screen.getAllByRole("button");
    const sendButton = sendButtons[sendButtons.length - 1];
    fireEvent.click(sendButton);

    // The Loader2 icon renders with the animate-spin class
    await waitFor(() => {
      const spinner = document.querySelector(".animate-spin");
      expect(spinner).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------
  // 10. Displays AI response after success
  // -------------------------------------------------------
  it("displays the AI response after a successful API call", async () => {
    mockPost.mockResolvedValue({ data: { text: "Here is your answer." } });
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));

    const input = screen.getByPlaceholderText("chat.placeholder");
    fireEvent.change(input, { target: { value: "Explain loans" } });

    const sendButtons = screen.getAllByRole("button");
    const sendButton = sendButtons[sendButtons.length - 1];
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText("Here is your answer.")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------
  // 11. Shows error toast on failure
  // -------------------------------------------------------
  it("displays an error message in chat on API failure", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));

    const input = screen.getByPlaceholderText("chat.placeholder");
    fireEvent.change(input, { target: { value: "Will this fail?" } });

    const sendButtons = screen.getAllByRole("button");
    const sendButton = sendButtons[sendButtons.length - 1];
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText("chat.errorResponse")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------
  // 12. Enter key submits message
  // -------------------------------------------------------
  it("submits the message when Enter key is pressed", async () => {
    mockPost.mockResolvedValue({ data: { text: "Enter reply" } });
    renderChatBot();
    fireEvent.click(screen.getByRole("button", { name: "chat.openChat" }));

    const input = screen.getByPlaceholderText("chat.placeholder");
    fireEvent.change(input, { target: { value: "Enter test" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/ai/chat", expect.objectContaining({
        message: "Enter test",
      }));
    });

    // The user message should also appear
    expect(screen.getByText("Enter test")).toBeInTheDocument();

    // And the input should be cleared
    expect((input as HTMLInputElement).value).toBe("");
  });
});
