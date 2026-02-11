import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

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
      setToasts((prev) => [...prev, { id, message, variant }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    },
    [],
  );

  const ICONS = { success: CheckCircle, error: AlertCircle, info: Info };
  const COLORS: Record<ToastVariant, string> = {
    success: "border-success/30 bg-success-glow text-success",
    error: "border-danger/30 bg-danger-glow text-danger",
    info: "border-[rgba(0,212,255,0.3)] bg-primary-glow text-primary",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => {
          const Icon = ICONS[t.variant];
          return (
            <div
              key={t.id}
              className={`flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg backdrop-blur-xl animate-in ${COLORS[t.variant]}`}
            >
              <Icon size={16} />
              <span className="text-sm">{t.message}</span>
              <button
                onClick={() =>
                  setToasts((p) => p.filter((x) => x.id !== t.id))
                }
              >
                <X
                  size={14}
                  className="opacity-50 transition-opacity hover:opacity-100"
                />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
