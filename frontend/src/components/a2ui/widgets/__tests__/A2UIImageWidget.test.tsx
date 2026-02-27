import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import A2UIImageWidget from "../A2UIImageWidget";

describe("A2UIImageWidget", () => {
  it("renders the image with the correct src", () => {
    render(<A2UIImageWidget src="https://example.com/photo.jpg" alt="Test photo" />);
    const img = screen.getByRole("img", { name: "Test photo" });
    expect(img).toHaveAttribute("src", "https://example.com/photo.jpg");
  });

  it("renders the image with alt text", () => {
    render(<A2UIImageWidget src="https://example.com/photo.jpg" alt="A sunset" />);
    expect(screen.getByAltText("A sunset")).toBeInTheDocument();
  });

  it("uses empty string as default alt text", () => {
    const { container } = render(<A2UIImageWidget src="https://example.com/photo.jpg" />);
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("alt", "");
  });

  it("renders caption when provided", () => {
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        caption="A beautiful sunset"
      />
    );
    expect(screen.getByText("A beautiful sunset")).toBeInTheDocument();
  });

  it("renders alt text as fallback when caption is not provided", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Sunset view" />
    );
    expect(screen.getByText("Sunset view")).toBeInTheDocument();
  });

  it("prefers caption over alt text in the text display area", () => {
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Alt text"
        caption="Caption text"
      />
    );
    expect(screen.getByText("Caption text")).toBeInTheDocument();
    // Alt text should only appear on the <img>, not as standalone text
    const altParagraphs = screen.queryAllByText("Alt text");
    // There is the img alt but not a visible <p> with "Alt text"
    const visibleAltP = altParagraphs.filter(
      (el) => el.tagName === "P" && el.classList.contains("italic")
    );
    expect(visibleAltP).toHaveLength(0);
  });

  it("renders dimensions when both width and height are provided", () => {
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Photo"
        width={800}
        height={600}
      />
    );
    expect(screen.getByText("800 x 600")).toBeInTheDocument();
  });

  it("does not render dimensions when only width is provided", () => {
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Photo"
        width={800}
      />
    );
    expect(screen.queryByText(/800 x/)).not.toBeInTheDocument();
  });

  it("shows loading skeleton before image loads", () => {
    const { container } = render(
      <A2UIImageWidget src="https://example.com/photo.jpg" />
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("shows error state when image fails to load", () => {
    const { container } = render(<A2UIImageWidget src="https://example.com/broken.jpg" />);
    const img = container.querySelector("img")!;
    fireEvent.error(img);
    expect(screen.getByText("Failed to load image")).toBeInTheDocument();
    expect(screen.getByText("https://example.com/broken.jpg")).toBeInTheDocument();
  });

  it("hides loading skeleton after image loads", () => {
    const { container } = render(<A2UIImageWidget src="https://example.com/photo.jpg" />);
    const img = container.querySelector("img")!;
    fireEvent.load(img);
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("opens lightbox when clicking on the image container", () => {
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Lightbox test"
      />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view lightbox test in fullscreen/i,
    });
    fireEvent.click(imageButton);

    // Lightbox should now be open - close button should be present
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();
  });

  it("does not open lightbox when image has an error", () => {
    render(<A2UIImageWidget src="https://example.com/broken.jpg" alt="Broken" />);
    const img = screen.getByRole("img");
    fireEvent.error(img);

    const imageButton = screen.getByRole("button", {
      name: /view broken in fullscreen/i,
    });
    fireEvent.click(imageButton);

    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
  });

  it("closes lightbox when close button is clicked", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Close test" />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view close test in fullscreen/i,
    });
    fireEvent.click(imageButton);
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();

    fireEvent.click(screen.getByTitle("Close (Esc)"));
    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
  });

  it("closes lightbox on Escape key press", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Esc test" />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view esc test in fullscreen/i,
    });
    fireEvent.click(imageButton);
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
  });

  it("renders caption in lightbox overlay when lightbox is open", () => {
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Caption lightbox"
        caption="Lightbox caption"
      />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view caption lightbox in fullscreen/i,
    });
    fireEvent.click(imageButton);

    // Caption appears both in main view and in lightbox overlay
    const captions = screen.getAllByText("Lightbox caption");
    expect(captions.length).toBeGreaterThanOrEqual(2);
  });

  it("sets aria-label for keyboard accessibility", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Accessible image" />
    );
    const imageButton = screen.getByRole("button", {
      name: "View Accessible image in fullscreen",
    });
    expect(imageButton).toBeInTheDocument();
  });

  it("opens lightbox via Enter key press (line 75: onKeyDown Enter branch)", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Key test" />
    );
    const img = screen.getByRole("img");
    // Load the image first so openLightbox works (hasError must be false)
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view key test in fullscreen/i,
    });
    // Cover line 91-93: onKeyDown handler with Enter key
    fireEvent.keyDown(imageButton, { key: "Enter" });
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();
  });

  it("opens lightbox via Space key press (line 91-93: onKeyDown Space branch)", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Space test" />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view space test in fullscreen/i,
    });
    // Cover the ' ' (space) branch
    fireEvent.keyDown(imageButton, { key: " " });
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();
  });

  it("does not open lightbox on non-Enter/Space keydown (line 91: else branch is skipped)", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Tab test" />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    const imageButton = screen.getByRole("button", {
      name: /view tab test in fullscreen/i,
    });
    fireEvent.keyDown(imageButton, { key: "Tab" });
    // Lightbox should NOT open
    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
  });

  it("does not render dimensions when only height is provided (line 91-93: width && height requires both)", () => {
    // Line 91: {width && height && <p>...} — only height provided means width is falsy
    render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Photo"
        height={400}
      />
    );
    // No dimension text should appear since width is not provided
    expect(screen.queryByText(/x 400/)).not.toBeInTheDocument();
  });

  it("closes lightbox when backdrop div itself is clicked (line 74-75: e.target === lightboxRef.current true branch)", () => {
    const { container } = render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Backdrop test" />
    );
    const img = container.querySelector("img")!;
    fireEvent.load(img);

    // Open the lightbox
    const imageButton = screen.getByRole("button", {
      name: /view backdrop test in fullscreen/i,
    });
    fireEvent.click(imageButton);
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();

    // Click on the backdrop div itself (the fixed overlay) — its ref is lightboxRef
    // When e.target === lightboxRef.current, closeLightbox() is called.
    const backdrop = container.querySelector(".fixed.inset-0")!;
    fireEvent.click(backdrop);

    // Lightbox should be closed
    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
  });

  it("does not close lightbox when clicking inside the lightbox content (line 74-75: false branch)", () => {
    const { container } = render(
      <A2UIImageWidget
        src="https://example.com/photo.jpg"
        alt="Inner click test"
        caption="Test caption"
      />
    );
    const img = container.querySelector("img")!;
    fireEvent.load(img);

    // Open the lightbox
    const imageButton = screen.getByRole("button", {
      name: /view inner click test in fullscreen/i,
    });
    fireEvent.click(imageButton);
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();

    // Click on the fullscreen image inside the lightbox (not the backdrop).
    // e.target !== lightboxRef.current → closeLightbox() is NOT called.
    const lightboxImgs = container.querySelectorAll(".fixed img");
    if (lightboxImgs.length > 0) {
      fireEvent.click(lightboxImgs[0]);
    }

    // Lightbox should remain open
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();
  });

  it("Escape key does not close lightbox when lightbox is already closed (useEffect early return branch)", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Esc closed test" />
    );
    // Lightbox is not open — pressing Escape should be a no-op
    // (useEffect `if (!isLightboxOpen) return;` early exit)
    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTitle("Close (Esc)")).not.toBeInTheDocument();
  });

  it("non-Escape key press while lightbox open does not close it (line 56 false branch)", () => {
    render(
      <A2UIImageWidget src="https://example.com/photo.jpg" alt="Non-escape test" />
    );
    const img = screen.getByRole("img");
    fireEvent.load(img);

    // Open the lightbox
    const imageButton = screen.getByRole("button", {
      name: /view non-escape test in fullscreen/i,
    });
    fireEvent.click(imageButton);
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();

    // Press a non-Escape key — the handleKeyDown `if (e.key === "Escape")` branch is false
    // so closeLightbox() is NOT called
    fireEvent.keyDown(document, { key: "ArrowLeft" });
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Enter" });
    expect(screen.getByTitle("Close (Esc)")).toBeInTheDocument();
  });

  it("error state renders with explicit width and height (lines 119-120 true branches)", () => {
    // When hasError=true and width+height are both provided, the error div uses
    // `${width}px` and `${height}px` instead of "100%" / "200px"
    const { container } = render(
      <A2UIImageWidget
        src="https://example.com/broken.jpg"
        alt="Sized error"
        width={640}
        height={480}
      />
    );
    const img = container.querySelector("img")!;
    fireEvent.error(img);

    // The error div should be in the DOM
    expect(screen.getByText("Failed to load image")).toBeInTheDocument();

    // The error container div uses explicit width and height
    const errorContainer = container.querySelector<HTMLElement>(
      ".flex.flex-col.items-center.justify-center.gap-3"
    );
    expect(errorContainer).not.toBeNull();
    expect(errorContainer?.style.width).toBe("640px");
    expect(errorContainer?.style.height).toBe("480px");
  });
});
