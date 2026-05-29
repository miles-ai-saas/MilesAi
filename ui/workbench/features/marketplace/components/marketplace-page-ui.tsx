"use client";

import Link from "next/link";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import type { AppInstallResult } from "@/lib/types";

export { StatChip as MarketplaceStatChip };
export { PageMessage as MarketplacePageMessage };

export function MarketplaceStarDisplay({ value, count }: { value: number; count?: number }) {
  const full = Math.round(value);
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500" title={`${value.toFixed(1)} 分`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= full ? "" : "opacity-25"}>
          ★
        </span>
      ))}
      {count !== undefined && <span className="ml-1 text-xs text-ink-faint">({count})</span>}
    </span>
  );
}

export function MarketplaceInstallSuccessBanner({ result, onDismiss }: { result: AppInstallResult; onDismiss: () => void }) {
  return (
    <div className="col-span-full rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium">{result.message || "安装完成"}</p>
        <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={onDismiss}>
          关闭
        </button>
      </div>
      <ul className="mt-2 space-y-1 text-xs">
        {result.kb_id ? (
          <li>
            知识库 →{" "}
            <Link href={`/workbench/kb/${result.kb_id}`} className="underline">
              管理文档
            </Link>
          </li>
        ) : null}
        {result.flow_id ? (
          <li>
            流程 →{" "}
            <Link href={`/workbench/flows/${result.flow_id}/edit`} className="underline">
              编辑画布
            </Link>
          </li>
        ) : null}
        {result.agent_id ? (
          <li>
            智能体 →{" "}
            <Link href="/workbench/agents/chat" className="underline">
              去对话
            </Link>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
