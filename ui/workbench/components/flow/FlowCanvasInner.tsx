"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState, type Ref } from "react";
import { FlowCanvasPalette } from "@/components/flow/FlowCanvasPalette";
import { FlowCanvasToolbar } from "@/components/flow/FlowCanvasToolbar";
import { FlowNodeInspector } from "@/components/flow/FlowNodeInspector";
import { flowNodeTypes } from "@/components/flow/FlowNodeCard";
import type { FlowCanvasHandle, FlowCanvasProps } from "@/components/flow/flow-canvas-types";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useFlowCanvasHistory } from "@/hooks/use-flow-canvas-history";
import { useFlowTemplates } from "@/hooks/use-flow-templates";
import type { EdgeChange, NodeChange } from "@xyflow/react";
import { createPaletteNode, graphToReactFlow, reactFlowToGraph } from "@/lib/flow-nodes";
import { isValidConnection } from "@/lib/flow-node-schemas";
import type { FlowGraph, FlowTemplate } from "@/lib/types";

export const FlowCanvasInner = forwardRef<FlowCanvasHandle, FlowCanvasProps>(function FlowCanvasInner(
  { initialGraph, onGraphChange, currentFlowId, kbs = [], models = [], prompts = [], toolCatalog = [], className, canvasRef },
  ref,
) {
  const init = initialGraph ? graphToReactFlow(initialGraph) : { nodes: [], edges: [] };
  const [nodes, setNodes, onNodesChange] = useNodesState(init.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(init.edges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [connectHint, setConnectHint] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(true);

  const clearSelection = useCallback(() => setSelectedNode(null), []);
  const { canUndo, canRedo, pushHistory, undo, redo, resetHistory, skipHistoryRef } = useFlowCanvasHistory(nodes, edges, setNodes, setEdges, clearSelection);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const applyGraph = useCallback(
    (graph: FlowGraph) => {
      const { nodes: n, edges: e } = graphToReactFlow(graph);
      skipHistoryRef.current = true;
      setNodes(n);
      setEdges(e);
      setSelectedNode(null);
      resetHistory();
    },
    [setNodes, setEdges, resetHistory, skipHistoryRef],
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

  useImperativeHandle(
    ref,
    () => ({
      loadGraph: applyGraph,
      selectNode,
    }),
    [applyGraph, selectNode],
  );
  useImperativeHandle(
    canvasRef as Ref<FlowCanvasHandle> | undefined,
    () => ({
      loadGraph: applyGraph,
      selectNode,
    }),
    [applyGraph, selectNode],
  );

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
  }, [nodes, edges, onGraphChange, skipHistoryRef]);

  const updateNodeData = useCallback(
    (nodeId: string, patch: Record<string, unknown>) => {
      setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n)));
      setSelectedNode((prev) => (prev?.id === nodeId ? { ...prev, data: { ...prev.data, ...patch } } : prev));
    },
    [setNodes],
  );

  const onConnect = useCallback(
    (conn: Connection) => {
      const sourceNode = nodes.find((n) => n.id === conn.source);
      const targetNode = nodes.find((n) => n.id === conn.target);
      if (!isValidConnection(sourceNode?.type, conn.sourceHandle, targetNode?.type, conn.targetHandle)) {
        setConnectHint(`连线无效：${conn.sourceHandle ?? "output"} → ${conn.targetHandle ?? "input"}（${sourceNode?.type} → ${targetNode?.type}）`);
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

  const onDropPalette = (type: Parameters<typeof createPaletteNode>[0]) => {
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
    [onNodesChange, pushHistory, skipHistoryRef],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (!skipHistoryRef.current && changes.some((c) => c.type === "remove")) {
        pushHistory();
      }
      onEdgesChange(changes);
    },
    [onEdgesChange, pushHistory, skipHistoryRef],
  );

  const onNodeDragStart = useCallback(() => {
    pushHistory();
  }, [pushHistory]);

  const onSelectionChange = useCallback(({ nodes: selNodes }: { nodes: Node[] }) => {
    if (selNodes.length === 1) {
      setSelectedNode(selNodes[0]);
    } else {
      setSelectedNode(null);
    }
  }, []);

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
    (tpl: FlowTemplate) => confirmReplaceGraph(`插入「${tpl.label}」模板`, tpl.graph_json),
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
      {connectHint && <p className="border-b border-amber-200/80 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">{connectHint}</p>}
      <div className="flex min-h-0 flex-1">
        <FlowCanvasPalette open={paletteOpen} onToggle={setPaletteOpen} onDropPalette={onDropPalette} />
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
          currentFlowId={currentFlowId}
          onChange={updateNodeData}
        />
      </div>
      {confirmDialog}
    </div>
  );
});
