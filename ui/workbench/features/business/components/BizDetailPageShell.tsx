"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";

type Props = {
  backHref: string;
  backLabel: string;
  loading: boolean;
  error?: string;
  notFoundLabel?: string;
  children: ReactNode;
};

export function BizDetailPageShell({
  backHref,
  backLabel,
  loading,
  error,
  notFoundLabel = "记录不存在",
  children,
}: Props) {
  if (loading) {
    return <BizListPageSkeleton statCount={2} />;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-8 text-center">
        <p className="text-sm text-red-700">{error}</p>
        <Link href={backHref} className="mt-3 inline-block text-sm text-brand hover:underline">
          {backLabel}
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full">
      <Link href={backHref} className="mb-4 inline-flex items-center gap-1 text-sm text-ink-muted transition hover:text-brand">
        <span aria-hidden>←</span>
        {backLabel}
      </Link>
      {children ?? (
        <p className="text-sm text-ink-muted">{notFoundLabel}</p>
      )}
    </div>
  );
}
