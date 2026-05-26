"use client";

/**
 * 流程画布（链路 §6，见 lib/chains.ts）：ReactFlow ↔ `flow-nodes` graph_json；
 * 保存后由 FlowService / LangGraph compiler 执行（backend integrations.langgraph.compiler）。
 */
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { EdgeChange, NodeChange } from "@xyflow/react";
import {
  NODE_PALETTE,
  type NodeType,
  createPaletteNode,
  graphToReactFlow,
  reactFlowToGraph,
} from "@/lib/flow-nodes";
import { flowNodeTypes } from "@/components/flow/FlowNodeCard";
import type { FlowGraph } from "@/lib/types";

interface FlowCanvasProps {
  initialGraph?: FlowGraph;
  onGraphChange?: (graph: FlowGraph) => void;
}

type Snapshot = { nodes: Node[]; edges: Edge[] };

function cloneSnapshot(nodes: Node[], edges: Edge[]): Snapshot {
  return {
    nodes: nodes.map((n) => ({ ...n, data: { ...n.data } })),
    edges: edges.map((e) => ({ ...e })),
  };
}

function FlowCanvasToolbar({
  onPushHistory,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
}: {
  onPushHistory: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
}) {
  const { getNodes, getEdges, setNodes, setEdges, deleteElements } = useReactFlow();
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const deleteSelected = useCallback(() => {
    const selectedNodes = getNodes().filter((n) => n.selected);
    const selectedEdges = getEdges().filter((e) => e.selected);
    if (selectedNodes.length === 0 && selectedEdges.length === 0) return;
    onPushHistory();
    deleteElements({
      nodes: selectedNodes.map((n) => ({ id: n.id })),
      edges: selectedEdges.map((e) => ({ id: e.id })),
    });
  }, [getNodes, getEdges, deleteElements, onPushHistory]);

  const clearAll = useCallback(() => {
    if (getNodes().length === 0) return;
    requestConfirm({
      title: "清空画布",
      message: "确定清空画布上所有节点和连线？",
      destructive: true,
      confirmLabel: "确认清空",
      onConfirm: () => {
        onPushHistory();
        setNodes([]);
        setEdges([]);
      },
    });
  }, [getNodes, setNodes, setEdges, onPushHistory, requestConfirm]);

  return (
    <>
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 bg-slate-50 px-2 py-1.5">
      <button
        type="button"
        title="撤销 (Ctrl+Z)"
        disabled={!canUndo}
        onClick={onUndo}
        className="rounded border border-slate-200 bg-white px-2 py-1 text-xs disabled:opacity-40 hover:bg-slate-100"
      >
        撤销
      </button>
      <button
        type="button"
        title="重做 (Ctrl+Shift+Z)"
        disabled={!canRedo}
        onClick={onRedo}
        className="rounded border border-slate-200 bg-white px-2 py-1 text-xs disabled:opacity-40 hover:bg-slate-100"
      >
        重做
      </button>
      <span className="mx-1 h-4 w-px bg-slate-300" />
      <button
        type="button"
        title="删除选中 (Delete)"
        onClick={deleteSelected}
        className="rounded border border-red-200 bg-white px-2 py-1 text-xs text-red-600 hover:bg-red-50"
      >
        删除选中
      </button>
      <button
        type="button"
        onClick={clearAll}
        className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
      >
        清空画布
      </button>
      </div>
      {confirmDialog}
    </>
  );
}

