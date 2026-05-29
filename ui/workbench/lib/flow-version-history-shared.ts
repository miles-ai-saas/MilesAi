import type { FlowGraph } from "@/lib/types";

export function formatVersionTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function graphStats(graph: FlowGraph | null): { nodes: number; edges: number } {
  if (!graph) return { nodes: 0, edges: 0 };
  return {
    nodes: graph.nodes?.length ?? 0,
    edges: graph.edges?.length ?? 0,
  };
}
