import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ParamList from "../ParamList";
import type { EndpointParam } from "../../../pages/docs-sections";

const sampleParams: EndpointParam[] = [
  {
    name: "agent_id",
    type: "string",
    required: true,
    desc: "Unique identifier for the agent",
  },
  {
    name: "limit",
    type: "integer",
    required: false,
    desc: "Maximum number of results to return",
  },
  {
    name: "category",
    type: "string",
    required: false,
    desc: "Filter by category",
  },
];

describe("ParamList", () => {
  it("renders all parameter names", () => {
    render(<ParamList params={sampleParams} />);
    expect(screen.getByText("agent_id")).toBeInTheDocument();
    expect(screen.getByText("limit")).toBeInTheDocument();
    expect(screen.getByText("category")).toBeInTheDocument();
  });

  it("renders parameter types", () => {
    render(<ParamList params={sampleParams} />);
    // "string" appears twice (agent_id and category), so use getAllByText
    const stringTypes = screen.getAllByText("string");
    expect(stringTypes).toHaveLength(2);
    expect(screen.getByText("integer")).toBeInTheDocument();
  });

  it("renders parameter descriptions", () => {
    render(<ParamList params={sampleParams} />);
    expect(
      screen.getByText("Unique identifier for the agent"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Maximum number of results to return"),
    ).toBeInTheDocument();
    expect(screen.getByText("Filter by category")).toBeInTheDocument();
  });

  it("shows Required badge for required parameters", () => {
    render(<ParamList params={sampleParams} />);
    const requiredBadges = screen.getAllByText("Required");
    expect(requiredBadges).toHaveLength(1);
  });

  it("does not show Required badge for optional parameters", () => {
    const optionalOnly: EndpointParam[] = [
      {
        name: "offset",
        type: "integer",
        required: false,
        desc: "Pagination offset",
      },
    ];
    render(<ParamList params={optionalOnly} />);
    expect(screen.queryByText("Required")).not.toBeInTheDocument();
  });

  it("renders param names in code elements", () => {
    render(<ParamList params={sampleParams} />);
    const codeElements = screen.getAllByText(
      (_content, element) => element?.tagName === "CODE",
    );
    expect(codeElements.length).toBe(3);
  });

  it("renders an empty container when params array is empty", () => {
    const { container } = render(<ParamList params={[]} />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toBeTruthy();
    expect(wrapper?.children.length).toBe(0);
  });

  it("renders multiple required badges when multiple params are required", () => {
    const allRequired: EndpointParam[] = [
      { name: "id", type: "string", required: true, desc: "The ID" },
      { name: "name", type: "string", required: true, desc: "The name" },
      {
        name: "email",
        type: "string",
        required: true,
        desc: "The email address",
      },
    ];
    render(<ParamList params={allRequired} />);
    const requiredBadges = screen.getAllByText("Required");
    expect(requiredBadges).toHaveLength(3);
  });

  it("applies correct styling to the Required badge", () => {
    const requiredParam: EndpointParam[] = [
      { name: "token", type: "string", required: true, desc: "Auth token" },
    ];
    render(<ParamList params={requiredParam} />);
    const badge = screen.getByText("Required");
    expect(badge.className).toContain("text-[#f87171]");
    expect(badge.className).toContain("uppercase");
  });
});
