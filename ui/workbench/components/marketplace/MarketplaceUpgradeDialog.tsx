"use client";

/** 应用升级 diff 预览：确认后再执行升级。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { AppUpgradePreview } from "@/lib/types";

const RESOURCE_LABELS: Record<string, string> = {
  knowledge_base: "知识库",
  flow: "流程",
  agent: "智能体",
};

type Props = {
  open: boolean;
  loading: boolean;
  preview: AppUpgradePreview | null;
  upgrading: boolean;
  onClose: () => void;
  onConfirm: () => void;
  /** upgrade（默认）或 rollback，仅影响文案 */
  mode?: "upgrade" | "rollback";
};

function DiffValue({ value, changed }: { value: string | null | undefined; changed: boolean }) {
  if (value == null || value === "") {
    return <span className="text-ink-faint">—</span>;
  }
  return (
    <span className={changed ? "text-amber-700 dark:text-amber-300" : "text-ink-muted"}>{value}</span>
  );
}

export function MarketplaceUpgradeDialog({
  open,
  loading,
  preview,
  upgrading,
  onClose,
  onConfirm,
  mode = "upgrade",
}: Props) {
  const isRollback = mode === "rollback";
  const title = preview
    ? isRollback
      ? `回滚 ${preview.app_name}`
      : `升级 ${preview.app_name}`
    : isRollback
      ? "应用回滚预览"
      : "应用升级预览";
  const description = preview
    ? `v${preview.installed_version} → v${preview.target_version}`
    : undefined;

  const canConfirm = preview?.can_upgrade && !loading && !upgrading;

  return (
    <ResourceDialog
      open={open}
      title={title}
      description={description}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={upgrading}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={onConfirm}
            disabled={!canConfirm}
          >
            {upgrading
              ? isRollback
                ? "回滚中…"
                : "升级中…"
              : isRollback
                ? "确认回滚"
                : "确认升级"}
          </button>
        </>
      }
    >
      {loading ? (
        <p className="text-sm text-ink-muted">正在加载变更对比…</p>
      ) : !preview ? (
        <p className="text-sm text-ink-muted">无法加载升级预览</p>
      ) : (
        <div className="space-y-4">
          {preview.message ? (
            <p className="rounded-lg border border-line bg-surface-muted/40 px-4 py-3 text-sm text-ink-muted">
              {preview.message}
            </p>
          ) : null}

          {!preview.can_upgrade ? (
            <p className="text-sm text-ink-muted">当前已是最新版本，无需升级。</p>
          ) : preview.resources.length === 0 ? (
            <p className="text-sm text-ink-muted">未发现可对比的资源。</p>
          ) : (
            preview.resources.map((resource) => (
              <section
                key={`${resource.resource_type}-${resource.resource_id ?? resource.resource_name}`}
                className="rounded-xl border border-line bg-surface-muted/20"
              >
                <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      {RESOURCE_LABELS[resource.resource_type] ?? resource.resource_type}
                    </p>
                    <p className="mt-0.5 text-sm font-medium text-ink">{resource.resource_name}</p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      resource.has_changes
                        ? "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
                        : "bg-surface-muted text-ink-muted"
                    }`}
                  >
                    {resource.has_changes ? "有变更" : "无变更"}
                  </span>
                </header>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] text-sm">
                    <thead>
                      <tr className="border-b border-line text-left text-xs text-ink-muted">
                        <th className="px-4 py-2 font-medium">字段</th>
                        <th className="px-4 py-2 font-medium">当前</th>
                        <th className="px-4 py-2 font-medium">升级后</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resource.changes.map((change) => (
                        <tr
                          key={change.field}
                          className={
                            change.changed ? "bg-amber-50/50 dark:bg-amber-950/20" : "border-b border-line/60"
                          }
                        >
                          <td className="px-4 py-2 align-top font-medium text-ink">{change.label}</td>
                          <td className="px-4 py-2 align-top whitespace-pre-wrap break-words">
                            <DiffValue value={change.before} changed={change.changed} />
                          </td>
                          <td className="px-4 py-2 align-top whitespace-pre-wrap break-words">
                            <DiffValue value={change.after} changed={change.changed} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))
          )}
        </div>
      )}
    </ResourceDialog>
  );
}
