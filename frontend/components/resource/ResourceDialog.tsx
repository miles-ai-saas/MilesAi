"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  /** md: 居中小窗；lg: 居中宽窗；fullscreen: 铺满视口 */
  size?: "md" | "lg" | "fullscreen";
};

export function ResourceDialog({
  open,
  title,
  onClose,
  children,
  footer,
  size = "md",
}: Props) {
  useEffect(() => {
    if (!open || size !== "fullscreen") return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open, size]);

  if (!open) return null;

  if (size === "fullscreen") {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-surface">
        <header className="flex shrink-0 items-center justify-between border-b border-line px-6 py-4">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          <button type="button" onClick={onClose} className="btn-ghost text-ink-faint">
            ✕
          </button>
        </header>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
            <div className="mx-auto w-full max-w-5xl">{children}</div>
          </div>
          {footer && (
            <footer className="shrink-0 border-t border-line bg-surface px-6 py-4">
              <div className="mx-auto w-full max-w-5xl">{footer}</div>
            </footer>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-ink/30"
        aria-label="关闭"
        onClick={onClose}
      />
      <div
        role="dialog"
        className={`relative z-10 flex max-h-[90vh] w-full flex-col rounded-xl border border-line bg-surface p-5 shadow-panel ${
          size === "lg" ? "max-w-3xl" : "max-w-lg"
        }`}
      >
        <div className="mb-4 flex shrink-0 items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          <button type="button" onClick={onClose} className="btn-ghost text-ink-faint">
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">{children}</div>
        {footer && <div className="mt-5 shrink-0">{footer}</div>}
      </div>
    </div>
  );
}
