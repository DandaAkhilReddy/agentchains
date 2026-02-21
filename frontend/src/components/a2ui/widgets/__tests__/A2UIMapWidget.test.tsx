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
});
