/**
 * 智能体架构图：由 GET /agents/{id}/architecture 数据生成 React Flow 节点/边。
 */

import type { Edge, Node } from "@xyflow/react";
import type {
  AgentArchitectureAttachments,
  AgentArchitectureDecisionStep,
} from "@/lib/types";

export type ArchitectureNodeData = {
  label: string;
  subtitle?: string;
  description?: string | null;
  active?: boolean;
  onPath?: boolean;
  variant?: "step" | "hub" | "attachment";
  muted?: boolean;
};

const ROUTING_ORDER = ["entry", "a2a_host", "subagent", "a2a_augmented", "flow"] as const;
const TERMINAL_IDS = new Set(["no_kb", "rag", "rag_fallback"]);

const NODE_W = 200;
const NODE_H = 56;
const GAP_Y = 24;

export function buildRoutingGraph(
  steps: AgentArchitectureDecisionStep[],
): { nodes: Node<ArchitectureNodeData>[]; edges: Edge[] } {
  const byId = new Map(steps.map((s) => [s.id, s]));
  const ordered: AgentArchitectureDecisionStep[] = [];
  for (const id of ROUTING_ORDER) {
    const s = byId.get(id);
    if (s) ordered.push(s);
  }
  const terminal = steps.find((s) => TERMINAL_IDS.has(s.id));
  if (terminal) ordered.push(terminal);

  const activeIdx = ordered.findIndex((s) => s.active);

  const nodes: Node<ArchitectureNodeData>[] = ordered.map((step, i) => {
    const onPath = activeIdx >= 0 && i <= activeIdx;
    const unconfigured = (step.description ?? "").includes("未配置");
    const notPublished = (step.description ?? "").includes("未绑定或未发布");
    return {
      id: step.id,
      type: "architectureNode",
      position: { x: 24, y: i * (NODE_H + GAP_Y) },
      data: {
        label: step.label,
        description: step.description,
        active: step.active,
        onPath,
        variant: "step",
        muted: !onPath && (unconfigured || notPublished),
      },
    };
  });

  const edges: Edge[] = [];
  for (let i = 0; i < ordered.length - 1; i += 1) {
    const onEdge = activeIdx >= 0 && i < activeIdx;
    edges.push({
      id: `e-${ordered[i].id}-${ordered[i + 1].id}`,
      source: ordered[i].id,
      target: ordered[i + 1].id,
      animated: onEdge && ordered[i + 1].active,
      style: {
        stroke: onEdge ? "var(--brand)" : "var(--line)",
        strokeWidth: onEdge ? 2 : 1,
      },
    });
  }

  return { nodes, edges };
}

export function buildTopologyGraph(
  attachments: AgentArchitectureAttachments,
  agentName: string,
  primaryPathLabel: string,
): { nodes: Node<ArchitectureNodeData>[]; edges: Edge[] } {
  const cx = 200;
  const cy = 160;
  const nodes: Node<ArchitectureNodeData>[] = [
    {
      id: "agent-hub",
      type: "architectureNode",
      position: { x: cx - NODE_W / 2, y: cy - NODE_H / 2 },
      data: {
        label: agentName,
        subtitle: primaryPathLabel,
        variant: "hub",
        active: true,
        onPath: true,
      },
    },
  ];
  const edges: Edge[] = [];

  const attach = (
    id: string,
    label: string,
    subtitle: string,
    position: { x: number; y: number },
    opts?: { muted?: boolean; active?: boolean },
  ) => {
    nodes.push({
      id,
      type: "architectureNode",
      position,
      data: {
        label,
        subtitle,
        variant: "attachment",
        muted: opts?.muted,
        active: opts?.active,
        onPath: opts?.active,
      },
    });
    edges.push({
      id: `e-hub-${id}`,
      source: "agent-hub",
      target: id,
      style: {
        stroke: opts?.muted ? "var(--line)" : "var(--brand)",
        strokeDasharray: opts?.muted ? "4 4" : undefined,
      },
    });
  };

  if (attachments.model) {
    attach(
      `model-${attachments.model.id}`,
      attachments.model.name,
      "大模型",
      { x: cx - NODE_W / 2, y: cy - 120 },
      { active: true },
    );
  }

  attachments.kbs.forEach((kb, i) => {
    const n = attachments.kbs.length;
    const offsetY = (i - (n - 1) / 2) * (NODE_H + 12);
    attach(`kb-${kb.id}`, kb.name, "知识库", { x: cx - 240, y: cy - 20 + offsetY });
  });

  attachments.sub_agents.forEach((sub, i) => {
    const n = attachments.sub_agents.length;
    const offsetY = (i - (n - 1) / 2) * (NODE_H + 12);
    attach(
      `sub-${sub.id}`,
      sub.name,
      sub.role_hint ? `子智能体 · ${sub.role_hint}` : "子智能体",
      { x: cx + 40, y: cy - 20 + offsetY },
      { active: true },
    );
  });

  attachments.a2a_peers.forEach((peer, i) => {
    const n = attachments.a2a_peers.length;
    const offsetX = (i - (n - 1) / 2) * (NODE_W + 16);
    attach(
      `peer-${peer.id}`,
      peer.name,
      peer.role_hint ? `A2A · ${peer.role_hint}` : "A2A 对端",
      { x: cx - NODE_W / 2 + offsetX, y: cy + 100 },
      { muted: !peer.enabled, active: peer.enabled },
    );
  });

  if (attachments.flow) {
    const flowActive = attachments.flow.is_runtime_path;
    const flowY = attachments.a2a_peers.length > 0 ? cy + 150 : cy + 100;
    attach(
      `flow-${attachments.flow.id}`,
      attachments.flow.name,
      `流程 v${attachments.flow.version}${flowActive ? " · 运行时" : ""}`,
      { x: cx - NODE_W / 2, y: flowY },
      { muted: !flowActive, active: flowActive },
    );
  }

  return { nodes, edges };
}

export const ARCHITECTURE_GRAPH_MIN_HEIGHT = 320;
