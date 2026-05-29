import type { ReactNode } from "react";
import type { ToolKindTab } from "@/lib/tool-labels";

export type ToolDialogMode = "create" | "edit";

export const DEFAULT_SCRIPT = `def run(params: dict) -> dict:
    """params 对应下方输入参数 schema"""
    # return {"result": params.get("query")}
    raise NotImplementedError("请实现 run(params)")`;

export type ToolCreateDialogKindTab = {
  key: ToolKindTab;
  label: string;
  hint: string;
  available: boolean;
};

export function ToolCreateDialogSection({
  title,
  hint,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface-muted/30 p-4 ${className}`}>
      <div className="mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
        {hint ? <p className="mt-1 text-xs leading-relaxed text-ink-faint">{hint}</p> : null}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
