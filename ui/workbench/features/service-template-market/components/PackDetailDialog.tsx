"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { BizServiceLineTemplatePack } from "@/lib/types";

const PUBLISHER_LABELS: Record<string, string> = {
  platform: "平台官方",
  partner: "合作伙伴",
  tenant: "租户分享",
};

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface-muted/30 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

type Props = {
  open: boolean;
  pack: BizServiceLineTemplatePack | null;
  applying: boolean;
  canApply: boolean;
  onClose: () => void;
  onApply: () => void;
};

export function PackDetailDialog({ open, pack, applying, canApply, onClose, onApply }: Props) {
  if (!pack) return null;

  const ai = pack.ai_config ?? {};
  const tagLabels = pack.tag_labels?.length ? pack.tag_labels : pack.tags;
  const description = [
    pack.category_label,
    `适用于 ${pack.service_line_label}`,
    `${PUBLISHER_LABELS[pack.publisher_type] ?? pack.publisher_type} · ${pack.publisher_name}`,
    pack.install_count > 0 ? `${pack.install_count} 次应用` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <ResourceDialog
      open={open}
      size="lg"
      title={pack.name}
      description={description}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost text-sm" onClick={onClose}>
            关闭
          </button>
          {canApply && (
            <button type="button" className="btn-primary text-sm" disabled={applying} onClick={onApply}>
              {applying ? "应用中…" : "应用到我的租户"}
            </button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {pack.description && (
          <DetailSection title="简介">
            <p className="text-sm leading-relaxed text-ink-muted">{pack.description}</p>
          </DetailSection>
        )}

        {tagLabels.length > 0 && (
          <DetailSection title="客户类型">
            <div className="flex flex-wrap gap-2">
              {tagLabels.map((tag, i) => (
                <span key={`${pack.id}-tag-${i}`} className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-ink">
                  {tag}
                </span>
              ))}
            </div>
          </DetailSection>
        )}

        <DetailSection title="阶段流水线">
          <ol className="space-y-2">
            {pack.stages.map((stage, i) => (
              <li key={i} className="flex gap-3 text-sm text-ink">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand/10 text-xs font-medium text-brand">
                  {i + 1}
                </span>
                <span className="pt-0.5">{stage}</span>
              </li>
            ))}
          </ol>
        </DetailSection>

        {(ai.agent_tag || ai.chat_hint || (ai.quick_prompts?.length ?? 0) > 0) && (
          <DetailSection title="AI 推荐配置">
            <dl className="space-y-2 text-sm">
              {ai.agent_tag && (
                <div>
                  <dt className="text-xs text-ink-muted">智能体标签</dt>
                  <dd className="mt-0.5 text-ink">{ai.agent_tag}</dd>
                </div>
              )}
              {ai.chat_hint && (
                <div>
                  <dt className="text-xs text-ink-muted">对话提示</dt>
                  <dd className="mt-0.5 text-ink-muted">{ai.chat_hint}</dd>
                </div>
              )}
              {(ai.quick_prompts?.length ?? 0) > 0 && (
                <div>
                  <dt className="text-xs text-ink-muted">快捷提示</dt>
                  <dd className="mt-1 flex flex-wrap gap-1.5">
                    {ai.quick_prompts!.map((prompt, i) => (
                      <span key={i} className="rounded bg-surface px-2 py-0.5 text-xs text-ink-muted">
                        {prompt}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </DetailSection>
        )}

        {pack.is_featured && (
          <p className="text-xs text-amber-700">此模板为平台精选推荐。</p>
        )}
      </div>
    </ResourceDialog>
  );
}
