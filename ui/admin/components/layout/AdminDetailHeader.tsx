import Link from "next/link";
import type { ReactNode } from "react";

type Props = {
  backHref: string;
  backLabel: string;
  title: string;
  description?: ReactNode;
  badges?: ReactNode;
  action?: ReactNode;
};

export function AdminDetailHeader({
  backHref,
  backLabel,
  title,
  description,
  badges,
  action,
}: Props) {
  return (
    <header className="mb-6">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-sm text-ink-muted transition hover:text-brand"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        {backLabel}
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
            {badges}
          </div>
          {description ? (
            <div className="mt-1.5 text-sm cell-muted">{description}</div>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </header>
  );
}
