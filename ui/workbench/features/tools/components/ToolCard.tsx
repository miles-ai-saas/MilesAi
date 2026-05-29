"use client";

/** 工具目录卡片（链路 §3 + §4，props.toolsMeta）。 */
import { CardActions, type CardActionItem } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { formatToolUpdatedAt, toolKindLabel, toolSourceLabel } from "@/features/tools/lib/tool-labels";
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
  const updated = formatToolUpdatedAt(tool);

  const actions: CardActionItem[] = [
    { label: "查看详情", onClick: onDetail, variant: "primary" },
    { label: "试调用", onClick: onTest },
  ];
  if (!readonly && onEdit) {
    actions.push({ label: "编辑", onClick: onEdit });
  }
  if (!readonly && onDelete) {
    actions.push({ label: "删除", onClick: onDelete, variant: "danger" });
  }

  return (
    <ResourceItemCard
      title={tool.name}
      description={tool.description || "—"}
      badge={toolSourceLabel(tool.source, toolsMeta)}
      meta={
        <>
          <p className="text-[10px] text-ink-faint">{tool.slug}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {tool.source === "custom" && tool.tool_type && (
              <span className="rounded border border-line bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted">
                {toolKindLabel(tool.tool_type, toolsMeta)}
              </span>
            )}
            {tool.version && <span className="rounded border border-line bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted">v{tool.version}</span>}
            {tool.require_confirmation && <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] text-amber-800">需确认</span>}
          </div>
          {updated ? <p className="mt-2">更新于 {updated}</p> : null}
        </>
      }
      actions={<CardActions actions={actions} />}
    />
  );
}
