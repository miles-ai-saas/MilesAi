import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type { Edge, Node } from "@xyflow/react";

export type FlowCanvasSnapshot = { nodes: Node[]; edges: Edge[] };

export function cloneFlowCanvasSnapshot(nodes: Node[], edges: Edge[]): FlowCanvasSnapshot {
  return {
    nodes: nodes.map((n) => ({ ...n, data: { ...n.data } })),
    edges: edges.map((e) => ({ ...e })),
  };
}

export function useFlowCanvasHistory(
  nodes: Node[],
  edges: Edge[],
  setNodes: Dispatch<SetStateAction<Node[]>>,
  setEdges: Dispatch<SetStateAction<Edge[]>>,
  onSelectionClear: () => void,
) {
  const pastRef = useRef<FlowCanvasSnapshot[]>([]);
  const futureRef = useRef<FlowCanvasSnapshot[]>([]);
  const skipHistoryRef = useRef(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const syncHistoryUi = useCallback(() => {
    setCanUndo(pastRef.current.length > 0);
    setCanRedo(futureRef.current.length > 0);
  }, []);

  const pushHistory = useCallback(() => {
    pastRef.current.push(cloneFlowCanvasSnapshot(nodes, edges));
    if (pastRef.current.length > 50) pastRef.current.shift();
    futureRef.current = [];
    syncHistoryUi();
  }, [nodes, edges, syncHistoryUi]);

  const applySnapshot = useCallback(
    (snap: FlowCanvasSnapshot) => {
      skipHistoryRef.current = true;
      setNodes(snap.nodes);
      setEdges(snap.edges);
      onSelectionClear();
    },
    [setNodes, setEdges, onSelectionClear],
  );

  const resetHistory = useCallback(() => {
    pastRef.current = [];
    futureRef.current = [];
    syncHistoryUi();
  }, [syncHistoryUi]);

  const undo = useCallback(() => {
    const past = pastRef.current;
    if (past.length === 0) return;
    futureRef.current.unshift(cloneFlowCanvasSnapshot(nodes, edges));
    const prev = past.pop()!;
    applySnapshot(prev);
    syncHistoryUi();
  }, [nodes, edges, applySnapshot, syncHistoryUi]);

  const redo = useCallback(() => {
    const future = futureRef.current;
    if (future.length === 0) return;
    pastRef.current.push(cloneFlowCanvasSnapshot(nodes, edges));
    const next = future.shift()!;
    applySnapshot(next);
    syncHistoryUi();
  }, [nodes, edges, applySnapshot, syncHistoryUi]);

  return {
    canUndo,
    canRedo,
    pushHistory,
    undo,
    redo,
    applySnapshot,
    resetHistory,
    skipHistoryRef,
  };
}
