"use client";

/** 工具详情（链路 §3 + tools meta）。 */
import { useEffect, useState, type ReactNode } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { formatToolUpdatedAt, toolKindLabel, toolSourceLabel } from "@/features/tools/lib/tool-labels";
import type { CustomTool, ToolCatalogItem, ToolParameterSpec, ToolsMeta } from "@/lib/types";

type Props = {
  open: boolean;
  item: ToolCatalogItem | null;
  toolsMeta?: ToolsMeta | null;
  onClose: () => void;
  onTest?: () => void;
  onEdit?: () => void;
};

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-3 sm:grid-cols-[7rem_1fr]">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-sm text-ink">{children}</dd>
    </div>
  );
}

function ParametersTable({ parameters }: { parameters: ToolParameterSpec[] }) {
  if (parameters.length === 0) {
    return <span className="text-ink-muted">无输入参数</span>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[28rem] text-left text-xs">
        <thead className="bg-surface-muted/60 text-ink-muted">
          <tr>
            <th className="px-3 py-2 font-medium">参数名</th>
            <th className="px-3 py-2 font-medium">类型</th>
            <th className="px-3 py-2 font-medium">必填</th>
            <th className="px-3 py-2 font-medium">说明</th>
          </tr>
        </thead>
        <tbody>
          {parameters.map((p) => (
            <tr key={p.name} className="border-t border-line-soft">
              <td className="px-3 py-2 font-mono text-ink">{p.name}</td>
              <td className="px-3 py-2 text-ink-muted">{p.type}</td>
              <td className="px-3 py-2 text-ink-muted">{p.required ? "是" : "否"}</td>
              <td className="px-3 py-2 text-ink-muted">{p.description || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfigSection({ detail }: { detail: CustomTool }) {
  const cfg = detail.config ?? {};
  if (detail.tool_type === "script") {
    const source = String(cfg.source ?? "");
    return (
      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">脚本配置</h3>
        <DetailRow label="语言">{String(cfg.language ?? "python")}</DetailRow>
        <DetailRow label="超时">{String(cfg.timeout_sec ?? 30)} 秒</DetailRow>
        <div>
          <p className="mb-2 text-xs font-medium text-ink-muted">脚本源码</p>
          <pre className="max-h-64 overflow-auto rounded-lg border border-line bg-surface-muted/40 p-3 font-mono text-xs leading-relaxed text-ink">
            {source || "—"}
          </pre>
        </div>
      </section>
    );
  }

  const headers = (cfg.headers as Record<string, string> | undefined) ?? {};
  return (
    <section className="space-y-0">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">HTTP 配置</h3>
      <DetailRow label="URL">
        <span className="break-all font-mono text-xs">{String(cfg.url ?? "—")}</span>
      </DetailRow>
      <DetailRow label="方法">{String(cfg.method ?? "POST")}</DetailRow>
      <DetailRow label="Body">{String(cfg.body_mode ?? "json")}</DetailRow>
      <DetailRow label="超时">{String(cfg.timeout_sec ?? 15)} 秒</DetailRow>
      <DetailRow label="Headers">
        {Object.keys(headers).length === 0 ? (
          <span className="text-ink-muted">无</span>
        ) : (
          <pre className="overflow-x-auto rounded-lg border border-line bg-surface-muted/40 p-2 font-mono text-xs">{JSON.stringify(headers, null, 2)}</pre>
        )}
      </DetailRow>
    </section>
  );
}

export function ToolDetailDialog({ open, item, toolsMeta, onClose, onTest, onEdit }: Props) {
  const [detail, setDetail] = useState<CustomTool | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !item) {
      setDetail(null);
      return;
    }
    if (item.source !== "custom" || !item.tool_id) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void api
      .getCustomTool(item.tool_id)
      .then((row) => {
        if (!cancelled) setDetail(row);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, item]);

  if (!item) return null;

  const parameters = (detail?.parameters ?? item.parameters ?? []) as ToolParameterSpec[];
  const readonly = item.source !== "custom";
  const updatedLabel = formatToolUpdatedAt(item);

  return (
    <ResourceDialog
      open={open}
      title={item.name}
      description={item.slug}
      size="lg"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
          {onTest && (
            <button type="button" className="btn-ghost border border-line" onClick={onTest}>
              试调用
            </button>
          )}
          {!readonly && onEdit && (
            <button type="button" className="btn-primary" onClick={onEdit}>
              编辑
            </button>
          )}
        </>
      }
    >
      <dl>
        <DetailRow label="来源">{toolSourceLabel(item.source, toolsMeta)}</DetailRow>
        {item.tool_type && <DetailRow label="类型">{toolKindLabel(item.tool_type, toolsMeta)}</DetailRow>}
        {item.version && <DetailRow label="版本">v{item.version}</DetailRow>}
        {(item.category_name || detail?.category_name) && <DetailRow label="分类">{item.category_name ?? detail?.category_name}</DetailRow>}
        <DetailRow label="需确认">{item.require_confirmation ? "是" : "否"}</DetailRow>
        {updatedLabel && <DetailRow label="更新时间">{updatedLabel}</DetailRow>}
        <DetailRow label="描述">
          {item.description ? <p className="whitespace-pre-wrap leading-relaxed">{item.description}</p> : <span className="text-ink-muted">—</span>}
        </DetailRow>
        {detail?.tags && detail.tags.length > 0 && (
          <DetailRow label="标签">
            <div className="flex flex-wrap gap-1.5">
              {detail.tags.map((t) => (
                <span key={t.id} className="rounded border border-line bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">
                  {t.name}
                </span>
              ))}
            </div>
          </DetailRow>
        )}
      </dl>

      <section className="mt-6">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">输入参数</h3>
        <ParametersTable parameters={parameters} />
      </section>

      {item.source === "custom" && (
        <section className="mt-6">
          {loading ? (
            <p className="text-sm text-ink-muted">加载配置…</p>
          ) : detail ? (
            <ConfigSection detail={detail} />
          ) : (
            <p className="text-sm text-ink-muted">未能加载工具配置</p>
          )}
        </section>
      )}
    </ResourceDialog>
  );
}
