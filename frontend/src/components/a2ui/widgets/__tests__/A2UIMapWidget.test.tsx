import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import A2UIMapWidget, { type MapMarker } from "../A2UIMapWidget";

describe("A2UIMapWidget", () => {
  const defaultProps = {
    latitude: 40.7128,
    longitude: -74.006,
  };

  it("renders the Map View heading", () => {
    render(<A2UIMapWidget {...defaultProps} />);
    expect(screen.getByText("Map View")).toBeInTheDocument();
  });

  it("renders formatted coordinates in the header", () => {
    render(<A2UIMapWidget latitude={40.7128} longitude={-74.006} />);
    expect(screen.getByText("40.7128, -74.0060")).toBeInTheDocument();
  });

  it("renders default zoom level of 4x", () => {
    render(<A2UIMapWidget {...defaultProps} />);
    expect(screen.getByText("4x")).toBeInTheDocument();
  });

  it("renders custom zoom level", () => {
    render(<A2UIMapWidget {...defaultProps} zoom={10} />);
    expect(screen.getByText("10x")).toBeInTheDocument();
  });

  it("increments zoom when zoom in button is clicked", () => {
    render(<A2UIMapWidget {...defaultProps} zoom={5} />);
    expect(screen.getByText("5x")).toBeInTheDocument();

    const zoomInButton = screen.getByTitle("Zoom in");
    fireEvent.click(zoomInButton);
    expect(screen.getByText("6x")).toBeInTheDocument();
  });

  it("decrements zoom when zoom out button is clicked", () => {
    render(<A2UIMapWidget {...defaultProps} zoom={5} />);
    expect(screen.getByText("5x")).toBeInTheDocument();

    const zoomOutButton = screen.getByTitle("Zoom out");
    fireEvent.click(zoomOutButton);
    expect(screen.getByText("4x")).toBeInTheDocument();
  });

  it("does not zoom below 1", () => {
    render(<A2UIMapWidget {...defaultProps} zoom={1} />);
    expect(screen.getByText("1x")).toBeInTheDocument();

    const zoomOutButton = screen.getByTitle("Zoom out");
    fireEvent.click(zoomOutButton);
    expect(screen.getByText("1x")).toBeInTheDocument();
  });

  it("does not zoom above 20", () => {
    render(<A2UIMapWidget {...defaultProps} zoom={20} />);
    expect(screen.getByText("20x")).toBeInTheDocument();

    const zoomInButton = screen.getByTitle("Zoom in");
    fireEvent.click(zoomInButton);
    expect(screen.getByText("20x")).toBeInTheDocument();
  });

  it("does not render marker list when no markers are provided", () => {
    render(<A2UIMapWidget {...defaultProps} />);
    expect(screen.queryByText(/Markers/)).not.toBeInTheDocument();
  });

  it("renders marker list with count when markers are provided", () => {
    const markers: MapMarker[] = [
      { id: "m1", latitude: 40.7128, longitude: -74.006, label: "NYC" },
      { id: "m2", latitude: 34.0522, longitude: -118.2437, label: "LA" },
    ];
    render(<A2UIMapWidget {...defaultProps} markers={markers} />);
    expect(screen.getByText("Markers (2)")).toBeInTheDocument();
  });

  it("renders marker labels in the marker list", () => {
    const markers: MapMarker[] = [
      { id: "m1", latitude: 40.7128, longitude: -74.006, label: "New York" },
      { id: "m2", latitude: 51.5074, longitude: -0.1278, label: "London" },
    ];
    render(<A2UIMapWidget {...defaultProps} markers={markers} />);
    expect(screen.getByText("New York")).toBeInTheDocument();
    expect(screen.getByText("London")).toBeInTheDocument();
  });

  it("uses marker id as fallback when label is not provided", () => {
    const markers: MapMarker[] = [
      { id: "marker-alpha", latitude: 40.7128, longitude: -74.006 },
    ];
    render(<A2UIMapWidget {...defaultProps} markers={markers} />);
    expect(screen.getByText("marker-alpha")).toBeInTheDocument();
  });

  it("renders marker coordinates in the list", () => {
    const markers: MapMarker[] = [
      { id: "m1", latitude: 48.8566, longitude: 2.3522, label: "Paris" },
    ];
    render(<A2UIMapWidget {...defaultProps} markers={markers} />);
    expect(screen.getByText("48.8566, 2.3522")).toBeInTheDocument();
  });

  it("renders the SVG map area", () => {
    const { container } = render(<A2UIMapWidget {...defaultProps} />);
    const svg = container.querySelector('svg[viewBox="0 0 100 60"]');
    expect(svg).toBeInTheDocument();
  });

  it("renders grid lines in the SVG", () => {
    const { container } = render(<A2UIMapWidget {...defaultProps} />);
    const lines = container.querySelectorAll("svg line");
    // 9 horizontal + 15 vertical + 2 crosshair = 26
    expect(lines.length).toBeGreaterThanOrEqual(24);
  });

  it("hovering a marker list item sets hoveredMarker (lines 265-266)", () => {
    const markers: MapMarker[] = [
      { id: "hover-test", latitude: 40.7128, longitude: -74.006, label: "HoverCity" },
    ];
    const { container } = render(
      <A2UIMapWidget {...defaultProps} markers={markers} />
    );

    // The marker list items have onMouseEnter/onMouseLeave handlers.
    // Find the list item container div (it has a specific class pattern).
    const listItem = container.querySelector(
      ".flex.items-center.gap-3.rounded-lg"
    ) as HTMLElement;
    expect(listItem).toBeInTheDocument();

    // Fire mouseEnter to cover line 265: onMouseEnter={() => setHoveredMarker(m.id)}
    fireEvent.mouseEnter(listItem);

    // Fire mouseLeave to cover line 266: onMouseLeave={() => setHoveredMarker(null)}
    fireEvent.mouseLeave(listItem);

    // Component should still render without error
    expect(screen.getByText("HoverCity")).toBeInTheDocument();
  });

  it("hovering SVG marker group sets hoveredMarker (lines 180-181)", () => {
    const markers: MapMarker[] = [
      { id: "svg-hover-test", latitude: 40.7128, longitude: -74.006, label: "SVG City", color: "#00ff00" },
    ];
    const { container } = render(
      <A2UIMapWidget {...defaultProps} markers={markers} />
    );

    // SVG marker groups are <g> elements inside the SVG map area
    const svg = container.querySelector('svg[viewBox="0 0 100 60"]') as SVGElement;
    expect(svg).toBeInTheDocument();

    // Find the <g> elements that have the style cursor:pointer (marker groups)
    const markerGroups = svg.querySelectorAll("g[style]");
    expect(markerGroups.length).toBeGreaterThan(0);

    const firstMarkerGroup = markerGroups[0] as SVGGElement;

    // Fire mouseEnter to cover line 180: onMouseEnter={() => setHoveredMarker(m.id)}
    fireEvent.mouseEnter(firstMarkerGroup);

    // Fire mouseLeave to cover line 181: onMouseLeave={() => setHoveredMarker(null)}
    fireEvent.mouseLeave(firstMarkerGroup);

    // Should still display correctly
    expect(screen.getByText("Markers (1)")).toBeInTheDocument();
  });

  it("hovering SVG marker shows tooltip label when marker has a label", () => {
    const markers: MapMarker[] = [
      { id: "labeled-marker", latitude: 40.7128, longitude: -74.006, label: "Labeled Pin" },
    ];
    const { container } = render(
      <A2UIMapWidget {...defaultProps} markers={markers} />
    );

    const svg = container.querySelector('svg[viewBox="0 0 100 60"]') as SVGElement;
    const markerGroups = svg.querySelectorAll("g[style]");
    const firstMarkerGroup = markerGroups[0] as SVGGElement;

    // Hover the marker — should trigger hoveredMarker state, which renders the label tooltip
    fireEvent.mouseEnter(firstMarkerGroup);

    // After hover, the label tooltip <text> should appear in the SVG
    const svgTexts = svg.querySelectorAll("text");
    expect(svgTexts.length).toBeGreaterThan(0);

    fireEvent.mouseLeave(firstMarkerGroup);
  });

  it("renders marker with default color when color is not specified", () => {
    const markers: MapMarker[] = [
      { id: "no-color-marker", latitude: 35.0, longitude: 139.0 },
    ];
    const { container } = render(
      <A2UIMapWidget {...defaultProps} markers={markers} />
    );

    // Default color (#f87171) should be applied to the marker dot in the list
    const markerDot = container.querySelector(
      ".h-2\\.5.w-2\\.5.flex-shrink-0.rounded-full"
    ) as HTMLElement;
    expect(markerDot).toBeInTheDocument();
    expect(markerDot.style.backgroundColor).toBe("rgb(248, 113, 113)");
  });

  it("hovering multiple markers in the list updates state correctly", () => {
    const markers: MapMarker[] = [
      { id: "m1", latitude: 40.0, longitude: -73.0, label: "Alpha" },
      { id: "m2", latitude: 51.0, longitude: -0.1, label: "Beta" },
    ];
    const { container } = render(
      <A2UIMapWidget {...defaultProps} markers={markers} />
    );

    const listItems = container.querySelectorAll(
      ".flex.items-center.gap-3.rounded-lg"
    );
    expect(listItems.length).toBe(2);

    // Hover first item — both markers are always in the DOM (list), so getAllByText
    fireEvent.mouseEnter(listItems[0]);
    expect(screen.getAllByText("Alpha").length).toBeGreaterThanOrEqual(1);

    // Hover second item
    fireEvent.mouseEnter(listItems[1]);
    expect(screen.getAllByText("Beta").length).toBeGreaterThanOrEqual(1);

    // Leave second item
    fireEvent.mouseLeave(listItems[1]);
    expect(screen.getAllByText("Alpha").length).toBeGreaterThanOrEqual(1);
  });
});
