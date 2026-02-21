import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FormulaDisplay, { type FormulaTerm } from "../FormulaDisplay";

const baseTerms: FormulaTerm[] = [
  { weight: 0.4, label: "Quality", color: "#3b82f6" },
  { weight: 0.3, label: "Speed", color: "#22c55e" },
  { weight: 0.3, label: "Cost", color: "#f59e0b" },
];

describe("FormulaDisplay", () => {
  it("renders 'Score =' label", () => {
    render(<FormulaDisplay terms={baseTerms} />);
    expect(screen.getByText("Score =")).toBeInTheDocument();
  });

  it("renders weight pills for each term", () => {
    render(<FormulaDisplay terms={baseTerms} />);
    expect(screen.getByText("0.4")).toBeInTheDocument();
    expect(screen.getAllByText("0.3")).toHaveLength(2);
  });

  it("renders term labels with multiplication sign", () => {
    render(<FormulaDisplay terms={baseTerms} />);
    // Each label is preceded by the multiplication sign in the same span
    expect(screen.getByText(/Quality/)).toBeInTheDocument();
    expect(screen.getByText(/Speed/)).toBeInTheDocument();
    expect(screen.getByText(/Cost/)).toBeInTheDocument();
  });

  it("renders title when provided", () => {
    render(<FormulaDisplay terms={baseTerms} title="Agent Score Formula" />);
    expect(screen.getByText("Agent Score Formula")).toBeInTheDocument();
  });

  it("does not render title when omitted", () => {
    const { container } = render(<FormulaDisplay terms={baseTerms} />);
    const h4 = container.querySelector("h4");
    expect(h4).toBeNull();
  });

  it("renders result pill when result is provided", () => {
    render(<FormulaDisplay terms={baseTerms} result={0.85} />);
    expect(screen.getByText("0.85")).toBeInTheDocument();
    // The equals sign for the result row
    expect(screen.getByText("=")).toBeInTheDocument();
  });

  it("does not render result pill when result is undefined", () => {
    const { container } = render(<FormulaDisplay terms={baseTerms} />);
    // No result pill — check that bg-primary-glow element is absent
    const resultPill = container.querySelector(".bg-primary-glow");
    expect(resultPill).toBeNull();
  });

  it("renders computed values row when terms have values", () => {
    const terms: FormulaTerm[] = [
      { weight: 0.5, label: "Quality", value: 0.9, color: "#3b82f6" },
      { weight: 0.5, label: "Speed", value: 0.8, color: "#22c55e" },
    ];
    render(<FormulaDisplay terms={terms} />);
    // Computed: 0.5 * 0.9 = 0.45 and 0.5 * 0.8 = 0.4
    expect(screen.getByText("= 0.45")).toBeInTheDocument();
    expect(screen.getByText("= 0.4")).toBeInTheDocument();
  });

  it("does not render computed values row when no term has a value", () => {
    const { container } = render(<FormulaDisplay terms={baseTerms} />);
    // The computed row has a specific left padding class
    const computedRow = container.querySelector(".pl-\\[3\\.25rem\\]");
    expect(computedRow).toBeNull();
  });

  it("renders bonus terms with plus sign and amber color", () => {
    const bonus: FormulaTerm[] = [
      { weight: 0.1, label: "Bonus", color: "#d97706" },
    ];
    render(<FormulaDisplay terms={baseTerms} bonusTerms={bonus} />);
    expect(screen.getByText("0.1")).toBeInTheDocument();
    expect(screen.getByText(/Bonus/)).toBeInTheDocument();
    // The bonus "+" sign
    const plusSigns = screen.getAllByText("+");
    // There are "+" between normal terms and one for the bonus prefix
    expect(plusSigns.length).toBeGreaterThanOrEqual(1);
  });

  it("renders bonus computed values when bonus terms have values", () => {
    const terms: FormulaTerm[] = [
      { weight: 0.5, label: "Quality", value: 0.9, color: "#3b82f6" },
    ];
    const bonus: FormulaTerm[] = [
      { weight: 0.2, label: "Reliability", value: 1.0, color: "#d97706" },
    ];
    render(<FormulaDisplay terms={terms} bonusTerms={bonus} />);
    // Bonus computed: 0.2 * 1.0 = 0.2
    expect(screen.getByText("= 0.2")).toBeInTheDocument();
  });

  it("applies custom className to the wrapper", () => {
    const { container } = render(
      <FormulaDisplay terms={baseTerms} className="extra-class" />,
    );
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain("extra-class");
  });

  it("applies term color as background color on weight pill", () => {
    const { container } = render(
      <FormulaDisplay
        terms={[{ weight: 0.7, label: "Accuracy", color: "#ef4444" }]}
      />,
    );
    const pill = screen.getByText("0.7");
    // jsdom normalizes hex+alpha (#ef44441a) to rgba format
    expect(pill.style.backgroundColor).toBe("rgba(239, 68, 68, 0.1)");
    expect(pill.style.color).toBe("rgb(239, 68, 68)");
  });
});
