/**
 * 智能体对话 WebSocket 客户端（工作台）。
 * 协议见 docs/architecture/realtime-transport-design.md
 */

import { getAccessToken } from "@/lib/auth-store";
import type { ChatMediaIn, ChatResponse, GenerativeJobOut } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WS_ENABLED = process.env.NEXT_PUBLIC_AGENT_CHAT_WS !== "false";

export type WsChatSendOptions = {
  query: string;
  media?: ChatMediaIn[];
  toolConfirmed?: boolean;
  pendingToolSlug?: string;
  pendingToolParams?: Record<string, unknown>;
  generativeImageN?: number;
  generativeVideoDuration?: number;
};

export type AgentChatWsCallbacks = {
  onDelta?: (text: string) => void;
  onStep?: (step: Record<string, unknown>) => void;
  onToolConfirmRequired?: (tool: { slug: string; name: string; description?: string | null; params: Record<string, unknown> }) => void;
  onGenerativeJob?: (job: GenerativeJobOut, phase: "queued" | "progress" | "done") => void;
  onError?: (message: string) => void;
  /** 重连后服务端报告环缓缺口（需依赖本地历史 / HTTP） */
  onSyncGap?: () => void;
};

type WsEnvelope = {
  type: string;
  id?: string;
  ts?: string;
  payload: Record<string, unknown>;
};

function apiBaseToWs(base: string): string {
  if (base.startsWith("https://")) return `wss://${base.slice(8)}`;
  if (base.startsWith("http://")) return `ws://${base.slice(7)}`;
  return base;
}

export function isAgentChatWsEnabled(): boolean {
  return WS_ENABLED;
}

export function buildAgentChatWsUrl(
  agentId: string,
  conversationId: string,
  lastEventId?: string | null,
): string {
  const token = getAccessToken();
  const wsBase = apiBaseToWs(API_BASE.replace(/\/$/, ""));
  const q = new URLSearchParams({
    conversation_id: conversationId,
  });
  if (token) q.set("token", token);
  if (lastEventId) q.set("last_event_id", lastEventId);
  return `${wsBase}/agents/${agentId}/chat/ws?${q.toString()}`;
}

export class AgentChatWsClient {
  private ws: WebSocket | null = null;
  private pending: {
    resolve: (res: ChatResponse) => void;
    reject: (err: Error) => void;
  } | null = null;
  private pendingCallbacks: AgentChatWsCallbacks | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;
  /** 最近一条已处理服务端事件 id，供重连续传 */
  private lastEventId: string | null = null;
  private seenEventIds = new Set<string>();
  private static readonly SEEN_CAP = 512;

  constructor(
    private readonly agentId: string,
    private readonly conversationId: string,
  ) {}

  connect(): void {
    if (!WS_ENABLED || typeof WebSocket === "undefined") return;
    this.intentionalClose = false;
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }
    const url = buildAgentChatWsUrl(this.agentId, this.conversationId, this.lastEventId);
    const socket = new WebSocket(url);
    this.ws = socket;
    socket.onopen = () => {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };
    socket.onmessage = (ev) => this.handleMessage(ev.data);
    socket.onerror = () => {
      // 断线续传依赖 onclose 重连；此处不立刻 reject pending，避免吞掉随后重放的 chat.done
    };
    socket.onclose = () => {
      this.ws = null;
      if (!this.intentionalClose && WS_ENABLED) {
        this.reconnectTimer = setTimeout(() => this.connect(), 1500);
      }
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    if (this.pending) {
      this.pending.reject(new Error("连接已关闭"));
      this.pending = null;
      this.pendingCallbacks = null;
    }
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  sendChat(opts: WsChatSendOptions, callbacks: AgentChatWsCallbacks = {}): Promise<ChatResponse> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("WebSocket 未连接"));
    }
    if (this.pending) {
      return Promise.reject(new Error("上一条消息仍在处理中"));
    }
    this.pendingCallbacks = null;
    return new Promise((resolve, reject) => {
      this.pendingCallbacks = callbacks;
      this.pending = { resolve, reject };
      const payload: Record<string, unknown> = {
        query: opts.query,
      };
      if (opts.media?.length) payload.media = opts.media;
      if (opts.generativeImageN != null) payload.generative_image_n = opts.generativeImageN;
      if (opts.generativeVideoDuration != null) payload.generative_video_duration = opts.generativeVideoDuration;
      if (opts.toolConfirmed) {
        payload.tool_confirmed = true;
        payload.pending_tool_slug = opts.pendingToolSlug;
        payload.pending_tool_params = opts.pendingToolParams ?? {};
      }
      this.ws!.send(
        JSON.stringify({
          type: opts.toolConfirmed ? "tool.confirm" : "chat.send",
          payload,
        }),
      );
    });
  }

  cancelGenerativeJob(jobId: string): void {
    if (!this.connected) return;
    this.ws!.send(
      JSON.stringify({
        type: "generative_job.cancel",
        payload: { job_id: jobId },
      }),
    );
  }

  private rememberEventId(id: string | undefined) {
    if (!id) return;
    this.lastEventId = id;
    this.seenEventIds.add(id);
    if (this.seenEventIds.size > AgentChatWsClient.SEEN_CAP) {
      const first = this.seenEventIds.values().next().value;
      if (first) this.seenEventIds.delete(first);
    }
  }

  private handleMessage(raw: string) {
    let frame: WsEnvelope;
    try {
      frame = JSON.parse(raw) as WsEnvelope;
    } catch {
      return;
    }
    const { type, payload, id } = frame;
    if (id && this.seenEventIds.has(id)) {
      return;
    }
    this.rememberEventId(id);

    const cb = this.pendingCallbacks;

    switch (type) {
      case "chat.sync": {
        if (payload.gap === true) {
          cb?.onSyncGap?.();
        }
        break;
      }
      case "chat.delta": {
        const text = String(payload.text ?? "");
        cb?.onDelta?.(text);
        break;
      }
      case "chat.step":
        cb?.onStep?.(payload as Record<string, unknown>);
        break;
      case "tool.confirm_required":
        cb?.onToolConfirmRequired?.({
          slug: String(payload.slug ?? ""),
          name: String(payload.name ?? payload.slug ?? ""),
          description: (payload.description as string) ?? null,
          params: (payload.params as Record<string, unknown>) ?? {},
        });
        break;
      case "generative_job.queued":
      case "generative_job.progress":
        cb?.onGenerativeJob?.(payload as unknown as GenerativeJobOut, "progress");
        break;
      case "generative_job.done":
        cb?.onGenerativeJob?.((payload.job as GenerativeJobOut) ?? (payload as unknown as GenerativeJobOut), "done");
        break;
      case "chat.done": {
        const res = payload as unknown as ChatResponse;
        this.pending?.resolve(res);
        this.pending = null;
        break;
      }
      case "chat.error": {
        const msg = String(payload.message ?? "对话失败");
        cb?.onError?.(msg);
        this.pending?.reject(new Error(msg));
        this.pending = null;
        this.pendingCallbacks = null;
        break;
      }
      default:
        break;
    }
  }
}