function FlowCanvasInner({ initialGraph, onGraphChange }: FlowCanvasProps) {
  const init = initialGraph ? graphToReactFlow(initialGraph) : { nodes: [], edges: [] };
  const [nodes, setNodes, onNodesChange] = useNodesState(init.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(init.edges);

  const pastRef = useRef<Snapshot[]>([]);
  const futureRef = useRef<Snapshot[]>([]);
  const skipHistoryRef = useRef(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const syncHistoryUi = useCallback(() => {
    setCanUndo(pastRef.current.length > 0);
    setCanRedo(futureRef.current.length > 0);
  }, []);

  const pushHistory = useCallback(() => {
    pastRef.current.push(cloneSnapshot(nodes, edges));
    if (pastRef.current.length > 50) pastRef.current.shift();
    futureRef.current = [];
    syncHistoryUi();
  }, [nodes, edges, syncHistoryUi]);

  const applySnapshot = useCallback(
    (snap: Snapshot) => {
      skipHistoryRef.current = true;
      setNodes(snap.nodes);
      setEdges(snap.edges);
    },
    [setNodes, setEdges]
  );

  const undo = useCallback(() => {
    const past = pastRef.current;
    if (past.length === 0) return;
    futureRef.current.unshift(cloneSnapshot(nodes, edges));
    const prev = past.pop()!;
    applySnapshot(prev);
    syncHistoryUi();
  }, [nodes, edges, applySnapshot, syncHistoryUi]);

  const redo = useCallback(() => {
    const future = futureRef.current;
    if (future.length === 0) return;
    pastRef.current.push(cloneSnapshot(nodes, edges));
    const next = future.shift()!;
    applySnapshot(next);
    syncHistoryUi();
  }, [nodes, edges, applySnapshot, syncHistoryUi]);

  useEffect(() => {
    if (initialGraph) {
      const { nodes: n, edges: e } = graphToReactFlow(initialGraph);
      skipHistoryRef.current = true;
      setNodes(n);
      setEdges(e);
      pastRef.current = [];
      futureRef.current = [];
      syncHistoryUi();
    }
  }, [initialGraph, setNodes, setEdges, syncHistoryUi]);

  useEffect(() => {
    if (skipHistoryRef.current) {
      skipHistoryRef.current = false;
      return;
    }
    onGraphChange?.(reactFlowToGraph(nodes, edges));
  }, [nodes, edges, onGraphChange]);

  const onConnect = useCallback(
    (conn: Connection) => {
      pushHistory();
      setEdges((eds) =>
        addEdge(
          {
            ...conn,
            sourceHandle: conn.sourceHandle || "output",
            targetHandle: conn.targetHandle || "input",
          },
          eds
        )
      );
    },
    [setEdges, pushHistory]
  );

  const onDropPalette = (type: NodeType) => {
    pushHistory();
    const node = createPaletteNode(type, {
      x: 120 + nodes.length * 40,
      y: 120 + nodes.length * 30,
    });
    setNodes((nds) => [...nds, node]);
  };

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      if (!skipHistoryRef.current && changes.some((c) => c.type === "remove")) {
        pushHistory();
      }
      onNodesChange(changes);
    },
    [onNodesChange, pushHistory]
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (!skipHistoryRef.current && changes.some((c) => c.type === "remove")) {
        pushHistory();
      }
      onEdgesChange(changes);
    },
    [onEdgesChange, pushHistory]
  );

  const onNodeDragStart = useCallback(() => {
    pushHistory();
  }, [pushHistory]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === "Z" || e.key === "z") && e.shiftKey) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [undo, redo]);

  return (
    <div className="flex h-full min-h-[520px] flex-col">
      <FlowCanvasToolbar
        onPushHistory={pushHistory}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={undo}
        onRedo={redo}
      />
      <div className="flex min-h-0 flex-1">
        <aside className="w-52 shrink-0 border-r border-slate-200 bg-slate-50 p-3">
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">节点面板</p>
          <div className="mb-4 flex flex-col gap-2">
            {NODE_PALETTE.map((item) => (
              <button
                key={item.type}
                type="button"
                onClick={() => onDropPalette(item.type)}
                className="rounded-md border border-slate-200 bg-white px-2 py-2 text-left text-sm hover:border-brand hover:bg-blue-50"
              >
                <span
                  className="mr-2 inline-block h-2 w-2 rounded-full"
                  style={{ background: item.color }}
                />
                {item.label}
              </button>
            ))}
          </div>
          <p className="text-xs font-semibold uppercase text-slate-500">操作说明</p>
          <ul className="mt-2 space-y-1 text-xs leading-relaxed text-slate-600">
            <li>点击节点或连线进行选中</li>
            <li>
              按 <span className="rounded border border-slate-200 bg-white px-1 font-mono text-[10px]">Delete</span> 或工具栏「删除选中」
            </li>
            <li>
              <span className="rounded border border-slate-200 bg-white px-1 font-mono text-[10px]">Ctrl+Z</span> 撤销，
              <span className="ml-1 rounded border border-slate-200 bg-white px-1 font-mono text-[10px]">Ctrl+Shift+Z</span> 重做
            </li>
            <li>拖拽节点移动；从右侧圆点拖出连线</li>
          </ul>
        </aside>
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={onConnect}
            onNodeDragStart={onNodeDragStart}
            nodesDraggable
            nodesConnectable
            elementsSelectable
            nodeTypes={flowNodeTypes}
            deleteKeyCode={["Backspace", "Delete"]}
            multiSelectionKeyCode={["Shift", "Meta", "Control"]}
            selectionOnDrag
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}

export function FlowCanvas(props: FlowCanvasProps) {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

export default FlowCanvas;
