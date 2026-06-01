"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizProjectAiContext } from "@/lib/types";
import {
  buildAgentChatDeepLink,
  buildFlowsDeepLink,
  buildKbDeepLink,
} from "@/features/projects/lib/business-context";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectAiTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { project, projectId } = vm;
  const [ctx, setCtx] = useState<BizProjectAiContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api.getProjectAiContext(projectId)
      .then(setCtx)
      .catch((e) => setError(e?.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (!project) return null;
  if (loading) return <p className="mt-4 text-sm text-ink-muted">加载 AI 推荐…</p>;
  if (error || !ctx) return <p className="mt-4 text-sm text-red-600">{error || "无法加载 AI 上下文"}</p>;

  return (
    <div className="mt-4 space-y-6">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${ctx.rag_enabled ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
            {ctx.rag_enabled ? "可引用知识库与案例" : "涉密项目 · 禁止外部 RAG"}
          </span>
          <span className="text-xs text-ink-muted">客户：{ctx.client_name}</span>
        </div>
        <pre className="mt-3 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-surface-muted p-3 text-xs text-ink-muted">{ctx.context_text}</pre>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <QuickLinkCard href={buildAgentChatDeepLink({ projectId, bizContext: toStoredContext(ctx) })} icon="💬" label="AI 对话" desc="带项目上下文打开智能体" />
        <QuickLinkCard href={buildKbDeepLink()} icon="📚" label="知识库" desc="管理品牌手册与案例库" external />
        <QuickLinkCard href={buildFlowsDeepLink()} icon="🔄" label="工作流" desc="编排审批与创作流水线" external />
      </div>

      {(ctx.related_cases?.length ?? 0) > 0 && ctx.rag_enabled && (
        <section>
          <h2 className="text-sm font-semibold text-ink">相关案例（知识库）</h2>
          <p className="mt-1 text-xs text-ink-muted">同客户或同服务线已结项入库的参考材料</p>
          <div className="mt-3 space-y-2">
            {ctx.related_cases!.map((c) => (
              <div key={c.document_id} className="card flex flex-wrap items-center justify-between gap-2 p-3">
                <div>
                  <p className="text-sm font-medium text-ink">{c.document_title}</p>
                  <p className="text-xs text-ink-muted">
                    来自「{c.project_name}」· {c.kb_name}
                    {c.service_line ? ` · ${c.service_line}` : ""}
                  </p>
                </div>
                <Link href={buildKbDeepLink(c.kb_id)} className="text-xs text-brand hover:underline" target="_blank">
                  打开知识库
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

      {ctx.recommendations.length === 0 ? (
        <p className="text-sm text-ink-faint">暂无工作包，请先添加工作包以获取服务线 AI 推荐。</p>
      ) : (
        <section>
          <h2 className="text-sm font-semibold text-ink">按服务线推荐</h2>
          <div className="mt-3 space-y-3">
            {ctx.recommendations.map((rec) => (
              <div key={`${rec.work_package_id}-${rec.service_line}`} className="card p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-ink">{rec.work_package_name}</p>
                    <p className="text-xs text-ink-muted">
                      {rec.service_line_label}
                      {rec.stage ? ` · 阶段 ${rec.stage}` : ""}
                    </p>
                    {rec.recommended_agent_name && (
                      <p className="mt-1 text-xs text-brand">推荐智能体：{rec.recommended_agent_name}</p>
                    )}
                    {rec.flow_template_label && (
                      <p className="text-xs text-ink-faint">流程模板：{rec.flow_template_label}</p>
                    )}
                  </div>
                  <Link
                    href={buildAgentChatDeepLink({
                      agentId: rec.recommended_agent_id,
                      projectId,
                      workPackageId: rec.work_package_id,
                      bizContext: toStoredContext(ctx, rec),
                    })}
                    className="btn-primary text-xs"
                  >
                    打开对话
                  </Link>
                </div>
                {rec.chat_hint && <p className="mt-2 text-xs text-ink-muted">{rec.chat_hint}</p>}
                {rec.quick_prompts.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {rec.quick_prompts.map((p) => (
                      <Link
                        key={p}
                        href={buildAgentChatDeepLink({
                          agentId: rec.recommended_agent_id,
                          projectId,
                          workPackageId: rec.work_package_id,
                          prompt: p,
                          bizContext: toStoredContext(ctx, rec),
                        })}
                        className="rounded-full border border-line px-3 py-1 text-xs text-ink hover:border-brand hover:text-brand"
                      >
                        {p}
                      </Link>
                    ))}
                  </div>
                )}
                {rec.flow_template_id && (
                  <Link href={buildFlowsDeepLink(rec.flow_template_id)} className="mt-2 inline-block text-xs text-brand hover:underline" target="_blank">
                    从「{rec.flow_template_label}」创建流程 →
                  </Link>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {ctx.retrospective_available && ctx.retrospective_prompt && (
        <section className="card border-brand/20 bg-brand-light/10 p-4">
          <h2 className="text-sm font-semibold text-ink">结项 AI 复盘</h2>
          <p className="mt-1 text-xs text-ink-muted">基于已登记交付物生成复盘报告</p>
          <Link
            href={buildAgentChatDeepLink({
              projectId,
              prompt: ctx.retrospective_prompt,
              bizContext: toStoredContext(ctx),
            })}
            className="btn-primary mt-3 text-xs"
          >
            生成结项复盘
          </Link>
        </section>
      )}
    </div>
  );
}

function toStoredContext(
  ctx: BizProjectAiContext,
  rec?: BizProjectAiContext["recommendations"][number],
) {
  return {
    projectId: ctx.project_id,
    projectName: ctx.project_name,
    clientName: ctx.client_name,
    workPackageId: rec?.work_package_id,
    workPackageName: rec?.work_package_name,
    serviceLine: rec?.service_line,
    serviceLineLabel: rec?.service_line_label,
    contextText: ctx.context_text,
    chatHint: rec?.chat_hint,
    ragEnabled: ctx.rag_enabled,
  };
}

function QuickLinkCard({
  href,
  icon,
  label,
  desc,
  external,
}: {
  href: string;
  icon: string;
  label: string;
  desc: string;
  external?: boolean;
}) {
  return (
    <Link href={href} className="card flex items-center gap-3 p-4 transition hover:shadow-md" {...(external ? { target: "_blank" } : {})}>
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="font-medium text-ink">{label}</p>
        <p className="text-xs text-ink-muted">{desc}</p>
      </div>
    </Link>
  );
}
