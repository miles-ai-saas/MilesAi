"use client";

/** 对话消息区（链路 §5）：渲染消息 + `AgentExecutionTimeline`（steps）。 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AgentExecutionSkeleton, AgentExecutionTimeline } from "@/features/agents/components/AgentExecutionTimeline";
import { ChatGenerativeCard } from "@/features/agents/components/ChatGenerativeCard";
import { ImagePreviewDialog } from "@/features/agents/components/ImagePreviewDialog";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";
import { turnIndexForMessageIndex } from "@/features/agents/lib/agent-trace";
import { effectiveArtifactStatus } from "@/lib/generative-jobs";
import { api } from "@/lib/api";
import type { GenerativeJobOut, PendingToolCall } from "@/lib/types";
import type { ReactNode } from "react";

type Props = {
  messages: ChatMessage[];
  chatting: boolean;
  pendingTool?: PendingToolCall | null;
  onConfirmPendingTool?: () => void;
  confirmPendingToolDisabled?: boolean;
  /** 覆盖默认「思考中…」 */
  chattingStatusLabel?: string | null;
  /** 异步生成进度（显示在最后一条助手消息下方或流式骨架下方；有进行中卡片时由 Thread 隐藏） */
  generativeStatus?: ReactNode;
  onCancelGenerativeJob?: (jobId: string) => void;
  onGenerativeJobRetried?: (job: GenerativeJobOut) => void;
  /** 点击助手消息打开 Trace（传入轮次下标） */
  onOpenTraceTurn?: (turnIndex: number) => void;
  /** 加载更早的消息 */
  onLoadMore?: () => void;
  loadingMore?: boolean;
  hasMore?: boolean;
  /** 会话 id：切换时复位「向上加载」武装，避免多消息会话一进页就刷接口 */
  conversationId?: string;
  /** 是否已选智能体（空态文案） */
  agentSelected?: boolean;
  /** 滚动容器 ref，用于 IntersectionObserver */
  scrollContainerRef?: React.RefObject<HTMLDivElement | null>;
};

function hasPendingConfirmationStep(steps?: Record<string, unknown>[]) {
  return steps?.some((s) => s.type === "tool_confirmation_required") ?? false;
}

/** 用户上传图片的可靠预览：preview_url 是 blob URL（刷新后必然失效），
 *  检测到 blob 协议时直接走 API fetch，不再依赖 onError 回退。 */
