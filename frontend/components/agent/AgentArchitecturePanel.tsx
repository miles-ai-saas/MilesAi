"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FlowCanvasPreview } from "@/components/flow/FlowCanvasPreview";
import { api } from "@/lib/api";
import type { AgentArchitecture, AgentArchitectureAttachments } from "@/lib/types";

type Props = {
  agentId: string;
};

function AttachmentChips({ attachments }: { attachments: AgentArchitectureAttachments }) {
  const items: { key: string; label: string }[] = [];
  if (attachments.model) {
    items.push({ key: "model", label: `模型 · ${attachments.model.name}` });
  }
  for (const kb of attachments.kbs) {
    items.push({ key: `kb-${kb.id}`, label: `知识库 · ${kb.name}` });
  }
  for (const sub of attachments.sub_agents) {
    items.push({
      key: `sub-${sub.id}`,
      label: sub.role_hint ? `子智能体 · ${sub.name}（${sub.role_hint}）` : `子智能体 · ${sub.name}`,
    });
  }
  for (const peer of attachments.a2a_peers) {
    items.push({
      key: `peer-${peer.id}`,
      label: peer.enabled ? `A2A · ${peer.name}` : `A2A · ${peer.name}（已禁用）`,
    });
  }
  if (attachments.flow) {
    items.push({
      key: "flow",
      label: `流程 · ${attachments.flow.name} v${attachments.flow.version}`,
    });
  }

  if (!items.length) {
    return <p className="text-xs text-ink-faint">暂无挂载能力，可在「配置」中绑定。</p>;
  }

  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li
          key={item.key}
          className="rounded-lg border border-line bg-surface-subtle px-2.5 py-1 text-xs text-ink-muted"
        >
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function AgentArchitecturePanel({ agentId }: Props) {
  const router = useRouter();
  const [data, setData] = useState<AgentArchitecture | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const arch = await api.getAgentArchitecture(agentId);
      setData(arch);
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const openFlowCanvas = () => {
    const flowId = data?.attachments.flow?.id;
    if (flowId) router.push(`/workbench/flows/${flowId}/edit`);
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">
        加载架构…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-ink-muted">{error ?? "无法加载架构"}</p>
        <button type="button" className="btn-sm-outline" onClick={() => void load()}>
          重试
        </button>
      </div>
    );
  }

  const flowNodes = data.flow_graph?.nodes?.length ?? 0;
  const showFlowPreview = flowNodes > 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <section className="shrink-0 space-y-4 border-b border-line-soft px-6 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-ink-muted">当前执行路径</span>
          <span className="rounded-full bg-brand-light px-3 py-1 text-sm font-medium text-brand">
            {data.primary_path_label}
          </span>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-muted">路由决策</h3>
          <ol className="space-y-1.5">
            {data.decision_steps.map((step) => (
              <li
                key={step.id}
                className={`flex gap-2 rounded-lg border px-3 py-2 text-sm ${
                  step.active
                    ? "border-brand/30 bg-brand-light/40 text-ink"
                    : "border-line-soft bg-surface-subtle/50 text-ink-muted"
                }`}
              >
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                    step.active ? "bg-brand" : "bg-line"
                  }`}
                  aria-hidden
                />
                <div className="min-w-0">
                  <span className="font-medium">{step.label}</span>
                  {step.description && (
                    <p className="mt-0.5 text-xs text-ink-faint">{step.description}</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-muted">能力挂载</h3>
          <AttachmentChips attachments={data.attachments} />
        </div>
      </section>

      <section className="flex min-h-[320px] flex-1 flex-col">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-6 py-3">
          <div>
            <h3 className="text-sm font-medium text-ink">编排流程预览</h3>
            <p className="mt-0.5 text-xs text-ink-faint">
              {data.attachments.flow
                ? data.attachments.flow.is_runtime_path
                  ? "当前对话将走此画布"
                  : "已绑定但未作为当前主路径（被上游路由优先）"
                : "未绑定已发布流程"}
            </p>
          </div>
          {data.attachments.flow && (
            <button type="button" className="btn-sm-primary shrink-0" onClick={openFlowCanvas}>
              编辑画布
            </button>
          )}
        </div>

        <div className="relative min-h-0 flex-1 bg-surface-subtle/30">
          {showFlowPreview ? (
            <>
              {data.attachments.flow && !data.attachments.flow.is_runtime_path && (
                <p className="shrink-0 border-b border-line-soft bg-amber-50/80 px-6 py-2 text-xs text-amber-900">
                  流程已绑定，但当前对话主路径为「{data.primary_path_label}」，运行时不会走此画布。
                </p>
              )}
              <FlowCanvasPreview graph={data.flow_graph!} className="h-full min-h-[280px] w-full" />
            </>
          ) : (
            <div className="flex h-full min-h-[200px] items-center justify-center p-6 text-center text-sm text-ink-muted">
              {data.attachments.flow
                ? "流程暂无节点，请进入画布添加节点并发布。"
                : "在「配置 → 工具与能力」中绑定已发布的编排流程后，可在此预览。"}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
