"use client";

/** 列表卡片容器（链路 §3 列表页通用）。 */

import Link from "next/link";
import type { KeyboardEvent, ReactNode } from "react";

type Props = {
  title: ReactNode;
  description?: string;
  meta?: ReactNode;
  href?: string;
  onClick?: () => void;
  actions?: ReactNode;
  badge?: string;
  muted?: boolean;
};

function CardMain({ title, description, meta, badge }: Pick<Props, "title" | "description" | "meta" | "badge">) {
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 font-medium text-ink line-clamp-1">{title}</div>
        {badge && <span className="shrink-0 rounded bg-brand-light px-2 py-0.5 text-[10px] text-brand">{badge}</span>}
      </div>
      {description && <p className="mt-2 flex-1 text-xs leading-relaxed text-ink-muted line-clamp-3">{description}</p>}
      {meta && <div className="mt-3 text-xs text-ink-faint">{meta}</div>}
    </>
  );
}

function CardActionsFooter({ actions }: { actions: ReactNode }) {
  return <div className="mt-4 flex flex-wrap gap-2 border-t border-line-soft pt-3">{actions}</div>;
}

export function ResourceItemCard({ title, description, meta, href, onClick, actions, badge, muted = false }: Props) {
  const className = muted ? "resource-card opacity-60 saturate-50" : "resource-card";

  const main = <CardMain title={title} description={description} meta={meta} badge={badge} />;

  if (href) {
    return (
      <Link href={href} className={className}>
        {main}
        {actions && <CardActionsFooter actions={actions} />}
      </Link>
    );
  }

  if (onClick) {
    const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onClick();
      }
    };

    return (
      <article className={className}>
        <button
          type="button"
          onClick={onClick}
          onKeyDown={onKeyDown}
          className="flex w-full min-h-0 flex-1 flex-col text-left outline-none transition hover:opacity-90 focus-visible:rounded-lg focus-visible:ring-2 focus-visible:ring-brand/30"
        >
          {main}
        </button>
        {actions && <CardActionsFooter actions={actions} />}
      </article>
    );
  }

  return (
    <article className={className}>
      {main}
      {actions && <CardActionsFooter actions={actions} />}
    </article>
  );
}
