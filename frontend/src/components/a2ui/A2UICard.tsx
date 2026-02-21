/**
 * A2UI Card widget.
 *
 * Renders a card with optional title, subtitle, image, body content,
 * and action buttons based on the data supplied by the agent.
 */
interface A2UICardProps {
  data: Record<string, any>;
  metadata?: Record<string, any>;
}

export default function A2UICard({ data, metadata }: A2UICardProps) {
  const {
    title,
    subtitle,
    content,
    image,
    image_alt,
    actions,
  } = data as {
    title?: string;
    subtitle?: string;
    content?: string;
    image?: string;
    image_alt?: string;
    actions?: Array<{ label: string; url?: string; variant?: string }>;
  };

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden transition-shadow hover:shadow-lg hover:shadow-[rgba(96,165,250,0.04)]">
      {/* Optional image */}
      {image && (
        <div className="w-full overflow-hidden">
          <img
            src={image}
            alt={image_alt ?? title ?? ""}
            className="h-48 w-full object-cover"
          />
        </div>
      )}

      <div className="p-6">
        {/* Header */}
        {title && (
          <h3 className="text-base font-semibold text-[#e2e8f0]">{title}</h3>
        )}
        {subtitle && (
          <p className="mt-1 text-xs text-[#64748b]">{subtitle}</p>
        )}

        {/* Body content */}
        {content && (
          <p className="mt-3 text-sm leading-relaxed text-[#94a3b8]">
            {content}
          </p>
        )}

        {/* Metadata badges */}
        {metadata && Object.keys(metadata).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(metadata).map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center gap-1 rounded-full bg-[#1e293b] px-2.5 py-0.5 text-[10px] font-medium text-[#94a3b8]"
              >
                <span className="text-[#64748b]">{key}:</span> {String(value)}
              </span>
            ))}
          </div>
        )}

        {/* Action buttons */}
        {actions && actions.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2">
            {actions.map((action, idx) => {
              const isPrimary = action.variant === "primary" || idx === 0;
              return (
                <button
                  key={idx}
                  onClick={() => {
                    if (action.url) {
                      window.open(action.url, "_blank", "noopener,noreferrer");
                    }
                  }}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                    isPrimary
                      ? "bg-[#60a5fa] text-[#0a0e1a] hover:bg-[#3b82f6]"
                      : "border border-[rgba(255,255,255,0.1)] text-[#94a3b8] hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
                  }`}
                >
                  {action.label}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
