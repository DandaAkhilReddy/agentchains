import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
} from "react";
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from "lucide-react";

type ToastVariant = "success" | "error" | "info" | "warning";

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
  createdAt: number;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const TOAST_DURATION = 4000;

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id = ++nextId.current;
      setToasts((prev) => [...prev, { id, message, variant, createdAt: Date.now() }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, TOAST_DURATION);
    },
    [],
  );

  const ICONS = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  };

  const BORDER_COLORS: Record<ToastVariant, string> = {
    success: "#34d399",
    error: "#f87171",
    warning: "#fbbf24",
    info: "#60a5fa",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => {
          const Icon = ICONS[t.variant];
          return (
            <ToastItem
              key={t.id}
              toast={t}
              icon={<Icon size={16} />}
              borderColor={BORDER_COLORS[t.variant]}
              onDismiss={() => setToasts((p) => p.filter((x) => x.id !== t.id))}
            />
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({
  toast,
  icon,
  borderColor,
  onDismiss,
}: {
  toast: Toast;
  icon: ReactNode;
  borderColor: string;
  onDismiss: () => void;
}) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = Date.now() - toast.createdAt;
      const remaining = Math.max(0, 100 - (elapsed / TOAST_DURATION) * 100);
      setProgress(remaining);
      if (remaining <= 0) clearInterval(interval);
    }, 50);
    return () => clearInterval(interval);
  }, [toast.createdAt]);

  return (
    <div
      className="relative overflow-hidden flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg backdrop-blur-xl animate-slide-in min-w-[300px]"
      style={{
        background: "rgba(20, 25, 40, 0.95)",
        borderLeft: `4px solid ${borderColor}`,
      }}
    >
      <span style={{ color: borderColor }} className="flex-shrink-0">
        {icon}
      </span>
      <span className="text-sm text-[#e2e8f0] flex-1">{toast.message}</span>
      <button onClick={onDismiss} className="ml-2 flex-shrink-0">
        <X
          size={14}
          className="text-[#64748b] transition-colors hover:text-[#e2e8f0]"
        />
      </button>
      {/* Progress bar at bottom */}
      <div
        className="absolute bottom-0 left-0 h-[2px] transition-all duration-100 ease-linear"
        style={{
          width: `${progress}%`,
          backgroundColor: borderColor,
          opacity: 0.6,
        }}
      />
    </div>
  );
}
