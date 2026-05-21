"use client";

import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { FlowGraph } from "@/lib/types";

const FlowCanvas = dynamic(
  () => import("@/components/flow/FlowCanvas").then((m) => m.FlowCanvas),
  { ssr: false }
);

export default function FlowEditPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { ready } = useRequireAuth();
  const graphRef = useRef<FlowGraph>({ nodes: [], edges: [] });
  const [initialGraph, setInitialGraph] = useState<FlowGraph | undefined>();
  const [flowName, setFlowName] = useState("");
  const [testQuery, setTestQuery] = useState("你好");
  const [runResult, setRunResult] = useState("");
  const [compileInfo, setCompileInfo] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ready) return;
    api
      .getFlowGraph(id)
      .then((v) => {
        setInitialGraph(v.graph_json);
        graphRef.current = v.graph_json;
      })
      .catch(() => {
        setInitialGraph({ nodes: [], edges: [] });
      });
  }, [id, ready, router]);

  const onGraphChange = useCallback((g: FlowGraph) => {
    graphRef.current = g;
  }, []);

  const save = async () => {
    setBusy(true);
    setMsg("");
    try {
      await api.saveFlowGraph(id, graphRef.current, "画布保存");
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
    setCompileInfo("");
    try {
      await api.saveFlowGraph(id, graphRef.current);
      const r = await api.compileFlow(id);
      const parallel =
        r.parallel_groups?.length > 0
          ? `；并行层 ${r.parallel_groups.map((g) => g.join("+")).join(" | ")}`
          : "";
      const cond =
        r.conditional_nodes?.length > 0 ? `；条件节点 ${r.conditional_nodes.join(", ")}` : "";
      setCompileInfo(
        r.compilable
          ? `可编译为 LangGraph（${r.node_types.join(" → ")}${parallel}${cond}）`
          : `不可编译：${r.errors.join("; ")}`,
      );
    } catch (e) {
      setCompileInfo(e instanceof Error ? e.message : "编译检查失败");
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    setBusy(true);
    setRunResult("");
    try {
      await api.saveFlowGraph(id, graphRef.current);
      const res = await api.runFlow(id, { query: testQuery });
      setRunResult(
        typeof res.output === "string" ? res.output : JSON.stringify(res.output, null, 2)
      );
    } catch (e) {
      setRunResult(e instanceof Error ? e.message : "运行失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-80px)] flex-col rounded-xl border border-line bg-surface shadow-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2">
        <span className="font-medium text-ink">{flowName || `流程 ${id.slice(0, 8)}`}</span>
        <button
          type="button"
          onClick={save}
          disabled={busy}
          className="rounded border border-line px-3 py-1 text-sm hover:bg-surface-muted"
        >
          保存
        </button>
        <button
          type="button"
          onClick={publish}
          disabled={busy}
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white hover:bg-emerald-700"
        >
          发布
        </button>
        <input
          className="ml-4 rounded border border-line px-2 py-1 text-sm"
          value={testQuery}
          onChange={(e) => setTestQuery(e.target.value)}
          placeholder="调试输入 query"
        />
        <button
          type="button"
          onClick={checkCompile}
          disabled={busy}
          className="rounded border border-line px-3 py-1 text-sm hover:bg-surface-muted"
        >
          编译检查
        </button>
        <button
          type="button"
          onClick={runTest}
          disabled={busy}
          className="rounded bg-brand px-3 py-1 text-sm text-white"
        >
          调试运行
        </button>
        {compileInfo && <span className="text-xs text-ink-muted">{compileInfo}</span>}
        {msg && <span className="text-sm text-emerald-600">{msg}</span>}
      </div>
      <div className="min-h-0 flex-1">
        {initialGraph !== undefined && (
          <FlowCanvas initialGraph={initialGraph} onGraphChange={onGraphChange} />
        )}
      </div>
      {runResult && (
        <pre className="max-h-32 overflow-auto border-t border-line bg-surface-muted p-3 text-xs">
          {runResult}
        </pre>
      )}
    </div>
  );
}
