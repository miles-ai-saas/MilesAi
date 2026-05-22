import {
  documentStatusLabel,
  documentStatusTone,
  type DocumentStatusTone,
} from "@/lib/document-status";

const TONE_CLASS: Record<DocumentStatusTone, string> = {
  success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  progress: "bg-sky-50 text-sky-800 ring-sky-200",
  error: "bg-red-50 text-red-800 ring-red-200",
  neutral: "bg-surface-muted text-ink-muted ring-line",
};

type Props = {
  status: string;
  pulse?: boolean;
};

export function DocumentStatusBadge({ status, pulse }: Props) {
  const tone = documentStatusTone(status);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASS[tone]} ${
        pulse && tone === "progress" ? "animate-pulse" : ""
      }`}
    >
      {tone === "progress" && (
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      )}
      {documentStatusLabel(status)}
    </span>
  );
}
