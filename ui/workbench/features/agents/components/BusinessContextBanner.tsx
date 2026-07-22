"use client";

import Link from "next/link";
import { clearBusinessContext, type BusinessContext } from "@/features/projects";

export function BusinessContextBanner({ ctx, onDismiss }: { ctx: BusinessContext; onDismiss: () => void }) {
  return (
    <div className="border-b border-brand/20 bg-brand-light/30 px-4 py-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 text-xs text-ink">
          <span className="font-medium text-brand">业务项目上下文</span>
          <span className="mx-2 text-ink-muted">·</span>
          <Link href={`/business/projects/detail?id=${ctx.projectId}`} className="text-brand hover:underline">
            {ctx.projectName}
          </Link>
          {ctx.workPackageName && (
            <span className="text-ink-muted"> / {ctx.workPackageName}</span>
          )}
          {!ctx.ragEnabled && (
            <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-red-600">涉密 · 勿引用外部 KB</span>
          )}
        </div>
        <button
          type="button"
          className="shrink-0 text-xs text-ink-muted hover:text-ink"
          onClick={() => {
            clearBusinessContext();
            onDismiss();
          }}
        >
          清除上下文
        </button>
      </div>
    </div>
  );
}
