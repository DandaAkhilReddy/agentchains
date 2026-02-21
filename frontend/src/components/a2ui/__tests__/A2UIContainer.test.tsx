import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import A2UIContainer from "../A2UIContainer";
import type { A2UIComponent, A2UIProgressMessage } from "../../../types/a2ui";

/* ─── helpers ─── */

/** Build an A2UIComponent with sensible defaults */
function makeComponent(
  overrides: Partial<A2UIComponent> & { component_type: A2UIComponent["component_type"] },
): A2UIComponent {
  return {
    component_id: overrides.component_id ?? `comp-${Math.random().toString(36).slice(2, 8)}`,
    component_type: overrides.component_type,
    data: overrides.data ?? {},
    metadata: overrides.metadata,
  };
}

/* ═══════════════════════════════════════════════════════
   1. Empty / fallback states
   ═══════════════════════════════════════════════════════ */

describe("A2UIContainer — empty states", () => {
  it("renders empty placeholder when components array is empty and no progress", () => {
    render(<A2UIContainer components={[]} />);
    expect(screen.getByText("No components rendered yet.")).toBeInTheDocument();
  });

  it("renders empty placeholder when components Map is empty and no progress", () => {
    render(<A2UIContainer components={new Map()} />);
    expect(screen.getByText("No components rendered yet.")).toBeInTheDocument();
  });

  it("renders empty placeholder when components array is empty and progress Map is empty", () => {
    render(<A2UIContainer components={[]} progress={new Map()} />);
    expect(screen.getByText("No components rendered yet.")).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════════════════
   2. Renders each component_type through the switch
   ═══════════════════════════════════════════════════════ */

describe("A2UIContainer — card type", () => {
  it("renders card component type via A2UICard", () => {
    const comp = makeComponent({
      component_type: "card",
      data: { title: "My Card Title" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("My Card Title")).toBeInTheDocument();
  });
});

describe("A2UIContainer — table type", () => {
  it("renders table component type via A2UITable", () => {
    const comp = makeComponent({
      component_type: "table",
      data: { headers: ["Name", "Score"], rows: [["Alice", 95]] },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
  });
});

describe("A2UIContainer — form type", () => {
  it("renders form component type via A2UIForm", () => {
    const comp = makeComponent({
      component_type: "form",
      data: {
        title: "Contact Form",
        fields: [{ name: "email", label: "Email", type: "text" }],
      },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Contact Form")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
  });
});

describe("A2UIContainer — chart type", () => {
  it("renders chart component type with title", () => {
    const comp = makeComponent({
      component_type: "chart",
      data: { title: "Revenue Chart" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Revenue Chart")).toBeInTheDocument();
    expect(screen.getByText("Chart")).toBeInTheDocument();
  });

  it("renders chart fallback title when data.title is missing", () => {
    const comp = makeComponent({
      component_type: "chart",
      data: { series: [1, 2, 3] },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Chart component")).toBeInTheDocument();
  });

  it("renders chart data as JSON", () => {
    const comp = makeComponent({
      component_type: "chart",
      data: { values: [10, 20] },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText(/"values"/)).toBeInTheDocument();
  });
});

describe("A2UIContainer — markdown type", () => {
  it("renders markdown component with content", () => {
    const comp = makeComponent({
      component_type: "markdown",
      data: { content: "Hello **world**" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Hello **world**")).toBeInTheDocument();
  });

  it("renders markdown with empty content when content is missing", () => {
    const comp = makeComponent({
      component_type: "markdown",
      data: {},
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const prose = container.querySelector(".prose");
    expect(prose).toBeInTheDocument();
    expect(prose!.textContent).toBe("");
  });
});

describe("A2UIContainer — code type", () => {
  it("renders code component with source", () => {
    const comp = makeComponent({
      component_type: "code",
      data: { source: 'console.log("hi")', language: "javascript" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText('console.log("hi")')).toBeInTheDocument();
    expect(screen.getByText("javascript")).toBeInTheDocument();
  });

  it("renders code component with content fallback when source is missing", () => {
    const comp = makeComponent({
      component_type: "code",
      data: { content: "print('hello')" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("print('hello')")).toBeInTheDocument();
  });

  it("renders code component with empty string when no source or content", () => {
    const comp = makeComponent({
      component_type: "code",
      data: {},
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const codeEl = container.querySelector("code");
    expect(codeEl).toBeInTheDocument();
    expect(codeEl!.textContent).toBe("");
  });

  it("does not render language badge when language is missing", () => {
    const comp = makeComponent({
      component_type: "code",
      data: { source: "x = 1" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    // The language badge uses uppercase tracking-wider — check it does not exist
    const badges = container.querySelectorAll("span.uppercase");
    expect(badges.length).toBe(0);
  });
});

describe("A2UIContainer — image type", () => {
  it("renders image component with src and alt", () => {
    const comp = makeComponent({
      component_type: "image",
      data: { src: "https://example.com/photo.png", alt: "A photo" },
    });
    render(<A2UIContainer components={[comp]} />);
    const img = screen.getByAltText("A photo");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/photo.png");
    // alt text also shown as caption
    expect(screen.getByText("A photo")).toBeInTheDocument();
  });

  it("renders image with url fallback when src is missing", () => {
    const comp = makeComponent({
      component_type: "image",
      data: { url: "https://example.com/pic.jpg" },
    });
    render(<A2UIContainer components={[comp]} />);
    const img = screen.getByRole("presentation");
    expect(img).toHaveAttribute("src", "https://example.com/pic.jpg");
  });

  it("renders image with empty alt when alt is missing", () => {
    const comp = makeComponent({
      component_type: "image",
      data: { src: "https://example.com/pic.jpg" },
    });
    render(<A2UIContainer components={[comp]} />);
    const img = screen.getByRole("presentation");
    expect(img).toHaveAttribute("alt", "");
  });
});

describe("A2UIContainer — alert type", () => {
  it("renders alert with title and message", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { title: "Heads up!", message: "Something happened", level: "info" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Heads up!")).toBeInTheDocument();
    expect(screen.getByText("Something happened")).toBeInTheDocument();
  });

  it("renders alert with default title when title is missing", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { message: "Default alert" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Alert")).toBeInTheDocument();
    expect(screen.getByText("Default alert")).toBeInTheDocument();
  });

  it("applies correct color for success alert level", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { title: "Success!", level: "success" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const titleEl = screen.getByText("Success!");
    // success color is #34d399 (jsdom returns rgb)
    expect(titleEl.style.color).toBe("rgb(52, 211, 153)");
  });

  it("applies correct color for warning alert level", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { title: "Warning!", level: "warning" },
    });
    render(<A2UIContainer components={[comp]} />);
    const titleEl = screen.getByText("Warning!");
    expect(titleEl.style.color).toBe("rgb(251, 191, 36)");
  });

  it("applies correct color for error alert level", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { title: "Error!", level: "error" },
    });
    render(<A2UIContainer components={[comp]} />);
    const titleEl = screen.getByText("Error!");
    expect(titleEl.style.color).toBe("rgb(248, 113, 113)");
  });

  it("defaults to info color when level is not specified", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { title: "No Level" },
    });
    render(<A2UIContainer components={[comp]} />);
    const titleEl = screen.getByText("No Level");
    expect(titleEl.style.color).toBe("rgb(96, 165, 250)");
  });

  it("does not render message paragraph when message is missing", () => {
    const comp = makeComponent({
      component_type: "alert",
      data: { title: "Title Only" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    // Only one <p> (the title), no message paragraph
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs.length).toBe(1);
  });
});

describe("A2UIContainer — steps type", () => {
  it("renders steps with title and step labels", () => {
    const comp = makeComponent({
      component_type: "steps",
      data: {
        title: "Onboarding",
        steps: [
          { label: "Sign up", status: "done" },
          { label: "Verify email", status: "active" },
          { label: "Complete profile" },
        ],
      },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Sign up")).toBeInTheDocument();
    expect(screen.getByText("Verify email")).toBeInTheDocument();
    expect(screen.getByText("Complete profile")).toBeInTheDocument();
  });

  it("renders checkmark for done steps and numbers for others", () => {
    const comp = makeComponent({
      component_type: "steps",
      data: {
        steps: [
          { label: "Step A", status: "done" },
          { label: "Step B", status: "active" },
          { label: "Step C" },
        ],
      },
    });
    render(<A2UIContainer components={[comp]} />);
    // done step shows checkmark
    expect(screen.getByText("\u2713")).toBeInTheDocument();
    // active step shows number 2
    expect(screen.getByText("2")).toBeInTheDocument();
    // pending step shows number 3
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders steps without title when title is missing", () => {
    const comp = makeComponent({
      component_type: "steps",
      data: {
        steps: [{ label: "Only Step" }],
      },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Only Step")).toBeInTheDocument();
    // No title paragraph (the p with font-semibold mb-4)
    const titleP = container.querySelector("p.mb-4");
    expect(titleP).not.toBeInTheDocument();
  });

  it("renders empty steps list when steps data is missing", () => {
    const comp = makeComponent({
      component_type: "steps",
      data: {},
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const ol = container.querySelector("ol");
    expect(ol).toBeInTheDocument();
    expect(ol!.children.length).toBe(0);
  });
});

describe("A2UIContainer — unknown/default type", () => {
  it("renders unknown component type with fallback message", () => {
    const comp = makeComponent({
      component_type: "widget" as any,
      data: { foo: "bar" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("Unknown component type: widget")).toBeInTheDocument();
    expect(screen.getByText(/"foo"/)).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════════════════
   3. Props passing and data handling
   ═══════════════════════════════════════════════════════ */

describe("A2UIContainer — props and data handling", () => {
  it("passes metadata to card sub-component", () => {
    const comp = makeComponent({
      component_type: "card",
      data: { title: "Meta Card" },
      metadata: { version: "2.0" },
    });
    render(<A2UIContainer components={[comp]} />);
    expect(screen.getByText("2.0")).toBeInTheDocument();
  });

  it("passes onFormSubmit callback to form sub-component", () => {
    const onSubmit = vi.fn();
    const comp = makeComponent({
      component_type: "form",
      component_id: "form-1",
      data: {
        title: "Test Form",
        fields: [{ name: "name", label: "Name" }],
        submit_label: "Send",
      },
    });
    render(<A2UIContainer components={[comp]} onFormSubmit={onSubmit} />);
    expect(screen.getByText("Send")).toBeInTheDocument();
  });

  it("handles empty data prop gracefully for card", () => {
    const comp = makeComponent({
      component_type: "card",
      data: {},
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    // Should render without crashing
    expect(container.firstChild).toBeInTheDocument();
  });

  it("handles empty data prop gracefully for table", () => {
    const comp = makeComponent({
      component_type: "table",
      data: {},
    });
    render(<A2UIContainer components={[comp]} />);
    // A2UITable renders "No table data provided." for empty data
    expect(screen.getByText("No table data provided.")).toBeInTheDocument();
  });

  it("accepts components as a Map", () => {
    const comp = makeComponent({
      component_id: "card-map-1",
      component_type: "card",
      data: { title: "Map Card" },
    });
    const map = new Map<string, A2UIComponent>();
    map.set(comp.component_id, comp);
    render(<A2UIContainer components={map} />);
    expect(screen.getByText("Map Card")).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════════════════
   4. Progress rendering
   ═══════════════════════════════════════════════════════ */

describe("A2UIContainer — progress bars", () => {
  it("renders progress bars from progress Map", () => {
    const progressMap = new Map<string, A2UIProgressMessage>();
    progressMap.set("t1", {
      task_id: "t1",
      progress_type: "determinate",
      value: 50,
      total: 100,
      message: "Uploading files",
    });
    render(<A2UIContainer components={[]} progress={progressMap} />);
    expect(screen.getByText("Uploading files")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("renders progress alongside components", () => {
    const progressMap = new Map<string, A2UIProgressMessage>();
    progressMap.set("t2", {
      task_id: "t2",
      progress_type: "indeterminate",
      message: "Loading data",
    });
    const comp = makeComponent({
      component_type: "card",
      data: { title: "Data Card" },
    });
    render(<A2UIContainer components={[comp]} progress={progressMap} />);
    expect(screen.getByText("Loading data")).toBeInTheDocument();
    expect(screen.getByText("Data Card")).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════════════════
   5. Multiple components rendering
   ═══════════════════════════════════════════════════════ */

describe("A2UIContainer — multiple components", () => {
  it("renders multiple components of different types", () => {
    const components: A2UIComponent[] = [
      makeComponent({ component_type: "card", data: { title: "Card One" } }),
      makeComponent({
        component_type: "table",
        data: { headers: ["Col"], rows: [["Row1"]] },
      }),
      makeComponent({ component_type: "alert", data: { title: "Alert One" } }),
      makeComponent({ component_type: "markdown", data: { content: "Some markdown" } }),
    ];
    render(<A2UIContainer components={components} />);
    expect(screen.getByText("Card One")).toBeInTheDocument();
    expect(screen.getByText("Col")).toBeInTheDocument();
    expect(screen.getByText("Alert One")).toBeInTheDocument();
    expect(screen.getByText("Some markdown")).toBeInTheDocument();
  });

  it("renders correct number of child wrapper divs", () => {
    const components: A2UIComponent[] = [
      makeComponent({ component_type: "card", data: { title: "A" } }),
      makeComponent({ component_type: "card", data: { title: "B" } }),
      makeComponent({ component_type: "card", data: { title: "C" } }),
    ];
    const { container } = render(<A2UIContainer components={components} />);
    // The outer flex div contains one div per component
    const outerDiv = container.firstChild as HTMLElement;
    // Count direct child divs that wrap each component (excluding progress)
    const wrapperDivs = outerDiv.querySelectorAll(":scope > div");
    expect(wrapperDivs.length).toBe(3);
  });
});

/* ═══════════════════════════════════════════════════════
   6. Structure verification
   ═══════════════════════════════════════════════════════ */

describe("A2UIContainer — structure verification", () => {
  it("wraps all content in a flex column container", () => {
    const comp = makeComponent({
      component_type: "card",
      data: { title: "Structure" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const outer = container.firstChild as HTMLElement;
    expect(outer.className).toContain("flex");
    expect(outer.className).toContain("flex-col");
    expect(outer.className).toContain("gap-4");
  });

  it("each component is wrapped in a div with component_id as key", () => {
    const comp = makeComponent({
      component_id: "unique-id-123",
      component_type: "markdown",
      data: { content: "Test" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    // The wrapper div exists around the markdown content
    const outerDiv = container.firstChild as HTMLElement;
    const wrapperDiv = outerDiv.querySelector(":scope > div") as HTMLElement;
    expect(wrapperDiv).toBeInTheDocument();
  });

  it("chart renders a pre element with JSON-stringified data", () => {
    const comp = makeComponent({
      component_type: "chart",
      data: { x: [1, 2], y: [3, 4] },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const pre = container.querySelector("pre");
    expect(pre).toBeInTheDocument();
    const parsed = JSON.parse(pre!.textContent!);
    expect(parsed.x).toEqual([1, 2]);
    expect(parsed.y).toEqual([3, 4]);
  });

  it("image renders an img element", () => {
    const comp = makeComponent({
      component_type: "image",
      data: { src: "https://example.com/img.png" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img!.getAttribute("src")).toBe("https://example.com/img.png");
  });

  it("code renders a pre > code structure", () => {
    const comp = makeComponent({
      component_type: "code",
      data: { source: "let x = 1;" },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const pre = container.querySelector("pre");
    expect(pre).toBeInTheDocument();
    const code = pre!.querySelector("code");
    expect(code).toBeInTheDocument();
    expect(code!.textContent).toBe("let x = 1;");
  });

  it("steps renders an ordered list", () => {
    const comp = makeComponent({
      component_type: "steps",
      data: { steps: [{ label: "First" }] },
    });
    const { container } = render(<A2UIContainer components={[comp]} />);
    const ol = container.querySelector("ol");
    expect(ol).toBeInTheDocument();
    expect(ol!.children.length).toBe(1);
  });
});
