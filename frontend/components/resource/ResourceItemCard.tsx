"use client";

import Link from "next/link";
import type { ReactNode } from "react";

type Props = {
  title: string;
  description?: string;
  meta?: ReactNode;
  href?: string;
  onClick?: () => void;
  actions?: ReactNode;
  badge?: string;
  muted?: boolean;
};

export function ResourceItemCard({
  title,
  description,
  meta,
  href,
  onClick,
  actions,
  badge,
  muted = false,
}: Props) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium text-ink line-clamp-1">{title}</h3>
        {badge && (
          <span className="shrink-0 rounded bg-brand-light px-2 py-0.5 text-[10px] text-brand">
            {badge}
          </span>
        )}
      </div>
      {description && (
        <p className="mt-2 flex-1 text-xs leading-relaxed text-ink-muted line-clamp-3">
          {description}
        </p>
      )}
      {meta && <div className="mt-3 text-xs text-ink-faint">{meta}</div>}
      {actions && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-line-soft pt-3">{actions}</div>
      )}
    </>
  );

  const className = muted
    ? "resource-card opacity-60 saturate-50"
    : "resource-card";

  if (href) {
    return (
      <Link href={href} className={className}>
        {body}
      </Link>
    );
  }

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={`${className} w-full`}>
        {body}
      </button>
    );
  }

  return <article className={className}>{body}</article>;
}
