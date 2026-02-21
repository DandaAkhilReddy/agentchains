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
});
