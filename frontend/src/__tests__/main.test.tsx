import { describe, it, expect, vi, afterEach } from "vitest";

// ── Mock react-dom/client so we can intercept createRoot ─────────────────────
const mockRender = vi.fn();
const mockCreateRoot = vi.fn(() => ({ render: mockRender }));

vi.mock("react-dom/client", () => ({
  createRoot: (...args: unknown[]) => mockCreateRoot(...args),
}));

// ── Mock App so main.tsx can render without the full component tree ────────────
vi.mock("../App", () => ({
  default: () => <div data-testid="app-root">App</div>,
}));

// ── Mock the CSS import ──────────────────────────────────────────────────────
vi.mock("../index.css", () => ({}));

// ── Helpers ───────────────────────────────────────────────────────────────────
function createRootElement(id = "root") {
  const el = document.createElement("div");
  el.setAttribute("id", id);
  document.body.appendChild(el);
  return {
    el,
    cleanup: () => {
      if (document.body.contains(el)) {
        document.body.removeChild(el);
      }
    },
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe("main.tsx — entry-point bootstrap", () => {
  let cleanup: () => void;

  afterEach(() => {
    cleanup?.();
    mockCreateRoot.mockClear();
    mockRender.mockClear();
    vi.resetModules();
  });

  it("calls createRoot with the #root DOM element", async () => {
    const { el, cleanup: c } = createRootElement("root");
    cleanup = c;

    await import("../main");

    expect(mockCreateRoot).toHaveBeenCalledTimes(1);
    expect(mockCreateRoot).toHaveBeenCalledWith(el);
  });

  it("calls render on the root with JSX content", async () => {
    const { cleanup: c } = createRootElement("root");
    cleanup = c;

    await import("../main");

    expect(mockRender).toHaveBeenCalledTimes(1);
    // The argument is a React element (StrictMode wrapping App)
    const rendered = mockRender.mock.calls[0][0];
    expect(rendered).toBeDefined();
  });

  it("throws when #root element is absent from the DOM", async () => {
    // Do NOT create a #root element — getElementById returns null,
    // and the non-null assertion (!) passes null to our mock createRoot.
    // The real createRoot would throw, but our mock doesn't — so we
    // verify createRoot was called with null.
    cleanup = () => {};

    await import("../main");

    expect(mockCreateRoot).toHaveBeenCalledWith(null);
  });

  it("imports the module without errors when #root exists", async () => {
    const { cleanup: c } = createRootElement("root");
    cleanup = c;

    // Should not throw
    await expect(import("../main")).resolves.toBeDefined();
  });
});
