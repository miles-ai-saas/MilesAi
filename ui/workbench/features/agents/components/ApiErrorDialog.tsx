"use client";

import { useEffect } from "react";

type Props = {
  open: boolean;
  title?: string;
  message: string;
  onClose: () => void;
};

/** API 错误弹窗：网络异常、后端不可用等提示，替代 window.alert 与内联错误文本。 */
export function ApiErrorDialog({ open, title = "请求失败", message, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4" role="dialog" aria-modal="true" onClick={onClose}>
      <div
        className="relative z-10 w-full max-w-md rounded-xl border border-line bg-surface shadow-panel"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 顶部红色提示条 */}
        <div className="flex items-center gap-3 rounded-t-xl border-b border-red-200 bg-red-50 px-5 py-3.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-red-800">{title}</p>
            <p className="mt-0.5 text-xs text-red-600/80">请检查后端服务状态或网络连接后重试</p>
          </div>
        </div>

        {/* 错误详情 */}
        <div className="px-5 py-4">
          <p className="text-sm leading-relaxed text-ink-muted">{message}</p>
        </div>

        {/* 底部操作 */}
        <div className="flex items-center justify-end gap-2 rounded-b-xl border-t border-line bg-surface-muted px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-foreground transition-colors hover:bg-brand-dark"
          >
            我知道了
          </button>
        </div>
      </div>
    </div>
  );
}
