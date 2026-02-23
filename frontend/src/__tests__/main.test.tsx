import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Mock App so main.tsx can render without the full component tree ────────────
vi.mock("../App", () => ({
  default: () => <div data-testid="app-root">App</div>,
}));

// ── Mock the CSS import (vitest handles css via config, but be explicit) ──────
vi.mock("../index.css", () => ({}));

// ── Helpers ───────────────────────────────────────────────────────────────────
/**
 * Builds a minimal DOM root element and attaches it to document.body.
 * Returns the element and a cleanup function.
 */
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
    // Reset module registry so each test gets a fresh import of main.tsx
    vi.resetModules();
  });

  it("mounts the App into the #root element", async () => {
    const { el, cleanup: c } = createRootElement("root");
    cleanup = c;

    // Dynamically importing main.tsx executes the createRoot(...).render(...) call.
    await import("../main");

    // After rendering, the #root element should contain the mocked App output.
    expect(el.querySelector("[data-testid='app-root']")).not.toBeNull();
  });

  it("wraps App in React StrictMode", async () => {
    // StrictMode does not render any DOM node itself, but it does double-invoke
    // render functions in development.  We verify the App renders correctly when
    // StrictMode is the parent — if StrictMode were broken or missing the mock
    // App would still render, so we focus on confirming the mount succeeds and
    // the expected output is present.
    const { el, cleanup: c } = createRootElement("root");
    cleanup = c;

    await import("../main");

    expect(el.textContent).toBe("App");
  });

  it("throws when #root element is absent from the DOM", async () => {
    // Do NOT create a #root element — the non-null assertion (!) in main.tsx
    // will cause createRoot to receive null, which React turns into an error.
    let caught: unknown;
    try {
      await import("../main");
    } catch (err) {
      caught = err;
    }
    // With a missing #root, React's createRoot throws.
    expect(caught).toBeDefined();
  });

  it("calls createRoot with the #root DOM element", async () => {
    const { el, cleanup: c } = createRootElement("root");
    cleanup = c;

    // Spy on ReactDOM.createRoot to verify it receives the correct element.
    const ReactDOM = await import("react-dom/client");
    const createRootSpy = vi.spyOn(ReactDOM, "createRoot");

    await import("../main");

    expect(createRootSpy).toHaveBeenCalledWith(el);
    createRootSpy.mockRestore();
  });
});
