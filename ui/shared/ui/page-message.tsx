"use client";

type Props = {
  message: string;
  onDismiss?: () => void;
  className?: string;
};

/** 列表页顶部提示条（成功/信息，可关闭） */
export function PageMessage({ message, onDismiss, className = "" }: Props) {
  return (
    <div
      className={`col-span-full flex items-start justify-between gap-3 rounded-xl border border-line bg-brand-light/40 px-4 py-3 text-sm text-ink ${className}`.trim()}
    >
      <p className="min-w-0 flex-1">{message}</p>
      {onDismiss ? (
        <button type="button" className="shrink-0 text-xs text-ink-muted hover:text-ink" onClick={onDismiss}>
          关闭
        </button>
      ) : null}
    </div>
  );
}
