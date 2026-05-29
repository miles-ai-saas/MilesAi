import type { FlowCompileErrorDetail } from "@/lib/flow-run-format";
import type { FlowRunArtifact } from "@/lib/flow-run-artifacts";
import type { KnowledgeBase } from "@/lib/types";

export interface FlowRunState {
  output: string;
  steps: Record<string, unknown>[];
  compileInfo?: string;
  compileErrorDetails?: FlowCompileErrorDetail[];
  error?: string;
}

export type FlowRunPendingMedia = {
  attachment_id: string;
  filename?: string;
  local_preview: string;
};

export type FlowRunPanelProps = {
  kbs: KnowledgeBase[];
  selectedKbIds: string[];
  onKbIdsChange: (ids: string[]) => void;
  query: string;
  onQueryChange: (q: string) => void;
  runState: FlowRunState | null;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onSelectCompileNode?: (nodeId: string) => void;
  onRun?: () => void;
  busy?: boolean;
  runBusyLabel?: string;
  generativeHint?: string | null;
  generativePollMsg?: string | null;
  generativeProgressPercent?: number | null;
  onCancelGenerativeJobs?: () => void;
  canCancelGenerative?: boolean;
  extraArtifacts?: FlowRunArtifact[];
  pendingMedia?: FlowRunPendingMedia[];
  onPendingMediaChange?: (items: FlowRunPendingMedia[]) => void;
};
