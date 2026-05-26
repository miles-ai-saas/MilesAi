"use client";

/** 工具目录卡片（链路 §3 + §4，props.toolsMeta）。 */
import { CardOverflowMenu, type OverflowMenuItem } from "@/components/resource/CardOverflowMenu";
import { formatToolUpdatedAt, toolKindLabel, toolSourceLabel } from "@/lib/tool-labels";
import type { ToolCatalogItem, ToolsMeta } from "@/lib/types";

type Props = {
  tool: ToolCatalogItem;
  /** `GET /tools/meta`，供 tool-labels 解析来源/类型文案 */
  toolsMeta?: ToolsMeta | null;
  onDetail: () => void;
  onTest: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
};

export function ToolCard({ tool, toolsMeta, onDetail, onTest, onEdit, onDelete }: Props) {
  const readonly = tool.source !== "custom";

  const menuItems: OverflowMenuItem[] = [
    { label: "查看详情", onClick: onDetail },
    { label: "试调用", onClick: onTest },
  ];
  if (!readonly && onEdit) {
    menuItems.push({ label: "编辑", onClick: onEdit });
  }
  if (!readonly && onDelete) {
    menuItems.push({ label: "删除", onClick: onDelete, variant: "danger" });
  }

  return (
    <article
      className="resource-card relative !min-h-[176px] cursor-pointer transition hover:border-brand/30"
      role="button"
      tabIndex={0}
      onClick={onDetail}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onDetail();
        }
      }}
    >
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-light text-lg">
          🔧
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="font-medium text-ink line-clamp-1">{tool.name}</h3>
              <p className="text-[10px] text-ink-faint">{tool.slug}</p>
            </div>
            <CardOverflowMenu items={menuItems} label={`${tool.name} 更多操作`} />
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-muted">
            {tool.description || "—"}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-[10px] font-medium text-brand">
          {toolSourceLabel(tool.source, toolsMeta)}
        </span>
        {tool.source === "custom" && tool.tool_type && (
          <span className="rounded border border-line bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted">
            {toolKindLabel(tool.tool_type, toolsMeta)}
          </span>
        )}
        {tool.version && (
          <span className="rounded border border-line bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted">
            v{tool.version}
          </span>
        )}
        {tool.require_confirmation && (
          <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] text-amber-800">
            需确认
          </span>
        )}
      </div>

      <p className="mt-auto pt-3 text-xs text-ink-faint">
        {formatToolUpdatedAt(tool) ? `更新于 ${formatToolUpdatedAt(tool)}` : ""}
      </p>
    </article>
  );
}
