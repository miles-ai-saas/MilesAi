"use client";

/** 单轮回复 steps 时间线（链路 §5，`agent-steps` 解析）。 */
import { useMemo, useState } from "react";
import {
  buildStepsSummary,
  formatToolParams,
  parseAgentSteps,
  type AgentStepStatus,
  type ParsedAgentStep,
} from "@/lib/agent-steps";
import {
  generativeToolConfirmButtonLabel,
  generativeToolConfirmNote,
} from "@/lib/generative-tool-ui";
import type { PendingToolCall } from "@/lib/types";

type Props = {
  steps: Record<string, unknown>[];
  pendingTool?: PendingToolCall | null;
  onConfirmTool?: () => void;
  confirmToolDisabled?: boolean;
};

const STATUS_DOT: Record<AgentStepStatus, string> = {
  success: "bg-emerald-500 ring-emerald-100",
  pending: "bg-amber-500 ring-amber-100 animate-pulse",
  error: "bg-red-500 ring-red-100",
  warning: "bg-amber-500 ring-amber-100",
  skipped: "bg-ink-faint ring-line",
  neutral: "bg-brand ring-brand-light",
};

const STATUS_LABEL: Record<AgentStepStatus, string> = {
  success: "完成",
  pending: "待确认",
  error: "失败",
  warning: "注意",
  skipped: "跳过",
  neutral: "",
};

export function AgentExecutionTimeline({
  steps,
  pendingTool,
  onConfirmTool,
  confirmToolDisabled,
}: Props) {
  const parsed = useMemo(() => parseAgentSteps(steps), [steps]);
  const summary = useMemo(() => buildStepsSummary(parsed), [parsed]);
  const [expanded, setExpanded] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  if (!parsed.length) return null;

  return (
    <section className="mb-3 rounded-lg border border-line-soft bg-surface-subtle/80">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition hover:bg-surface-muted/60"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <Chevron expanded={expanded} />
        <span className="font-medium text-ink">执行步骤</span>
        <span className="min-w-0 flex-1 truncate text-ink-muted">{summary}</span>
        <span className="shrink-0 rounded-full bg-surface px-2 py-0.5 text-[10px] text-ink-muted">
          {parsed.length}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-line-soft px-3 py-3">
          <ol className="space-y-0">
            {parsed.map((step, index) => (
              <StepRow
                key={step.key}
                step={step}
                isLast={index === parsed.length - 1}
                pendingTool={pendingTool}
                onConfirmTool={onConfirmTool}
                confirmToolDisabled={confirmToolDisabled}
              />
            ))}
          </ol>

          <div className="mt-3 border-t border-line-soft pt-2">
            <button
              type="button"
              className="text-[11px] text-ink-muted hover:text-brand"
              onClick={() => setShowRaw((v) => !v)}
            >
              {showRaw ? "隐藏原始数据" : "查看原始数据"}
            </button>
            {showRaw && (
              <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-surface p-2 font-mono text-[10px] text-ink-muted">
                {JSON.stringify(steps, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function StepRow({
  step,
  isLast,
  pendingTool,
  onConfirmTool,
  confirmToolDisabled,
}: {
  step: ParsedAgentStep;
  isLast: boolean;
  pendingTool?: PendingToolCall | null;
  onConfirmTool?: () => void;
  confirmToolDisabled?: boolean;
}) {
  const statusLabel = STATUS_LABEL[step.status];
  const showConfirm =
    step.type === "tool_confirmation_required" &&
    pendingTool &&
    (!step.raw.slug || step.raw.slug === pendingTool.slug);
  const confirmNote = showConfirm && pendingTool
    ? generativeToolConfirmNote(pendingTool.slug, pendingTool.params)
    : null;

  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      {!isLast && (
        <span
          className="absolute left-[7px] top-4 h-[calc(100%-4px)] w-px bg-line"
          aria-hidden
        />
      )}
      <span
        className={`relative z-[1] mt-1 h-3.5 w-3.5 shrink-0 rounded-full ring-4 ${STATUS_DOT[step.status]}`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="text-xs font-medium text-ink">{step.title}</span>
          {statusLabel ? (
            <span
              className={`text-[10px] ${
                step.status === "error"
                  ? "text-red-600"
                  : step.status === "pending"
                    ? "text-amber-700"
                    : step.status === "warning"
                      ? "text-amber-700"
                      : "text-ink-muted"
              }`}
            >
              {statusLabel}
            </span>
          ) : null}
        </div>
        {step.detail ? (
          <p className="mt-0.5 text-[11px] leading-relaxed text-ink-muted">{step.detail}</p>
        ) : null}

        {showConfirm && pendingTool ? (
          <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50/80 p-2.5">
            <p className="text-[11px] font-medium text-amber-900">{pendingTool.name}</p>
            {pendingTool.description ? (
              <p className="mt-0.5 text-[11px] text-amber-800/80">{pendingTool.description}</p>
            ) : null}
            {confirmNote ? (
              <p className="mt-1.5 text-[11px] leading-relaxed text-amber-900/90">
                {confirmNote}
              </p>
            ) : null}
            <p className="mt-1.5 font-mono text-[10px] text-amber-900/90">
              {formatToolParams(pendingTool.params)}
            </p>
            {onConfirmTool ? (
              <button
                type="button"
                className="btn-primary mt-2 px-3 py-1 text-xs"
                disabled={confirmToolDisabled}
                onClick={onConfirmTool}
              >
                {generativeToolConfirmButtonLabel(pendingTool.slug)}
              </button>
            ) : null}
          </div>
        ) : null}

        {step.type === "grade" && step.raw.reason ? (
          <p className="mt-1 text-[10px] text-ink-faint">{String(step.raw.reason)}</p>
        ) : null}
      </div>
    </li>
  );
}

function Chevron({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`h-3.5 w-3.5 shrink-0 text-ink-muted transition ${expanded ? "rotate-90" : ""}`}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden
    >
      <path
        d="M6 4l4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** 请求进行中的占位时间线 */
export function AgentExecutionSkeleton() {
  return (
    <div className="mb-3 rounded-lg border border-line-soft bg-surface-subtle/80 px-3 py-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-ink-muted">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-brand" />
        正在执行…
      </div>
      <div className="space-y-3 pl-1">
        {[0, 1].map((i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="h-3 w-3 animate-pulse rounded-full bg-line" />
            <span
              className="h-2.5 animate-pulse rounded bg-line"
              style={{ width: `${55 + i * 15}%` }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
