import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Skeleton, {
  SkeletonCard,
  SkeletonTable,
  SkeletonStatCard,
  SkeletonChart,
} from "../Skeleton";

describe("Skeleton", () => {
  it("renders a skeleton element", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild;
    expect(el).toBeInTheDocument();
    expect(el?.tagName).toBe("DIV");
  });

  it("applies rounded-lg base class", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild;
    expect(el?.className).toContain("rounded-lg");
  });

  it("applies custom className", () => {
    const { container } = render(<Skeleton className="h-4 w-2/3" />);
    const el = container.firstElementChild;
    expect(el?.className).toContain("h-4");
    expect(el?.className).toContain("w-2/3");
  });

  it("applies shimmer animation via inline style", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.style.animation).toContain("skeleton-shimmer");
    expect(el.style.background).toContain("linear-gradient");
    expect(el.style.backgroundSize).toBe("200% 100%");
  });

  it("renders with empty className by default", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild;
    // Should only have the base rounded-lg plus a space from template literal
    expect(el?.className).toContain("rounded-lg");
  });

  it("renders multiple skeletons independently", () => {
    const { container } = render(
      <div>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-3 w-1/4" />
      </div>
    );
    const skeletons = container.querySelectorAll(".rounded-lg");
    expect(skeletons).toHaveLength(3);
  });
});

describe("SkeletonCard", () => {
  it("renders multiple skeleton lines inside a card", () => {
    const { container } = render(<SkeletonCard />);
    const skeletons = container.querySelectorAll(".rounded-lg");
    // SkeletonCard contains 4 Skeleton components (h-4, h-3, h-8, plus 2 in flex = 5 total)
    expect(skeletons.length).toBeGreaterThanOrEqual(4);
  });

  it("has dark card background styling", () => {
    const { container } = render(<SkeletonCard />);
    const card = container.firstElementChild;
    expect(card?.getAttribute("style")).toContain("background");
  });
});

describe("SkeletonTable", () => {
  it("renders default 5 rows", () => {
    const { container } = render(<SkeletonTable />);
    // Each row has 4 skeletons, plus 1 header skeleton
    const skeletons = container.querySelectorAll(".rounded-lg");
    // header (1) + 5 rows * 4 skeletons = 21
    expect(skeletons.length).toBe(21);
  });

  it("renders custom number of rows", () => {
    const { container } = render(<SkeletonTable rows={3} />);
    const skeletons = container.querySelectorAll(".rounded-lg");
    // header (1) + 3 rows * 4 skeletons = 13
    expect(skeletons.length).toBe(13);
  });
});

describe("SkeletonStatCard", () => {
  it("renders skeleton elements inside a stat card", () => {
    const { container } = render(<SkeletonStatCard />);
    const skeletons = container.querySelectorAll(".rounded-lg");
    expect(skeletons.length).toBeGreaterThanOrEqual(2);
  });
});

describe("SkeletonChart", () => {
  it("renders skeleton elements for chart placeholder", () => {
    const { container } = render(<SkeletonChart />);
    const skeletons = container.querySelectorAll(".rounded-lg");
    expect(skeletons.length).toBeGreaterThanOrEqual(2);
  });
});
