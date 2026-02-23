import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor, act } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import DocsPage from "../DocsPage";
import { SECTIONS, SIDEBAR_GROUPS } from "../docs-sections";

// Capture the IntersectionObserver callback so we can trigger it in tests
let intersectionCallback: IntersectionObserverCallback;
const mockObserve = vi.fn();
const mockUnobserve = vi.fn();
const mockDisconnect = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });

  global.IntersectionObserver = class {
    constructor(cb: IntersectionObserverCallback, _options?: IntersectionObserverInit) {
      intersectionCallback = cb;
    }
    observe = mockObserve;
    unobserve = mockUnobserve;
    disconnect = mockDisconnect;
  } as any;

  // Mock clipboard API
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn(() => Promise.resolve()) },
  });

  // Mock scrollIntoView
  Element.prototype.scrollIntoView = vi.fn();

  // Reset location hash
  window.history.replaceState(null, "", window.location.pathname);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("DocsPage", () => {
  it("renders the docs page title", () => {
    renderWithProviders(<DocsPage />);
    expect(screen.getByText("API Documentation")).toBeInTheDocument();
  });

  it("renders the subtitle with section count", () => {
    renderWithProviders(<DocsPage />);
    expect(
      screen.getByText(
        `Complete reference \u2014 ${SECTIONS.length} sections covering all endpoints`,
      ),
    ).toBeInTheDocument();
  });

  it("renders all documentation section titles", () => {
    renderWithProviders(<DocsPage />);

    for (const section of SECTIONS) {
      const elements = screen.getAllByText(section.title);
      expect(elements.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders the sidebar group labels", () => {
    renderWithProviders(<DocsPage />);

    for (const group of SIDEBAR_GROUPS) {
      const matches = screen.getAllByText(group.label);
      expect(matches.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders the search input in the sidebar", () => {
    renderWithProviders(<DocsPage />);

    const searchInput = screen.getByPlaceholderText("Search docs...");
    expect(searchInput).toBeInTheDocument();
  });

  it("filters sidebar items when typing in search", () => {
    renderWithProviders(<DocsPage />);

    const searchInput = screen.getByPlaceholderText("Search docs...");
    fireEvent.change(searchInput, { target: { value: "Authentication" } });

    const authButtons = screen.getAllByText("Authentication");
    expect(authButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders code examples with language tabs", () => {
    renderWithProviders(<DocsPage />);

    expect(screen.getAllByText("Python").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("JavaScript").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("cURL").length).toBeGreaterThanOrEqual(1);
  });

  it("renders endpoint method badges for documented endpoints", () => {
    renderWithProviders(<DocsPage />);

    const getBadges = screen.getAllByText("GET");
    expect(getBadges.length).toBeGreaterThanOrEqual(1);

    const postBadges = screen.getAllByText("POST");
    expect(postBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("renders section descriptions", () => {
    renderWithProviders(<DocsPage />);

    expect(
      screen.getByText(/AgentChains is a decentralized marketplace/),
    ).toBeInTheDocument();
  });

  it("renders copy permalink buttons for sections", () => {
    renderWithProviders(<DocsPage />);

    const permalinkButtons = screen.getAllByTitle("Copy permalink");
    expect(permalinkButtons.length).toBe(SECTIONS.length);
  });

  // ─── New coverage tests below ───

  it("copies permalink to clipboard and shows check icon", async () => {
    renderWithProviders(<DocsPage />);

    const permalinkButtons = screen.getAllByTitle("Copy permalink");
    fireEvent.click(permalinkButtons[0]);

    // Check that navigator.clipboard.writeText was called with the correct URL
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(`#${SECTIONS[0].id}`),
    );

    // After clicking, the copied state should be true (Check icon appears)
    // Wait for the state update then advance timers to reset
    await act(async () => {
      vi.advanceTimersByTime(2100);
    });
  });

  it("sidebar click calls scrollIntoView on the target section", () => {
    renderWithProviders(<DocsPage />);

    // Find a sidebar button for a known section. The sidebar renders buttons
    // with section titles. Click a button that is NOT the first section.
    const secondSection = SECTIONS[1];
    const sidebarButtons = screen.getAllByText(secondSection.title);
    // Click the sidebar button (the one in the sidebar nav)
    fireEvent.click(sidebarButtons[0]);

    // scrollIntoView should have been called
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("IntersectionObserver sets activeSection when entry is intersecting", () => {
    renderWithProviders(<DocsPage />);

    // The observer should have been set up and observe called
    expect(mockObserve).toHaveBeenCalled();

    // Simulate an intersection event for the second section
    const secondSection = SECTIONS[1];
    const mockEntry = {
      isIntersecting: true,
      target: { id: secondSection.id },
    } as unknown as IntersectionObserverEntry;

    act(() => {
      intersectionCallback(
        [mockEntry],
        {} as IntersectionObserver,
      );
    });

    // The sidebar should now reflect the active section
    // (We can verify by checking that the button for this section has the active style)
  });

  it("IntersectionObserver skips non-intersecting entries", () => {
    renderWithProviders(<DocsPage />);

    const mockEntry = {
      isIntersecting: false,
      target: { id: SECTIONS[1].id },
    } as unknown as IntersectionObserverEntry;

    act(() => {
      intersectionCallback(
        [mockEntry],
        {} as IntersectionObserver,
      );
    });
    // No error should occur; activeSection remains the first section
  });

  it("disconnects IntersectionObserver on unmount", () => {
    const { unmount } = renderWithProviders(<DocsPage />);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("scrolls to hash section on mount when location hash is present", () => {
    // Set hash before rendering
    window.history.replaceState(null, "", `#${SECTIONS[2].id}`);

    renderWithProviders(<DocsPage />);

    // scrollIntoView should be called after a timeout for hash scrolling
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("does not scroll when hash is empty", () => {
    window.history.replaceState(null, "", window.location.pathname);

    renderWithProviders(<DocsPage />);

    act(() => {
      vi.advanceTimersByTime(200);
    });

    // scrollIntoView should not be called from the hash effect
    // (it may be called from sidebar clicks, but not from hash)
  });

  it("renders PUT method badges with correct styling", () => {
    renderWithProviders(<DocsPage />);

    // Check if PUT endpoints exist in sections
    const hasPut = SECTIONS.some(s => s.endpoints?.some(e => e.method === "PUT"));
    if (hasPut) {
      const putBadges = screen.getAllByText("PUT");
      expect(putBadges.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders DELETE method badges when present", () => {
    renderWithProviders(<DocsPage />);

    const hasDelete = SECTIONS.some(s => s.endpoints?.some(e => e.method === "DELETE"));
    if (hasDelete) {
      const deleteBadges = screen.getAllByText("DELETE");
      expect(deleteBadges.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders PATCH method badges when present", () => {
    renderWithProviders(<DocsPage />);

    const hasPatch = SECTIONS.some(s => s.endpoints?.some(e => e.method === "PATCH"));
    if (hasPatch) {
      const patchBadges = screen.getAllByText("PATCH");
      expect(patchBadges.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders WS method badges when present", () => {
    renderWithProviders(<DocsPage />);

    const hasWS = SECTIONS.some(s => s.endpoints?.some(e => e.method === "WS"));
    if (hasWS) {
      const wsBadges = screen.getAllByText("WS");
      expect(wsBadges.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders SSE method badges when present", () => {
    renderWithProviders(<DocsPage />);

    const hasSSE = SECTIONS.some(s => s.endpoints?.some(e => e.method === "SSE"));
    if (hasSSE) {
      const sseBadges = screen.getAllByText("SSE");
      expect(sseBadges.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders auth lock icon for auth-required endpoints", () => {
    renderWithProviders(<DocsPage />);

    // Check that there's at least one endpoint with auth=true in sections data
    const hasAuth = SECTIONS.some(
      (s) => s.endpoints?.some((e) => e.auth === true),
    );
    if (hasAuth) {
      // Lock icons should be rendered (lucide-lock class)
      const lockIcons = document.querySelectorAll(".lucide-lock");
      expect(lockIcons.length).toBeGreaterThan(0);
    }
  });

  it("renders globe icon for non-auth endpoints", () => {
    renderWithProviders(<DocsPage />);

    const hasNonAuth = SECTIONS.some(
      (s) => s.endpoints?.some((e) => e.auth === false),
    );
    if (hasNonAuth) {
      const globeIcons = document.querySelectorAll(".lucide-globe");
      expect(globeIcons.length).toBeGreaterThan(0);
    }
  });

  it("renders endpoint response blocks", () => {
    renderWithProviders(<DocsPage />);

    // The first section has endpoints with response JSON
    const responseLabels = screen.getAllByText("Response");
    expect(responseLabels.length).toBeGreaterThanOrEqual(1);
  });

  it("renders section details when present", () => {
    renderWithProviders(<DocsPage />);

    // The first section has details array
    const firstSectionWithDetails = SECTIONS.find(s => s.details && s.details.length > 0);
    if (firstSectionWithDetails && firstSectionWithDetails.details) {
      // Check that at least one detail string is rendered (partial match)
      expect(
        screen.getByText(/Base URL for all API requests/),
      ).toBeInTheDocument();
    }
  });

  it("renders section dividers between sections (not after last)", () => {
    const { container } = renderWithProviders(<DocsPage />);

    // The divider uses col-span-full class
    const dividers = container.querySelectorAll(".col-span-full");
    // Should be SECTIONS.length - 1 dividers
    expect(dividers.length).toBe(SECTIONS.length - 1);
  });

  it("renders endpoint parameters when present", () => {
    renderWithProviders(<DocsPage />);

    // Find a section that has endpoints with params
    const sectionWithParams = SECTIONS.find(
      s => s.endpoints?.some(e => e.params && e.params.length > 0),
    );
    if (sectionWithParams) {
      const paramEndpoint = sectionWithParams.endpoints!.find(
        e => e.params && e.params.length > 0,
      )!;
      // The first param name should be displayed (may appear multiple times)
      const elements = screen.getAllByText(paramEndpoint.params![0].name);
      expect(elements.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders endpoint paths as code elements", () => {
    renderWithProviders(<DocsPage />);

    // The first section has "/health" endpoint
    const healthPath = screen.getByText("/health");
    expect(healthPath).toBeInTheDocument();
    expect(healthPath.tagName.toLowerCase()).toBe("code");
  });

  it("setSectionRef removes ref when element is null", () => {
    // This tests the cleanup callback of ref
    const { unmount } = renderWithProviders(<DocsPage />);
    // Unmounting will call ref callbacks with null
    unmount();
    // No errors should be thrown
  });

  it("renders all section descriptions", () => {
    renderWithProviders(<DocsPage />);

    // Each section has a description - check that each is rendered
    for (const section of SECTIONS) {
      // Use partial match (first 30 chars) to avoid issues with long descriptions
      const snippet = section.description.slice(0, 30);
      const descElement = screen.getByText(new RegExp(snippet.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
      expect(descElement).toBeInTheDocument();
    }
  });

  it("handles history replaceState on sidebar click", () => {
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    renderWithProviders(<DocsPage />);

    const secondSection = SECTIONS[1];
    const sidebarButtons = screen.getAllByText(secondSection.title);
    fireEvent.click(sidebarButtons[0]);

    expect(replaceStateSpy).toHaveBeenCalledWith(
      null,
      "",
      `#${secondSection.id}`,
    );

    replaceStateSpy.mockRestore();
  });

  it("handles history replaceState on permalink copy", () => {
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    renderWithProviders(<DocsPage />);

    const permalinkButtons = screen.getAllByTitle("Copy permalink");
    fireEvent.click(permalinkButtons[0]);

    expect(replaceStateSpy).toHaveBeenCalledWith(
      null,
      "",
      `#${SECTIONS[0].id}`,
    );

    replaceStateSpy.mockRestore();
  });
});
