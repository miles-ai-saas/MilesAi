"use client";

import { useMemo, useState } from "react";
import type { MutableRefObject } from "react";
import { useGenerativeJobPoll } from "@/hooks/use-generative-job-poll";
import { api } from "@/lib/api";
import { analyzeFlowGenerativeRun } from "@/features/flows/lib/flow-generative-hints";
import type { FlowRunArtifact } from "@/features/flows/lib/flow-run-artifacts";
import type { FlowRunState, FlowRunPendingMedia } from "@/features/flows/lib/flow-run-panel-shared";
import { extractPendingGenerativeJobs } from "@/lib/generative-jobs";
import type { ChatMediaIn, FlowGraph } from "@/lib/types";

type DebugSliceDeps = {
  id: string;
  graphRef: MutableRefObject<FlowGraph>;
  graphTick: number;
  busy: boolean;
  setBusy: (busy: boolean) => void;
};

export function useFlowEditDebug({ id, graphRef, graphTick, setBusy }: DebugSliceDeps) {
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [testQuery, setTestQuery] = useState("你好");
  const [runMedia, setRunMedia] = useState<FlowRunPendingMedia[]>([]);
  const [runState, setRunState] = useState<FlowRunState | null>(null);
  const [debugPanelOpen, setDebugPanelOpen] = useState(false);
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

  const generativeRun = useMemo(
    () => analyzeFlowGenerativeRun(graphRef.current),
    // graphTick 驱动 graphRef 变更后重新分析
    // eslint-disable-next-line react-hooks/exhaustive-deps -- graphRef 非响应式，需 tick 触发
    [graphTick],
  );

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

  const cancelGenerativeJobs = () => {
    for (const j of pollJobs) void cancelGenerativeJob(j.jobId);
  };

  return {
    selectedKbIds,
    setSelectedKbIds,
    testQuery,
    setTestQuery,
    runMedia,
    setRunMedia,
    runState,
    debugPanelOpen,
    setDebugPanelOpen,
    generativeRun,
    generativePollMsg,
    generativeProgress,
    canCancelGenerative,
    extraRunArtifacts,
    checkCompile,
    runTest,
    cancelGenerativeJobs,
  };
}

export type FlowEditDebugSlice = ReturnType<typeof useFlowEditDebug>;
