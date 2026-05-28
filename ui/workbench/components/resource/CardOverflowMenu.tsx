"use client";

/** 卡片「更多」菜单（链路 §3）。 */
import { useEffect, useRef, useState } from "react";

export type OverflowMenuItem = {
  label: string;
  onClick: () => void;
  variant?: "default" | "danger";
};

type Props = {
  items: OverflowMenuItem[];
  /** 无障碍：描述菜单用途 */
  label?: string;
  /** dots：小号文字 ···；icon：竖三点 SVG */
  trigger?: "dots" | "icon";
};

function MenuTriggerContent({ variant }: { variant: "dots" | "icon" }) {
  if (variant === "icon") {
    return (
      <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <circle cx="10" cy="4" r="1.5" />
        <circle cx="10" cy="10" r="1.5" />
        <circle cx="10" cy="16" r="1.5" />
      </svg>
    );
  }
  return (
    <span aria-hidden className="inline-block translate-y-px text-[10px] font-medium leading-none tracking-[0.12em] text-current">
      ···
    </span>
  );
}

export function CardOverflowMenu({ items, label = "更多操作", trigger = "dots" }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (items.length === 0) return null;

  const run = (item: OverflowMenuItem) => {
    setOpen(false);
    item.onClick();
  };

  const dangerItems = items.filter((i) => i.variant === "danger");
  const normalItems = items.filter((i) => i.variant !== "danger");

  return (
    <div className="relative shrink-0" ref={rootRef}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={`flex items-center justify-center rounded-md border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30 ${
          trigger === "dots" ? "h-6 min-w-[1.5rem] px-1" : "h-7 w-7"
        } ${
          open
            ? "border-line/80 bg-surface-muted text-ink-muted shadow-sm"
            : "border-transparent text-ink-faint/90 hover:border-line/60 hover:bg-surface-muted/80 hover:text-ink-muted"
        }`}
      >
        <MenuTriggerContent variant={trigger} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 z-20 mt-1.5 min-w-[9.5rem] overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-panel">
          {normalItems.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className="flex w-full items-center px-3 py-2 text-left text-sm text-ink transition-colors hover:bg-surface-muted"
              onClick={(e) => {
                e.stopPropagation();
                run(item);
              }}
            >
              {item.label}
            </button>
          ))}
          {dangerItems.length > 0 && normalItems.length > 0 && <div className="my-1 border-t border-line-soft" role="separator" />}
          {dangerItems.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className="flex w-full items-center px-3 py-2 text-left text-sm text-red-600 transition-colors hover:bg-red-50"
              onClick={(e) => {
                e.stopPropagation();
                run(item);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
