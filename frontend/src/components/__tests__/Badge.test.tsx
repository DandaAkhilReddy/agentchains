import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge, { categoryVariant, statusVariant, agentTypeVariant } from "../Badge";

describe("Badge", () => {
  it("renders label text", () => {
    render(<Badge label="Test Badge" />);
    expect(screen.getByText("Test Badge")).toBeInTheDocument();
  });

  it("applies default gray variant when no variant is specified", () => {
    const { container } = render(<Badge label="Default" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(100,116,139,0.15)]");
    expect(badge?.className).toContain("text-[#94a3b8]");
  });

  it("applies green variant styles", () => {
    const { container } = render(<Badge label="Green Badge" variant="green" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(16,185,129,0.15)]");
    expect(badge?.className).toContain("text-[#10b981]");
  });

  it("applies blue variant styles", () => {
    const { container } = render(<Badge label="Blue Badge" variant="blue" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(0,212,255,0.15)]");
    expect(badge?.className).toContain("text-[#00d4ff]");
  });

  it("applies purple variant styles", () => {
    const { container } = render(<Badge label="Purple Badge" variant="purple" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(139,92,246,0.15)]");
    expect(badge?.className).toContain("text-[#8b5cf6]");
  });

  it("applies red variant styles", () => {
    const { container } = render(<Badge label="Red Badge" variant="red" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(239,68,68,0.15)]");
    expect(badge?.className).toContain("text-[#ef4444]");
  });

  it("applies yellow variant styles", () => {
    const { container } = render(<Badge label="Yellow Badge" variant="yellow" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(234,179,8,0.15)]");
    expect(badge?.className).toContain("text-[#eab308]");
  });

  it("applies amber variant styles", () => {
    const { container } = render(<Badge label="Amber Badge" variant="amber" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(245,158,11,0.15)]");
    expect(badge?.className).toContain("text-[#f59e0b]");
  });

  it("applies orange variant styles", () => {
    const { container } = render(<Badge label="Orange Badge" variant="orange" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(249,115,22,0.15)]");
    expect(badge?.className).toContain("text-[#f97316]");
  });

  it("applies rose variant styles", () => {
    const { container } = render(<Badge label="Rose Badge" variant="rose" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(244,63,94,0.15)]");
    expect(badge?.className).toContain("text-[#f43f5e]");
  });

  it("applies cyan variant styles", () => {
    const { container } = render(<Badge label="Cyan Badge" variant="cyan" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(0,212,255,0.15)]");
    expect(badge?.className).toContain("text-[#00d4ff]");
  });

  it("falls back to gray variant for unknown variant", () => {
    const { container } = render(<Badge label="Unknown" variant={"unknown" as any} />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[rgba(100,116,139,0.15)]");
    expect(badge?.className).toContain("text-[#94a3b8]");
  });

  it("includes base badge styling classes", () => {
    const { container } = render(<Badge label="Styled" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("inline-flex");
    expect(badge?.className).toContain("items-center");
    expect(badge?.className).toContain("rounded-full");
    expect(badge?.className).toContain("px-2");
    expect(badge?.className).toContain("py-0.5");
    expect(badge?.className).toContain("text-[11px]");
    expect(badge?.className).toContain("font-medium");
  });
});

describe("categoryVariant helper", () => {
  it("returns blue for web_search category", () => {
    expect(categoryVariant("web_search")).toBe("blue");
  });

  it("returns purple for code_analysis category", () => {
    expect(categoryVariant("code_analysis")).toBe("purple");
  });

  it("returns amber for document_summary category", () => {
    expect(categoryVariant("document_summary")).toBe("amber");
  });

  it("returns cyan for api_response category", () => {
    expect(categoryVariant("api_response")).toBe("cyan");
  });

  it("returns rose for computation category", () => {
    expect(categoryVariant("computation")).toBe("rose");
  });

  it("returns gray for unknown category", () => {
    expect(categoryVariant("unknown")).toBe("gray");
  });
});

describe("statusVariant helper", () => {
  it("returns green for active status", () => {
    expect(statusVariant("active")).toBe("green");
  });

  it("returns green for completed status", () => {
    expect(statusVariant("completed")).toBe("green");
  });

  it("returns green for verified status", () => {
    expect(statusVariant("verified")).toBe("green");
  });

  it("returns cyan for delivered status", () => {
    expect(statusVariant("delivered")).toBe("cyan");
  });

  it("returns blue for payment_confirmed status", () => {
    expect(statusVariant("payment_confirmed")).toBe("blue");
  });

  it("returns gray for initiated status", () => {
    expect(statusVariant("initiated")).toBe("gray");
  });

  it("returns yellow for payment_pending status", () => {
    expect(statusVariant("payment_pending")).toBe("yellow");
  });

  it("returns red for failed status", () => {
    expect(statusVariant("failed")).toBe("red");
  });

  it("returns orange for disputed status", () => {
    expect(statusVariant("disputed")).toBe("orange");
  });

  it("returns gray for inactive status", () => {
    expect(statusVariant("inactive")).toBe("gray");
  });

  it("returns gray for delisted status", () => {
    expect(statusVariant("delisted")).toBe("gray");
  });

  it("returns gray for unknown status", () => {
    expect(statusVariant("unknown")).toBe("gray");
  });
});

describe("agentTypeVariant helper", () => {
  it("returns blue for seller type", () => {
    expect(agentTypeVariant("seller")).toBe("blue");
  });

  it("returns green for buyer type", () => {
    expect(agentTypeVariant("buyer")).toBe("green");
  });

  it("returns purple for both type", () => {
    expect(agentTypeVariant("both")).toBe("purple");
  });

  it("returns gray for unknown type", () => {
    expect(agentTypeVariant("unknown")).toBe("gray");
  });
});
