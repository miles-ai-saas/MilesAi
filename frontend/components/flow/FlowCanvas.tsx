"use client";

/**
 * 流程画布（链路 §6）：ReactFlow ↔ flow-nodes；FlowNodeInspector / flow-node-schemas。
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
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useFlowTemplates } from "@/hooks/use-flow-templates";
import type { EdgeChange, NodeChange } from "@xyflow/react";
import {
  PALETTE_GROUPS,
  paletteItemsByGroup,
  type NodeType,
  createPaletteNode,
  graphToReactFlow,
  reactFlowToGraph,
} from "@/lib/flow-nodes";
import type { FlowTemplate } from "@/lib/types";
import { isValidConnection } from "@/lib/flow-node-schemas";
import { flowNodeTypes } from "@/components/flow/FlowNodeCard";
import { FlowNodeInspector } from "@/components/flow/FlowNodeInspector";
import type {
  FlowGraph,
  KnowledgeBase,
  ModelConfig,
  PromptTemplate,
  ToolCatalogItem,
} from "@/lib/types";

export interface FlowCanvasHandle {
  loadGraph: (graph: FlowGraph) => void;
  selectNode: (nodeId: string) => void;
}

interface FlowCanvasProps {
  initialGraph?: FlowGraph;
  onGraphChange?: (graph: FlowGraph) => void;
  kbs?: KnowledgeBase[];
  models?: ModelConfig[];
  prompts?: PromptTemplate[];
  toolCatalog?: ToolCatalogItem[];
  className?: string;
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
  insertableTemplates,
  onInsertTemplate,
}: {
  onPushHistory: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  insertableTemplates: FlowTemplate[];
  onInsertTemplate: (template: FlowTemplate) => void;
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
      <div className="flex flex-wrap items-center gap-1 border-b border-line bg-surface px-2 py-1.5">
        <button
          type="button"
          title="撤销 (Ctrl+Z)"
          disabled={!canUndo}
          onClick={onUndo}
          className="btn-sm-ghost disabled:opacity-40"
        >
          撤销
        </button>
        <button
          type="button"
          title="重做 (Ctrl+Shift+Z)"
          disabled={!canRedo}
          onClick={onRedo}
          className="btn-sm-ghost disabled:opacity-40"
        >
          重做
        </button>
        <span className="mx-0.5 h-4 w-px bg-line" />
        <button
          type="button"
          title="删除选中 (Delete)"
          onClick={deleteSelected}
          className="btn-sm text-red-600 hover:bg-red-50"
        >
          删除
        </button>
        <button type="button" onClick={clearAll} className="btn-sm-ghost">
          清空
        </button>
        <span className="mx-0.5 h-4 w-px bg-line" />
        {insertableTemplates.length > 0 && (
          <label className="inline-flex items-center gap-1.5 text-sm">
            <span className="text-ink-muted">插入模板</span>
            <select
              className="input-field max-w-[11rem] py-1 text-sm"
              defaultValue=""
              onChange={(e) => {
                const id = e.target.value;
                e.target.value = "";
                const tpl = insertableTemplates.find((t) => t.id === id);
                if (tpl) onInsertTemplate(tpl);
              }}
            >
              <option value="" disabled>
                选择…
              </option>
              {insertableTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {confirmDialog}
    </>
  );
}

const FlowCanvasInner = forwardRef<FlowCanvasHandle, FlowCanvasProps>(
  function FlowCanvasInner(
    {
      initialGraph,
      onGraphChange,
      kbs = [],
      models = [],
      prompts = [],
      toolCatalog = [],
      className,
    },
    ref,
  ) {
    const init = initialGraph
      ? graphToReactFlow(initialGraph)
      : { nodes: [], edges: [] };
    const [nodes, setNodes, onNodesChange] = useNodesState(init.nodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(init.edges);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);
    const [connectHint, setConnectHint] = useState("");
    const [paletteOpen, setPaletteOpen] = useState(true);

    const pastRef = useRef<Snapshot[]>([]);
    const futureRef = useRef<Snapshot[]>([]);
    const skipHistoryRef = useRef(false);
    const [canUndo, setCanUndo] = useState(false);
    const [canRedo, setCanRedo] = useState(false);
    const { requestConfirm, confirmDialog } = useConfirmAction();

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

    const applyGraph = useCallback(
      (graph: FlowGraph) => {
        const { nodes: n, edges: e } = graphToReactFlow(graph);
        skipHistoryRef.current = true;
        setNodes(n);
        setEdges(e);
        setSelectedNode(null);
        pastRef.current = [];
        futureRef.current = [];
        syncHistoryUi();
      },
      [setNodes, setEdges, syncHistoryUi],
    );

    const selectNode = useCallback(
      (nodeId: string) => {
        setNodes((nds) => {
          const target = nds.find((n) => n.id === nodeId);
          setSelectedNode(target ? { ...target, selected: true } : null);
          return nds.map((n) => ({ ...n, selected: n.id === nodeId }));
        });
      },
      [setNodes],
    );

    useImperativeHandle(ref, () => ({
      loadGraph: applyGraph,
      selectNode,
    }));

    const applySnapshot = useCallback(
      (snap: Snapshot) => {
        skipHistoryRef.current = true;
        setNodes(snap.nodes);
        setEdges(snap.edges);
        setSelectedNode(null);
      },
      [setNodes, setEdges],
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
        applyGraph(initialGraph);
      }
    }, [initialGraph, applyGraph]);

    useEffect(() => {
      if (skipHistoryRef.current) {
        skipHistoryRef.current = false;
        return;
      }
      onGraphChange?.(reactFlowToGraph(nodes, edges));
    }, [nodes, edges, onGraphChange]);

    const updateNodeData = useCallback(
      (nodeId: string, patch: Record<string, unknown>) => {
        setNodes((nds) =>
          nds.map((n) =>
            n.id === nodeId
              ? { ...n, data: { ...n.data, ...patch } }
              : n,
          ),
        );
        setSelectedNode((prev) =>
          prev?.id === nodeId
            ? { ...prev, data: { ...prev.data, ...patch } }
            : prev,
        );
      },
      [setNodes],
    );

    const onConnect = useCallback(
      (conn: Connection) => {
        const sourceNode = nodes.find((n) => n.id === conn.source);
        const targetNode = nodes.find((n) => n.id === conn.target);
        if (
          !isValidConnection(
            sourceNode?.type,
            conn.sourceHandle,
            targetNode?.type,
            conn.targetHandle,
          )
        ) {
          setConnectHint(
            `连线无效：${conn.sourceHandle ?? "output"} → ${conn.targetHandle ?? "input"}（${sourceNode?.type} → ${targetNode?.type}）`,
          );
          window.setTimeout(() => setConnectHint(""), 4000);
          return;
        }
        setConnectHint("");
        pushHistory();
        setEdges((eds) =>
          addEdge(
            {
              ...conn,
              sourceHandle: conn.sourceHandle || "output",
              targetHandle: conn.targetHandle || "input",
            },
            eds,
          ),
        );
      },
      [nodes, setEdges, pushHistory],
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
      [onNodesChange, pushHistory],
    );

    const handleEdgesChange = useCallback(
      (changes: EdgeChange[]) => {
        if (!skipHistoryRef.current && changes.some((c) => c.type === "remove")) {
          pushHistory();
        }
        onEdgesChange(changes);
      },
      [onEdgesChange, pushHistory],
    );

    const onNodeDragStart = useCallback(() => {
      pushHistory();
    }, [pushHistory]);

    const onSelectionChange = useCallback(
      ({ nodes: selNodes }: { nodes: Node[] }) => {
        if (selNodes.length === 1) {
          setSelectedNode(selNodes[0]);
        } else {
          setSelectedNode(null);
        }
      },
      [],
    );

    const confirmReplaceGraph = useCallback(
      (title: string, graph: FlowGraph) => {
        const apply = () => {
          if (nodes.length > 0) pushHistory();
          applyGraph(graph);
        };
        if (nodes.length > 0) {
          requestConfirm({
            title,
            message: "将替换当前画布上所有节点与连线，是否继续？",
            destructive: true,
            confirmLabel: "替换画布",
            onConfirm: apply,
          });
        } else {
          apply();
        }
      },
      [nodes.length, requestConfirm, applyGraph, pushHistory],
    );

    const { insertable: insertableTemplates } = useFlowTemplates();

    const insertTemplate = useCallback(
      (tpl: FlowTemplate) =>
        confirmReplaceGraph(`插入「${tpl.label}」模板`, tpl.graph_json),
      [confirmReplaceGraph],
    );

    useEffect(() => {
      const onKeyDown = (e: KeyboardEvent) => {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

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
      <div className={`flex h-full min-h-0 flex-col ${className ?? ""}`}>
        <FlowCanvasToolbar
          onPushHistory={pushHistory}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={undo}
          onRedo={redo}
          insertableTemplates={insertableTemplates}
          onInsertTemplate={insertTemplate}
        />
        {connectHint && (
          <p className="border-b border-amber-200/80 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">
            {connectHint}
          </p>
        )}
        <div className="flex min-h-0 flex-1">
          {paletteOpen ? (
            <aside className="flex w-44 shrink-0 flex-col border-r border-line bg-surface sm:w-48">
              <div className="flex items-center justify-between border-b border-line px-2 py-2">
                <span className="text-xs font-semibold text-ink-muted">节点</span>
                <button
                  type="button"
                  className="btn-sm-ghost !px-1.5 text-[10px]"
                  onClick={() => setPaletteOpen(false)}
                  title="收起节点面板"
                >
                  ‹
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-2">
                <div className="flex flex-col gap-3">
                  {PALETTE_GROUPS.map((group) => {
                    const items = paletteItemsByGroup(group.key);
                    if (!items.length) return null;
                    return (
                      <div key={group.key}>
                        <p className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
                          {group.label}
                        </p>
                        <div className="flex flex-col gap-1">
                          {items.map((item) => (
                            <button
                              key={item.type}
                              type="button"
                              onClick={() => onDropPalette(item.type)}
                              className="flex items-center gap-2 rounded-lg border border-line bg-surface px-2 py-2 text-left text-xs transition hover:border-brand/50 hover:bg-brand-light"
                            >
                              <span
                                className="h-2 w-2 shrink-0 rounded-full"
                                style={{ background: item.color }}
                              />
                              <span className="text-ink">{item.label}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-3 text-[10px] leading-relaxed text-ink-faint">
                  选中节点在右侧编辑；Delete 删除；Ctrl+Z 撤销
                </p>
              </div>
            </aside>
          ) : (
            <div className="flex w-9 shrink-0 flex-col items-center border-r border-line bg-surface py-2">
              <button
                type="button"
                className="btn-sm-ghost !px-1 text-lg leading-none"
                onClick={() => setPaletteOpen(true)}
                title="展开节点面板"
                aria-label="展开节点面板"
              >
                ›
              </button>
            </div>
          )}
          <div className="min-w-0 flex-1 bg-white">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={handleNodesChange}
              onEdgesChange={handleEdgesChange}
              onConnect={onConnect}
              onNodeDragStart={onNodeDragStart}
              onSelectionChange={onSelectionChange}
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
          <FlowNodeInspector
            node={selectedNode}
            kbs={kbs}
            models={models}
            prompts={prompts}
            toolCatalog={toolCatalog}
            onChange={updateNodeData}
          />
        </div>
        {confirmDialog}
      </div>
    );
  },
);

export const FlowCanvas = forwardRef<FlowCanvasHandle, FlowCanvasProps>(
  function FlowCanvas(props, ref) {
    return (
      <ReactFlowProvider>
        <FlowCanvasInner {...props} ref={ref} />
      </ReactFlowProvider>
    );
  },
);

export default FlowCanvas;
