"use client";

/** 流程编辑页顶栏（链路 §6）。 */
import Link from "next/link";

interface FlowEditHeaderProps {
  flowName: string;
  flowId: string;
  currentVersion: number;
  busy: boolean;
  msg: string;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
  flowDescription?: string | null;
  onEditMeta?: () => void;
  onSave: () => void;
  onPublish: () => void;
  onHistory: () => void;
  onCompile: () => void;
  onRun: () => void;
}

function FullscreenIcon({ exit }: { exit?: boolean }) {
  if (exit) {
    return (
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Divider() {
  return <span className="mx-1 hidden h-5 w-px bg-line sm:block" aria-hidden />;
}

export function FlowEditHeader({
  flowName,
  flowId,
  currentVersion,
  busy,
  msg,
  flowDescription,
  onEditMeta,
  onSave,
  onPublish,
  onHistory,
  isFullscreen,
  onToggleFullscreen,
  onCompile,
  onRun,
}: FlowEditHeaderProps) {
  return (
    <header className="flex shrink-0 flex-col gap-2 border-b border-line bg-surface px-3 py-2 sm:px-4">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <Link
              href="/workbench/flows"
              className="btn-sm-ghost shrink-0 !px-2 text-ink-muted"
              title="返回流程列表"
            >
              ← 列表
            </Link>
            <h1 className="truncate text-base font-semibold text-ink">
              {flowName || `流程 ${flowId.slice(0, 8)}`}
            </h1>
            {currentVersion > 0 && (
              <span className="shrink-0 rounded-md bg-brand-light px-2 py-0.5 text-xs font-medium text-brand">
                v{currentVersion}
              </span>
            )}
            {onEditMeta && (
              <button
                type="button"
                className="btn-sm-ghost shrink-0 text-xs text-ink-muted"
                disabled={busy}
                onClick={onEditMeta}
                title="编辑名称与描述"
              >
                基本信息
              </button>
            )}
          </div>
          {flowDescription?.trim() && (
            <p className="mt-0.5 truncate pl-10 text-xs text-ink-muted">{flowDescription.trim()}</p>
          )}
        </div>
        {msg && (
          <span className="shrink-0 text-sm text-emerald-600" role="status">
            {msg}
          </span>
        )}
        {onToggleFullscreen && (
          <button
            type="button"
            className="btn-sm-ghost shrink-0 !px-2"
            onClick={onToggleFullscreen}
            title={isFullscreen ? "退出全屏 (Esc)" : "全屏编辑"}
            aria-label={isFullscreen ? "退出全屏" : "全屏编辑"}
          >
            <FullscreenIcon exit={isFullscreen} />
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1">
        <span className="mr-1 hidden text-[10px] font-medium uppercase tracking-wide text-ink-faint sm:inline">
          画布
        </span>
        <button
          type="button"
          className="btn-sm-outline"
          disabled={busy}
          onClick={onSave}
        >
          保存
        </button>
        <button
          type="button"
          className="btn-sm-primary"
          disabled={busy}
          onClick={onPublish}
        >
          发布
        </button>
        <Divider />
        <button
          type="button"
          className="btn-sm-outline"
          disabled={busy || currentVersion === 0}
          onClick={onHistory}
        >
          版本历史
        </button>
        <Divider />
        <span className="mr-1 hidden text-[10px] font-medium uppercase tracking-wide text-ink-faint sm:inline">
          校验
        </span>
        <button
          type="button"
          className="btn-sm-outline"
          disabled={busy}
          onClick={onCompile}
        >
          编译检查
        </button>
        <button
          type="button"
          className="btn-sm-primary"
          disabled={busy}
          onClick={onRun}
        >
          调试运行
        </button>
      </div>
    </header>
  );
}
