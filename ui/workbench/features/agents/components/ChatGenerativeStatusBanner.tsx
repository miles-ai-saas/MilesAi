"use client";

/** 生图/生视频等异步任务进度（贴在消息区末尾，不占输入框高度）。 */

type Props = {
  message: string;
  progressPercent?: number | null;
  canCancel?: boolean;
  onCancel?: () => void;
};

export function ChatGenerativeStatusBanner({ message, progressPercent, canCancel, onCancel }: Props) {
  return (
    <div className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-xs text-amber-900">
      <div className="flex items-center justify-between gap-2">
        <span>{message}</span>
        {canCancel && onCancel ? (
          <button type="button" className="btn-sm-ghost shrink-0 text-xs text-amber-900" onClick={onCancel}>
            取消
          </button>
        ) : null}
      </div>
      {progressPercent != null ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-200/60">
          <div className="h-full rounded-full bg-amber-600 transition-all duration-300" style={{ width: `${progressPercent}%` }} />
        </div>
      ) : null}
    </div>
  );
}
