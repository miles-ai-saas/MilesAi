"use client";

import { addEdge, useEdgesState, useNodesState, type Connection, type Node, type EdgeChange, type NodeChange } from "@xyflow/react";
import { useCallback, useEffect, useImperativeHandle, useState, type Ref } from "react";
import type { FlowCanvasHandle, FlowCanvasProps } from "@/features/flows/components/flow-canvas-types";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useFlowCanvasHistory } from "@/features/flows/hooks/use-flow-canvas-history";
import { useFlowTemplates } from "@/features/flows/hooks/use-flow-templates";
import { createPaletteNode, graphToReactFlow, reactFlowToGraph } from "@/features/flows/lib/flow-nodes";
import { isValidConnection } from "@/features/flows/lib/flow-node-schemas";
import type { FlowGraph, FlowTemplate } from "@/lib/types";

type Params = Pick<FlowCanvasProps, "initialGraph" | "onGraphChange" | "canvasRef"> & {
  forwardedRef: Ref<FlowCanvasHandle>;
};

export function useFlowCanvasCore({ initialGraph, onGraphChange, canvasRef, forwardedRef }: Params) {
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

  const imperativeHandle: FlowCanvasHandle = {
    loadGraph: applyGraph,
    selectNode,
  };

  useImperativeHandle(forwardedRef, () => imperativeHandle, [applyGraph, selectNode]);
  useImperativeHandle(canvasRef as Ref<FlowCanvasHandle> | undefined, () => imperativeHandle, [applyGraph, selectNode]);

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

  return {
    nodes,
    edges,
    selectedNode,
    connectHint,
    paletteOpen,
    setPaletteOpen,
    canUndo,
    canRedo,
    undo,
    redo,
    pushHistory,
    confirmDialog,
    updateNodeData,
    onConnect,
    onDropPalette,
    handleNodesChange,
    handleEdgesChange,
    onNodeDragStart,
    onSelectionChange,
    insertableTemplates,
    insertTemplate,
  };
}
