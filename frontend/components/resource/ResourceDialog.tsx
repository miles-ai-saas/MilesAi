"use client";

/** 创建/编辑弹窗壳（链路 §3）：档位见 design.md §5.7；业务表单作为 children 传入。 */

import { useEffect } from "react";
import type { ReactNode } from "react";

type PanelSize = "md" | "lg" | "sheet" | "fullscreen";

type Props = {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  /** md: 居中小窗；lg: 居中宽窗；sheet: 顶栏下铺满；fullscreen: 铺满视口（慎用，会盖住 App Header） */
  size?: PanelSize;
  /** sheet / fullscreen 内容区最大宽度，默认 max-w-5xl */
  contentMaxWidth?: string;
};

function PanelChrome({
  title,
  description,
  onClose,
  children,
  footer,
  contentMaxWidth = "max-w-5xl",
}: {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  contentMaxWidth?: string;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-6 py-4">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
        </div>
        <button type="button" onClick={onClose} className="btn-ghost shrink-0 text-ink-faint" aria-label="关闭">
          ✕
        </button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          <div className={`mx-auto w-full ${contentMaxWidth}`}>{children}</div>
        </div>
        {footer && (
          <footer className="shrink-0 border-t border-line bg-surface px-6 py-4">
            <div className={`mx-auto flex w-full flex-wrap items-center justify-end gap-2 ${contentMaxWidth}`}>
              {footer}
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}

function useDialogEffects(open: boolean, size: PanelSize, onClose: () => void) {
  useEffect(() => {
    if (!open || (size !== "fullscreen" && size !== "sheet")) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open, size]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
}

export function ResourceDialog({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  size = "md",
  contentMaxWidth = "max-w-5xl",
}: Props) {
  useDialogEffects(open, size, onClose);

  if (!open) return null;

  if (size === "sheet") {
    return (
      <div
        role="dialog"
        aria-modal="true"
        className="fixed inset-x-0 bottom-0 top-14 z-40 flex flex-col border-t border-line bg-surface shadow-panel"
      >
        <PanelChrome
          title={title}
          description={description}
          onClose={onClose}
          footer={footer}
          contentMaxWidth={contentMaxWidth}
        >
          {children}
        </PanelChrome>
      </div>
    );
  }

  if (size === "fullscreen") {
    return (
      <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex flex-col bg-surface">
        <PanelChrome
          title={title}
          onClose={onClose}
          footer={footer}
          contentMaxWidth={contentMaxWidth}
        >
          {children}
        </PanelChrome>
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
        aria-modal="true"
        className={`relative z-10 flex max-h-[90vh] w-full flex-col rounded-xl border border-line bg-surface p-5 shadow-panel ${
          size === "lg" ? "max-w-3xl" : "max-w-lg"
        }`}
      >
        <div className="mb-4 flex shrink-0 items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">{title}</h2>
            {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
          </div>
          <button type="button" onClick={onClose} className="btn-ghost shrink-0 text-ink-faint" aria-label="关闭">
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">{children}</div>
        {footer && <div className="mt-5 flex shrink-0 flex-wrap items-center justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}
