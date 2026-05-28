"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useGenerativeJobPoll } from "@/hooks/use-generative-job-poll";
import { useElementFullscreen } from "@/hooks/use-element-fullscreen";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { analyzeFlowGenerativeRun } from "@/lib/flow-generative-hints";
import type { FlowRunArtifact } from "@/lib/flow-run-artifacts";
import type { FlowRunState, FlowRunPendingMedia } from "@/components/flow/FlowRunPanel";
import type { FlowCanvasHandle } from "@/components/flow/FlowCanvas";
import { extractPendingGenerativeJobs } from "@/lib/generative-jobs";
import type { ChatMediaIn } from "@/lib/types";
import type { FlowGraph, KnowledgeBase, ModelConfig, PromptTemplate, ToolCatalogItem } from "@/lib/types";

export function useFlowEditPage() {
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
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [testQuery, setTestQuery] = useState("你好");
  const [runMedia, setRunMedia] = useState<FlowRunPendingMedia[]>([]);
  const [runState, setRunState] = useState<FlowRunState | null>(null);
  const [debugPanelOpen, setDebugPanelOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [graphTick, setGraphTick] = useState(0);
  const [pollJobs, setPollJobs] = useState<{ jobId: string; kind: string }[]>([]);
  const [extraRunArtifacts, setExtraRunArtifacts] = useState<FlowRunArtifact[]>([]);

  const {
    statusMsg: generativePollMsg,
    progressPercent: generativeProgress,
    cancelJob: cancelGenerativeJob,
    canCancel: canCancelGenerative,
  } = useGenerativeJobPoll(pollJobs, (artifacts) => {
    setExtraRunArtifacts(
      artifacts.map((a) => ({
        attachmentId: a.attachment_id,
        kind: a.kind as "image" | "video",
        mimeType: a.mime_type,
        label: "异步生成",
      })),
    );
    setPollJobs([]);
  });

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

  const generativeRun = useMemo(
    () => analyzeFlowGenerativeRun(graphRef.current),
    // graphTick 驱动 graphRef 变更后重新分析
    // eslint-disable-next-line react-hooks/exhaustive-deps -- graphRef 非响应式，需 tick 触发
    [graphTick],
  );

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

  const checkCompile = async () => {
    setBusy(true);
    try {
      await api.saveFlowGraph(id, graphRef.current);
      const r = await api.compileFlow(id);
      const parallel = r.parallel_groups?.length > 0 ? `；并行层 ${r.parallel_groups.map((g) => g.join("+")).join(" | ")}` : "";
      const cond = r.conditional_nodes?.length > 0 ? `；条件节点 ${r.conditional_nodes.join(", ")}` : "";
      setRunState((prev) => ({
        output: prev?.output ?? "",
        steps: prev?.steps ?? [],
        compileInfo: r.compilable ? `可编译（${r.node_types.join(" → ")}${parallel}${cond}）` : undefined,
        compileErrorDetails: r.compilable ? undefined : (r.error_details ?? []),
      }));
      setDebugPanelOpen(true);
    } catch (e) {
      setRunState({
        output: "",
        steps: [],
        error: e instanceof Error ? e.message : "编译检查失败",
      });
      setDebugPanelOpen(true);
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    const q = testQuery.trim();
    const media: ChatMediaIn[] = runMedia.map((m) => ({
      attachment_id: m.attachment_id,
    }));
    if (!q && media.length === 0) return;

    setBusy(true);
    setRunState(null);
    setPollJobs([]);
    setExtraRunArtifacts([]);
    try {
      await api.saveFlowGraph(id, graphRef.current);
      const res = await api.runFlow(id, {
        inputs: { query: q || "请根据附图回答。" },
        kb_ids: selectedKbIds,
        media: media.length ? media : undefined,
      });
      const output = typeof res.output === "string" ? res.output : JSON.stringify(res.output, null, 2);
      const steps = (res.steps as Record<string, unknown>[]) ?? [];
      setRunState({
        output,
        steps,
      });
      setPollJobs(
        extractPendingGenerativeJobs(steps).map((j) => ({
          jobId: j.jobId,
          kind: j.kind,
        })),
      );
      setRunMedia([]);
      setDebugPanelOpen(true);
    } catch (e) {
      setRunState({
        output: "",
        steps: [],
        error: e instanceof Error ? e.message : "运行失败",
      });
      setDebugPanelOpen(true);
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

  const cancelGenerativeJobs = () => {
    for (const j of pollJobs) void cancelGenerativeJob(j.jobId);
  };

  return {
    id,
    shellRef,
    isFullscreen,
    toggleFullscreen,
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
    selectedKbIds,
    setSelectedKbIds,
    testQuery,
    setTestQuery,
    runMedia,
    setRunMedia,
    runState,
    debugPanelOpen,
    setDebugPanelOpen,
    msg,
    busy,
    onGraphChange,
    generativeRun,
    generativePollMsg,
    generativeProgress,
    canCancelGenerative,
    extraRunArtifacts,
    save,
    publish,
    checkCompile,
    runTest,
    saveFlowMeta,
    restoreVersion,
    cancelGenerativeJobs,
  };
}

export type FlowEditPageVm = ReturnType<typeof useFlowEditPage>;
