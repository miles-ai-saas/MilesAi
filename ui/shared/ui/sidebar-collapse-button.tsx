"use client";

type Props = {
  side: "left" | "right";
  collapsed: boolean;
  onToggle: () => void;
  hidden?: boolean;
};

/** 侧栏边缘折叠 / 展开按钮（租户端、运营后台共用）。 */
export function SidebarCollapseButton({ side, collapsed, onToggle, hidden }: Props) {
  if (hidden) return null;

  const label = collapsed ? "展开侧栏" : "收起侧栏";
  const chevron =
    side === "left"
      ? collapsed
        ? "M9 6l6 6-6 6"
        : "M15 6l-6 6 6 6"
      : collapsed
        ? "M15 6l-6 6 6 6"
        : "M9 6l6 6-6 6";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      className={`absolute top-1/2 z-50 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-surface text-ink-muted shadow-sm transition hover:border-brand/30 hover:text-brand ${
        side === "left" ? "-right-3.5" : "-left-3.5"
      }`}
    >
      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d={chevron} />
      </svg>
    </button>
  );
}
