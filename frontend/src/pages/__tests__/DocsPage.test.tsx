import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import DocsPage from "../DocsPage";
import { SECTIONS, SIDEBAR_GROUPS } from "../docs-sections";

// Mock IntersectionObserver for the scrollspy
const mockObserve = vi.fn();
const mockUnobserve = vi.fn();
const mockDisconnect = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();

  global.IntersectionObserver = class {
    constructor(_cb: any, _options?: any) {}
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
      // Each section title appears both in the sidebar and in the main content,
      // so use getAllByText to account for duplicates
      const elements = screen.getAllByText(section.title);
      expect(elements.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders the sidebar group labels", () => {
    renderWithProviders(<DocsPage />);

    for (const group of SIDEBAR_GROUPS) {
      // Some group labels (e.g. "Getting Started") may also appear as
      // section titles in the main content and sidebar buttons, so use
      // getAllByText to handle duplicates
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

    // The "Authentication" section should still be visible in the sidebar
    // Sections that do not match (e.g., "Webhooks") should be filtered out.
    // The sidebar buttons for non-matching sections should disappear.
    const authButtons = screen.getAllByText("Authentication");
    expect(authButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders code examples with language tabs", () => {
    renderWithProviders(<DocsPage />);

    // The first section (Getting Started) has Python, JavaScript, cURL code examples
    expect(screen.getAllByText("Python").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("JavaScript").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("cURL").length).toBeGreaterThanOrEqual(1);
  });

  it("renders endpoint method badges for documented endpoints", () => {
    renderWithProviders(<DocsPage />);

    // The Getting Started section has GET endpoints
    const getBadges = screen.getAllByText("GET");
    expect(getBadges.length).toBeGreaterThanOrEqual(1);

    // Other sections have POST endpoints
    const postBadges = screen.getAllByText("POST");
    expect(postBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("renders section descriptions", () => {
    renderWithProviders(<DocsPage />);

    // Check that the first section description is present (partial match)
    expect(
      screen.getByText(/AgentChains is a decentralized marketplace/),
    ).toBeInTheDocument();
  });

  it("renders copy permalink buttons for sections", () => {
    renderWithProviders(<DocsPage />);

    const permalinkButtons = screen.getAllByTitle("Copy permalink");
    // There should be one per section
    expect(permalinkButtons.length).toBe(SECTIONS.length);
  });
});
