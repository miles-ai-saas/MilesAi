"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useElementFullscreen } from "@/hooks/use-element-fullscreen";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { FlowCanvasHandle } from "@/components/flow/FlowCanvas";
import type { FlowGraph, KnowledgeBase, ModelConfig, PromptTemplate, ToolCatalogItem } from "@/lib/types";

export function useFlowEditCore() {
  const { id } = useParams<{ id: string }>();
  const { ready } = useRequireAuth();
  const graphRef = useRef<FlowGraph>({ nodes: [], edges: [] });
  const canvasRef = useRef<FlowCanvasHandle>(null);
  const [initialGraph, setInitialGraph] = useState<FlowGraph | undefined>();
  const [flowName, setFlowName] = useState("");
  const [flowDescription, setFlowDescription] = useState<string | null>(null);
  const [flowTagIds, setFlowTagIds] = useState<string[]>([]);
  const [currentVersion, setCurrentVersion] = useState(0);
  const [metaOpen, setMetaOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [toolCatalog, setToolCatalog] = useState<ToolCatalogItem[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [graphTick, setGraphTick] = useState(0);

  const { ref: shellRef, active: isFullscreen, toggle: toggleFullscreen } = useElementFullscreen<HTMLDivElement>();

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.getFlow(id), api.getFlowGraph(id), api.listKbs(1, 100), api.listModelConfigs(), api.listPromptTemplates(1, 100), api.listToolCatalog()])
      .then(([flow, version, kbPage, modelList, promptPage, catalog]) => {
        setFlowName(flow.name);
        setFlowDescription(flow.description ?? null);
        setFlowTagIds(flow.tags?.map((t) => t.id) ?? []);
        setCurrentVersion(flow.current_version);
        setInitialGraph(version.graph_json);
        graphRef.current = version.graph_json;
        setKbs(kbPage.items);
        setModels(modelList.filter((m) => m.is_active !== false));
        setPrompts(promptPage.items.filter((p) => p.is_active !== false));
        setToolCatalog(catalog);
      })
      .catch(() => {
        setInitialGraph({ nodes: [], edges: [] });
      });
  }, [id, ready]);

  const onGraphChange = useCallback((g: FlowGraph) => {
    graphRef.current = g;
    setGraphTick((t) => t + 1);
  }, []);

  const save = async () => {
    setBusy(true);
    setMsg("");
    try {
      const v = await api.saveFlowGraph(id, graphRef.current, "画布保存");
      setCurrentVersion(v.version);
      setMsg("已保存");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    setBusy(true);
    try {
      await api.saveFlowGraph(id, graphRef.current);
      await api.publishFlow(id);
      setMsg("已发布");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "发布失败");
    } finally {
      setBusy(false);
    }
  };

  const saveFlowMeta = async (name: string, description: string, tagIds: string[]) => {
    const updated = await api.updateFlow(id, {
      name,
      description: description || null,
      tag_ids: tagIds,
    });
    setFlowName(updated.name);
    setFlowDescription(updated.description ?? null);
    setFlowTagIds(updated.tags?.map((t) => t.id) ?? []);
    setMsg("基本信息已保存");
  };

  const restoreVersion = (graph: FlowGraph, ver: number) => {
    graphRef.current = graph;
    setInitialGraph(graph);
    setCurrentVersion(ver);
    canvasRef.current?.loadGraph(graph);
    setMsg(`已恢复为 v${ver}（新版本）`);
  };

  return {
    id,
    graphRef,
    canvasRef,
    initialGraph,
    flowName,
    flowDescription,
    flowTagIds,
    currentVersion,
    metaOpen,
    setMetaOpen,
    historyOpen,
    setHistoryOpen,
    kbs,
    models,
    prompts,
    toolCatalog,
    msg,
    busy,
    setBusy,
    graphTick,
    shellRef,
    isFullscreen,
    toggleFullscreen,
    onGraphChange,
    save,
    publish,
    saveFlowMeta,
    restoreVersion,
  };
}

export type FlowEditCoreSlice = ReturnType<typeof useFlowEditCore>;
