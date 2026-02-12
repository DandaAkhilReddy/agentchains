import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
} from "react";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

type ToastVariant = "success" | "error" | "info";

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

  const ICONS = { success: CheckCircle, error: AlertCircle, info: Info };
  const COLORS: Record<ToastVariant, string> = {
    success: "border-success/30 bg-success-glow text-success",
    error: "border-danger/30 bg-danger-glow text-danger",
    info: "border-[rgba(59,130,246,0.15)] bg-primary-glow text-primary",
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
              colorClass={COLORS[t.variant]}
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
  colorClass,
  onDismiss,
}: {
  toast: Toast;
  icon: ReactNode;
  colorClass: string;
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
      className={`relative overflow-hidden flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg backdrop-blur-xl animate-slide-up ${colorClass}`}
    >
      {icon}
      <span className="text-sm">{toast.message}</span>
      <button onClick={onDismiss} className="ml-2">
        <X size={14} className="opacity-50 transition-opacity hover:opacity-100" />
      </button>
      <div
        className="absolute bottom-0 left-0 h-0.5 bg-current opacity-30 transition-all"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
