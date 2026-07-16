"use client";

/** 智能体架构：路由图 / 能力拓扑 / 流程画布（链路 §5）。 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentArchitectureRoutingGraph } from "@/features/agents/components/architecture/AgentArchitectureRoutingGraph";
import { AgentArchitectureTopologyGraph } from "@/features/agents/components/architecture/AgentArchitectureTopologyGraph";
import { FlowCanvasPreview } from "@/features/flows";
import { api } from "@/lib/api";
import type { AgentArchitecture } from "@/lib/types";

type Props = {
  agentId: string;
  agentName?: string;
};

type ArchViewTab = "routing" | "topology" | "flow";

const TABS: { id: ArchViewTab; label: string }[] = [
  { id: "routing", label: "执行路由" },
  { id: "topology", label: "能力挂载" },
  { id: "flow", label: "编排画布" },
];

function ArchitectureLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[10px] text-ink-faint">
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-brand" />
        当前路径
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full border border-line bg-surface" />
        未命中
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-3 w-5 rounded border border-dashed border-line-soft" />
        未配置 / 未启用
      </span>
    </div>
  );
}

export function AgentArchitecturePanel({ agentId, agentName }: Props) {
  const router = useRouter();
  const [data, setData] = useState<AgentArchitecture | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<ArchViewTab>("routing");

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

  useEffect(() => {
    if (!data) return;
    const hasFlow = data.primary_path === "flow" && (data.flow_graph?.nodes?.length ?? 0) > 0;
    setTab(hasFlow ? "flow" : "routing");
  }, [agentId, data]);

  const openFlowCanvas = () => {
    const flowId = data?.attachments.flow?.id;
    if (flowId) router.push(`/workbench/flows/${flowId}/edit`);
  };

  if (loading) {
    return <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">加载架构…</div>;
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

  const displayName = agentName?.trim() || "当前智能体";
  const flowNodes = data.flow_graph?.nodes?.length ?? 0;
  const showFlowPreview = flowNodes > 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="shrink-0 space-y-3 border-b border-line-soft px-6 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted">当前执行路径</span>
          <span className="rounded-full bg-brand-light px-3 py-1 text-sm font-medium text-brand">{data.primary_path_label}</span>
        </div>
        <ArchitectureLegend />
        <nav className="flex gap-1 rounded-lg border border-line-soft bg-surface-subtle/50 p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition ${
                tab === t.id ? "bg-surface text-brand shadow-sm" : "text-ink-muted hover:text-ink"
              }`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="relative min-h-0 flex-1">
        {tab === "routing" && (
          <div className="flex h-full min-h-[320px] flex-col">
            <p className="shrink-0 border-b border-line-soft px-6 py-2 text-xs text-ink-faint">
              自上而下为路由优先级；高亮为本次配置下实际命中的分支（与 chat 路由一致）。
            </p>
            <div className="min-h-0 flex-1 bg-surface-subtle/30">
              <AgentArchitectureRoutingGraph steps={data.decision_steps} className="h-full min-h-[300px] w-full" />
            </div>
          </div>
        )}

        {tab === "topology" && (
          <div className="flex h-full min-h-[320px] flex-col">
            <p className="shrink-0 border-b border-line-soft px-6 py-2 text-xs text-ink-faint">
              中心为当前智能体；连线表示已绑定资源（虚线表示未启用或非运行时路径）。
            </p>
            <div className="min-h-0 flex-1 bg-surface-subtle/30">
              <AgentArchitectureTopologyGraph
                agentName={displayName}
                primaryPathLabel={data.primary_path_label}
                attachments={data.attachments}
                className="h-full min-h-[300px] w-full"
              />
            </div>
          </div>
        )}

        {tab === "flow" && (
          <div className="flex h-full min-h-[320px] flex-col">
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-6 py-3">
              <div>
                <p className="text-sm font-medium text-ink">编排流程预览</p>
                <p className="mt-0.5 text-xs text-ink-faint">
                  {data.attachments.flow ? (data.attachments.flow.is_runtime_path ? "当前对话将走此画布" : "已绑定但未作为当前主路径") : "未绑定已发布流程"}
                </p>
              </div>
              {data.attachments.flow ? (
                <button type="button" className="btn-sm-primary shrink-0" onClick={openFlowCanvas}>
                  编辑画布
                </button>
              ) : null}
            </div>
            <div className="relative min-h-0 flex-1 bg-surface-subtle/30">
              {data.attachments.flow && !data.attachments.flow.is_runtime_path && (
                <p className="shrink-0 border-b border-line-soft bg-amber-50/80 px-6 py-2 text-xs text-amber-900">
                  流程已绑定，但当前对话主路径为「{data.primary_path_label}」，运行时不会走此画布。
                </p>
              )}
              {showFlowPreview ? (
                <FlowCanvasPreview graph={data.flow_graph!} className="h-full min-h-[280px] w-full" />
              ) : (
                <div className="flex h-full min-h-[200px] items-center justify-center p-6 text-center text-sm text-ink-muted">
                  {data.attachments.flow ? "流程暂无节点，请进入画布添加节点并发布。" : "在「配置 → 工具与能力」中绑定已发布的编排流程后，可在此预览。"}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
