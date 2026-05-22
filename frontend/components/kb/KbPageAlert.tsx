type Props = {
  tone: "success" | "error" | "info";
  message: string;
  onDismiss?: () => void;
};

const TONE_CLASS = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  error: "border-red-200 bg-red-50 text-red-900",
  info: "border-sky-200 bg-sky-50 text-sky-900",
};

export function KbPageAlert({ tone, message, onDismiss }: Props) {
  if (!message) return null;
  return (
    <div
      className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm ${TONE_CLASS[tone]}`}
      role="alert"
    >
      <span className="min-w-0 flex-1">{message}</span>
      {onDismiss && (
        <button
          type="button"
          className="shrink-0 text-xs opacity-70 hover:opacity-100"
          onClick={onDismiss}
          aria-label="关闭提示"
        >
          关闭
        </button>
      )}
    </div>
  );
}