function ChatMediaImage({ attachmentId, previewUrl, filename }: { attachmentId: string; previewUrl?: string; filename?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const triedRef = useRef(false);

  const fetchFromApi = useCallback(async () => {
    if (triedRef.current) return;
    triedRef.current = true;
    let url: string | null = null;
    try {
      url = await api.fetchAttachmentPreviewUrl(attachmentId);
    } catch {
      // 加载失败，显示占位
    }
    if (url) setSrc(url);
    return url;
  }, [attachmentId]);

  useEffect(() => {
    // preview_url 是 blob: URL，刷新后必然失效——直接 API fetch
    const isBlobUrl = previewUrl && previewUrl.startsWith("blob:");
    if (!previewUrl || isBlobUrl) {
      void fetchFromApi();
      return;
    }
    // 非 blob URL（如持久化的签名 URL），直接使用
    setSrc(previewUrl);
  }, [previewUrl, fetchFromApi]);

  // 卸载时清理 blob URL
  useEffect(() => {
    return () => {
      if (src) URL.revokeObjectURL(src);
    };
  }, [src]);

  if (!src) {
    return <div className="flex h-24 w-24 items-center justify-center rounded-lg bg-white/20 text-xs text-white/50">加载中…</div>;
  }

  return (
    <>
      <img
        key={attachmentId}
        src={src}
        alt={filename ?? "附图"}
        className="max-h-32 max-w-[140px] cursor-pointer rounded-lg object-cover transition-opacity hover:opacity-80"
        onClick={() => setPreviewOpen(true)}
        title="点击查看大图"
      />
      <ImagePreviewDialog open={previewOpen} src={src} alt={filename ?? "附图"} onClose={() => setPreviewOpen(false)} />
    </>
  );
}

export function ChatMessageThread({
  messages,
  chatting,
  pendingTool,
  onConfirmPendingTool,
  confirmPendingToolDisabled,
  chattingStatusLabel,
  generativeStatus,
  onCancelGenerativeJob,
  onGenerativeJobRetried,
  onOpenTraceTurn,
  onLoadMore,
  loadingMore,
  hasMore,
  conversationId,
  agentSelected,
  scrollContainerRef,
}: Props) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const prevScrollHeightRef = useRef(0);
  /** 仅在用户真正向上滚过之后才自动 loadMore，避免内容不足一屏时哨兵常驻视口刷接口 */
  const loadMoreArmedRef = useRef(false);
  const loadingMoreRef = useRef(!!loadingMore);
  loadingMoreRef.current = !!loadingMore;

  useEffect(() => {
    loadMoreArmedRef.current = false;
  }, [conversationId]);

  useEffect(() => {
    const root = scrollContainerRef?.current;
    if (!root || !hasMore) return;
    const onScroll = () => {
      const distBottom = root.scrollHeight - root.scrollTop - root.clientHeight;
      if (distBottom < 48) {
        loadMoreArmedRef.current = false;
      } else if (root.scrollTop < 120) {
        loadMoreArmedRef.current = true;
      }
    };
    root.addEventListener("scroll", onScroll, { passive: true });
    return () => root.removeEventListener("scroll", onScroll);
  }, [hasMore, scrollContainerRef, conversationId]);

  // IntersectionObserver：顶部哨兵进入视口时触发加载更早消息
  useEffect(() => {
    const sentinel = sentinelRef.current;
    const root = scrollContainerRef?.current ?? null;
    if (!sentinel || !onLoadMore || !hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return;
        if (!loadMoreArmedRef.current || loadingMoreRef.current) return;
        onLoadMore();
      },
      { root, rootMargin: "64px", threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, onLoadMore, scrollContainerRef, conversationId]);

  // 加载更早消息后保持滚动位置（防止内容向上跳）
  useEffect(() => {
    const container = scrollContainerRef?.current;
    if (!container || prevScrollHeightRef.current === 0) return;
    const newHeight = container.scrollHeight;
    const delta = newHeight - prevScrollHeightRef.current;
    if (delta > 0) {
      container.scrollTop += delta;
    }
  }, [messages.length, scrollContainerRef]);

  // 记录 messages 变化前的 scrollHeight
  useEffect(() => {
    const container = scrollContainerRef?.current;
    if (container) {
      prevScrollHeightRef.current = container.scrollHeight;
    }
  }, [messages.length, scrollContainerRef]);

  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();

  const lastAssistantHasInFlight =
    lastAssistantIndex >= 0 &&
    (messages[lastAssistantIndex].artifacts?.some((a) => {
      const s = effectiveArtifactStatus(a);
      return s === "pending" || s === "running";
    }) ??
      false);

  const showGenerativeBanner = Boolean(generativeStatus) && !lastAssistantHasInFlight;

  if (messages.length === 0 && !chatting) {
    return (
      <div className="flex h-full min-h-[200px] flex-col items-center justify-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-light">
          <span className="text-2xl text-brand">◇</span>
        </div>
        {conversationId ? (
          <>
            <p className="text-sm text-ink-muted">输入问题开始对话</p>
            <p className="mt-1 text-xs text-ink-faint">支持直连、RAG、流程与多模态；助手卡片可点「Trace」查看执行步骤</p>
          </>
        ) : agentSelected ? (
          <>
            <p className="text-sm text-ink-muted">请从左侧选择会话，或新建对话</p>
            <p className="mt-1 text-xs text-ink-faint">选定会话后加载消息，地址栏会带上会话 ID</p>
          </>
        ) : (
          <>
            <p className="text-sm text-ink-muted">请从左侧选择智能体</p>
            <p className="mt-1 text-xs text-ink-faint">也可从智能体列表点击「对话」进入</p>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 顶部哨兵：触发加载更早消息 */}
      {hasMore !== false ? (
        <div ref={sentinelRef} className="flex items-center justify-center py-2">
          {loadingMore ? (
            <span className="text-xs text-ink-muted">加载更早的消息…</span>
          ) : (
            <span className="text-xs text-ink-faint">向上滚动加载更多</span>
          )}
        </div>
      ) : messages.length > 0 ? (
        <div className="flex items-center justify-center py-2">
          <span className="text-xs text-ink-faint">— 已显示全部消息 —</span>
        </div>
      ) : null}
      {messages.map((msg, i) => {
        const traceTurn = msg.role === "assistant" ? turnIndexForMessageIndex(messages, i) : null;
        const showTraceBtn = traceTurn != null && onOpenTraceTurn && ((msg.steps?.length ?? 0) > 0 || Boolean(msg.traceId));

        return (
          <div key={`${i}-${msg.role}`}>
            {msg.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-2.5 text-sm text-brand-foreground">
                  {msg.media && msg.media.length > 0 && (
                    <div className="mb-2 flex flex-wrap justify-end gap-2">
                      {msg.media.map((m) => (
                        <ChatMediaImage
                          key={m.attachment_id}
                          attachmentId={m.attachment_id}
                          previewUrl={m.preview_url}
                          filename={m.filename}
                        />
                      ))}
                    </div>
                  )}
                  {msg.content ? <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p> : null}
                </div>
              </div>
            ) : (
              <div className="card p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-brand">助手</p>
                  {showTraceBtn ? (
                    <button type="button" className="btn-sm-ghost text-[10px] text-ink-muted" onClick={() => onOpenTraceTurn(traceTurn)}>
                      Trace
                    </button>
                  ) : null}
                </div>
                {msg.steps && msg.steps.length > 0 && (
                  <AgentExecutionTimeline
                    steps={msg.steps}
                    pendingTool={i === lastAssistantIndex && pendingTool && hasPendingConfirmationStep(msg.steps) ? pendingTool : null}
                    onConfirmTool={i === lastAssistantIndex && pendingTool && hasPendingConfirmationStep(msg.steps) ? onConfirmPendingTool : undefined}
                    confirmToolDisabled={confirmPendingToolDisabled}
                  />
                )}
                {msg.artifacts && msg.artifacts.length > 0 && (
                  <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                    {msg.artifacts.map((a, idx) => (
                      <ChatGenerativeCard
                        key={a.job_id ?? a.attachment_id ?? `art-${idx}`}
                        artifact={a}
                        onCancel={onCancelGenerativeJob}
                        onRetried={onGenerativeJobRetried}
                      />
                    ))}
                  </div>
                )}
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{msg.content}</div>
                {i === lastAssistantIndex && showGenerativeBanner ? <div className="mt-3">{generativeStatus}</div> : null}
              </div>
            )}
          </div>
        );
      })}
      {chatting && (
        <div className="card p-4">
          <p className="mb-2 text-xs font-medium text-brand">助手</p>
          <AgentExecutionSkeleton />
          <p className="mt-1 text-sm text-ink-muted">{chattingStatusLabel ?? "思考中…"}</p>
          {showGenerativeBanner ? <div className="mt-3">{generativeStatus}</div> : null}
        </div>
      )}
      {!chatting && lastAssistantIndex < 0 && showGenerativeBanner ? <div>{generativeStatus}</div> : null}
    </div>
  );
}
