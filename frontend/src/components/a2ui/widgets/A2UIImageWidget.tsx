import { useState, useCallback, useRef, useEffect } from "react";
import { X, ImageOff, Maximize2 } from "lucide-react";

/**
 * A2UI Image Widget.
 *
 * Renders an image with lazy loading, optional caption, error state handling,
 * and a full-screen lightbox overlay on click.
 */

interface A2UIImageWidgetProps {
  src: string;
  alt?: string;
  caption?: string;
  width?: number;
  height?: number;
}

export default function A2UIImageWidget({
  src,
  alt = "",
  caption,
  width,
  height,
}: A2UIImageWidgetProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);
  const lightboxRef = useRef<HTMLDivElement>(null);

  const handleLoad = useCallback(() => {
    setIsLoaded(true);
    setHasError(false);
  }, []);

  const handleError = useCallback(() => {
    setIsLoaded(true);
    setHasError(true);
  }, []);

  const openLightbox = useCallback(() => {
    if (!hasError) {
      setIsLightboxOpen(true);
    }
  }, [hasError]);

  const closeLightbox = useCallback(() => {
    setIsLightboxOpen(false);
  }, []);

  // Close lightbox on Escape key
  useEffect(() => {
    if (!isLightboxOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeLightbox();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    // Prevent body scroll when lightbox is open
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isLightboxOpen, closeLightbox]);

  // Close lightbox on outside click
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === lightboxRef.current) {
        closeLightbox();
      }
    },
    [closeLightbox],
  );

  return (
    <>
      <div className="group rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden transition-shadow hover:shadow-lg hover:shadow-[rgba(96,165,250,0.04)]">
        {/* Image container */}
        <div
          className="relative cursor-pointer overflow-hidden"
          onClick={openLightbox}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              openLightbox();
            }
          }}
          aria-label={`View ${alt || "image"} in fullscreen`}
        >
          {/* Loading skeleton */}
          {!isLoaded && !hasError && (
            <div
              className="flex items-center justify-center bg-[#0d1220] animate-pulse"
              style={{
                width: width ? `${width}px` : "100%",
                height: height ? `${height}px` : "200px",
              }}
            >
              <div className="flex flex-col items-center gap-2">
                <div className="h-8 w-8 rounded-full border-2 border-[#1e293b] border-t-[#60a5fa] animate-spin" />
                <span className="text-[10px] text-[#64748b]">Loading...</span>
              </div>
            </div>
          )}

          {/* Error state */}
          {hasError && (
            <div
              className="flex flex-col items-center justify-center gap-3 bg-[#0d1220]"
              style={{
                width: width ? `${width}px` : "100%",
                height: height ? `${height}px` : "200px",
              }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(248,113,113,0.1)]">
                <ImageOff className="h-6 w-6 text-[#f87171]" />
              </div>
              <div className="text-center">
                <p className="text-xs font-medium text-[#f87171]">
                  Failed to load image
                </p>
                <p className="mt-0.5 text-[10px] text-[#64748b] max-w-[200px] truncate">
                  {src}
                </p>
              </div>
            </div>
          )}

          {/* Actual image */}
          <img
            src={src}
            alt={alt}
            loading="lazy"
            onLoad={handleLoad}
            onError={handleError}
            className={`w-full object-cover transition-all duration-300 ${
              isLoaded && !hasError
                ? "opacity-100"
                : "absolute inset-0 opacity-0"
            } group-hover:scale-[1.02]`}
            style={{
              maxWidth: width ? `${width}px` : undefined,
              maxHeight: height ? `${height}px` : undefined,
            }}
          />

          {/* Hover overlay */}
          {isLoaded && !hasError && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all duration-300 group-hover:bg-black/30 group-hover:opacity-100">
              <div className="flex items-center gap-2 rounded-lg bg-[#0d1220]/80 px-3 py-2 backdrop-blur-sm">
                <Maximize2 className="h-3.5 w-3.5 text-[#e2e8f0]" />
                <span className="text-xs font-medium text-[#e2e8f0]">
                  View fullscreen
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Caption + metadata */}
        {(caption || alt) && (
          <div className="px-5 py-3">
            {caption && (
              <p className="text-sm text-[#94a3b8] leading-relaxed">
                {caption}
              </p>
            )}
            {alt && !caption && (
              <p className="text-xs text-[#64748b] italic">{alt}</p>
            )}
            {width && height && (
              <p className="mt-1 text-[10px] font-mono text-[#475569]">
                {width} x {height}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Lightbox overlay */}
      {isLightboxOpen && (
        <div
          ref={lightboxRef}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
          onClick={handleBackdropClick}
          style={{ animation: "lightbox-fade-in 0.2s ease-out" }}
        >
          {/* Close button */}
          <button
            onClick={closeLightbox}
            className="absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-[rgba(255,255,255,0.1)] text-white transition-colors hover:bg-[rgba(255,255,255,0.2)]"
            title="Close (Esc)"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Fullscreen image */}
          <img
            src={src}
            alt={alt}
            className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain"
            style={{ animation: "lightbox-scale-in 0.25s ease-out" }}
          />

          {/* Caption at bottom */}
          {caption && (
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-lg bg-[#141928]/90 px-4 py-2 backdrop-blur-sm">
              <p className="text-sm text-[#e2e8f0]">{caption}</p>
            </div>
          )}
        </div>
      )}

      {/* Lightbox animations */}
      <style>{`
        @keyframes lightbox-fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes lightbox-scale-in {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </>
  );
}
