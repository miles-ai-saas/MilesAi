"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { FlowGraph, FlowVersionSummary } from "@/lib/types";

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

function graphStats(graph: FlowGraph | null): { nodes: number; edges: number } {
  if (!graph) return { nodes: 0, edges: 0 };
  return {
    nodes: graph.nodes?.length ?? 0,
    edges: graph.edges?.length ?? 0,
  };
}

export type FlowVersionHistoryProps = {
  flowId: string;
  open: boolean;
  currentVersion: number;
  onClose: () => void;
  onRestored: (graph: FlowGraph, newVersion: number) => void;
};

export function useFlowVersionHistory({ flowId, open, currentVersion, onClose, onRestored }: FlowVersionHistoryProps) {
  const [versions, setVersions] = useState<FlowVersionSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [previewGraph, setPreviewGraph] = useState<FlowGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState("");
  const [diffMode, setDiffMode] = useState(false);
  const [diffTarget, setDiffTarget] = useState<number | null>(null);
  const [diffGraph, setDiffGraph] = useState<FlowGraph | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const selectedMeta = useMemo(() => versions.find((v) => v.version === selected) ?? null, [versions, selected]);
  const stats = useMemo(() => graphStats(previewGraph), [previewGraph]);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await api.listFlowVersions(flowId);
      setVersions(list);
      if (list.length > 0) {
        setSelected((prev) => {
          if (prev !== null) return prev;
          const cur = list.find((v) => v.version === currentVersion);
          return cur?.version ?? list[0].version;
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载版本失败");
    } finally {
      setLoading(false);
    }
  }, [flowId, currentVersion]);

  useEffect(() => {
    if (open) {
      setSelected(null);
      setPreviewGraph(null);
      void loadList();
    }
  }, [open, loadList]);

  useEffect(() => {
    if (!open || selected === null) return;
    setPreviewLoading(true);
    api
      .getFlowVersion(flowId, selected)
      .then((v) => setPreviewGraph(v.graph_json))
      .catch((e) => {
        setPreviewGraph(null);
        setError(e instanceof Error ? e.message : "加载预览失败");
      })
      .finally(() => setPreviewLoading(false));
  }, [open, flowId, selected]);

  const restore = async () => {
    if (selected === null || !previewGraph) return;
    setRestoring(true);
    setError("");
    try {
      const saved = await api.saveFlowGraph(flowId, previewGraph, `恢复自 v${selected}`);
      onRestored(saved.graph_json, saved.version);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复失败");
    } finally {
      setRestoring(false);
    }
  };

  const canRestore = !restoring && selected !== null && previewGraph !== null && selected !== currentVersion;

  const loadDiffGraph = async (v: number) => {
    setDiffTarget(v);
    setDiffLoading(true);
    try {
      const ver = await api.getFlowVersion(flowId, v);
      setDiffGraph(ver.graph_json);
    } catch {
      setDiffGraph(null);
    } finally {
      setDiffLoading(false);
    }
  };

  const toggleDiffMode = () => {
    if (diffMode) {
      setDiffMode(false);
      setDiffTarget(null);
      setDiffGraph(null);
    } else {
      setDiffMode(true);
      setDiffTarget(currentVersion);
      void loadDiffGraph(currentVersion);
    }
  };

  const diffResult = useMemo(() => {
    if (!diffMode || !previewGraph || !diffGraph) return null;
    const a = JSON.stringify(previewGraph, null, 2).split("\n");
    const b = JSON.stringify(diffGraph, null, 2).split("\n");
    return { a, b };
  }, [diffMode, previewGraph, diffGraph]);

  return {
    versions,
    selected,
    setSelected,
    previewGraph,
    loading,
    previewLoading,
    restoring,
    error,
    diffMode,
    diffTarget,
    diffLoading,
    selectedMeta,
    stats,
    canRestore,
    diffResult,
    restore,
    loadDiffGraph,
    toggleDiffMode,
  };
}

export type FlowVersionHistoryVm = ReturnType<typeof useFlowVersionHistory>;
