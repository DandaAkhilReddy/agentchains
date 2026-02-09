import { useEffect, useRef } from "react";
import { useToastStore } from "../../store/toastStore";

const typeStyles: Record<string, string> = {
  success: "bg-green-600 text-white",
  error: "bg-red-600 text-white",
  warning: "bg-yellow-500 text-black",
  info: "bg-blue-600 text-white",
};

function ToastItem({
  id,
  type,
  message,
}: {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
}) {
  const removeToast = useToastStore((s) => s.removeToast);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Trigger slide-in animation
    requestAnimationFrame(() => {
      ref.current?.classList.remove("translate-x-full", "opacity-0");
      ref.current?.classList.add("translate-x-0", "opacity-100");
    });

    const timer = setTimeout(() => {
      removeToast(id);
    }, 5000);

    return () => clearTimeout(timer);
  }, [id, removeToast]);

  return (
    <div
      ref={ref}
      className={`${typeStyles[type]} translate-x-full opacity-0 transition-all duration-300 ease-out flex items-center justify-between gap-3 rounded-lg px-4 py-3 shadow-lg min-w-[300px] max-w-[400px]`}
    >
      <span className="text-sm font-medium">{message}</span>
      <button
        onClick={() => removeToast(id)}
        className="shrink-0 cursor-pointer rounded p-0.5 hover:bg-black/10 transition-colors"
        aria-label="Close"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          id={toast.id}
          type={toast.type}
          message={toast.message}
        />
      ))}
    </div>
  );
}
