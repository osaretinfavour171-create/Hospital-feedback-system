import { useEffect } from "react";
import { AlertTriangle, CheckCircle2, X, XCircle } from "lucide-react";

const STYLES = {
  success: {
    icon: CheckCircle2,
    tile: "bg-emerald-soft text-emerald",
    bar: "bg-emerald",
    text: "text-emerald",
  },
  alert: {
    icon: AlertTriangle,
    tile: "bg-rose-soft text-rose",
    bar: "bg-rose",
    text: "text-rose",
  },
  error: {
    icon: XCircle,
    tile: "bg-rose-soft text-rose",
    bar: "bg-rose",
    text: "text-rose",
  },
};

export default function Toast({ type = "success", title, message, onClose }) {
  const style = STYLES[type] || STYLES.success;
  const Icon = style.icon;

  useEffect(() => {
    const t = setTimeout(onClose, 3200);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className="fixed top-5 right-5 z-50 animate-toast-in">
      <div className="bg-white rounded-card shadow-float border border-line overflow-hidden w-[340px] max-w-[calc(100vw-40px)]">
        <div className="flex items-start gap-3 p-4">
          <span
            className={`w-10 h-10 rounded-lg2 grid place-items-center shrink-0 ${style.tile}`}
          >
            <Icon size={20} strokeWidth={2.2} />
          </span>
          <div className="flex-1 min-w-0 pt-0.5">
            <p className="text-sm font-semibold text-ink">{title}</p>
            {message && (
              <p className="text-xs text-ink-muted mt-0.5 leading-relaxed">{message}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-ink-faint hover:text-ink transition-colors shrink-0 mt-1"
            aria-label="Dismiss"
          >
            <X size={16} />
          </button>
        </div>
        <div className="relative h-[3px] bg-chip">
          <div
            className={`absolute inset-y-0 left-0 rounded-r-full ${style.bar} animate-progress-shrink`}
          />
        </div>
      </div>
    </div>
  );
}
