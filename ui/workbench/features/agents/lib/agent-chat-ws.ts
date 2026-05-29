/**
 * 智能体对话 WebSocket 客户端（工作台）。
 * 协议见 docs/architecture/realtime-transport-design.md
 */

import { getAccessToken } from "./auth-store";
import type { ChatArtifact, ChatMediaIn, ChatResponse, GenerativeJobOut } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WS_ENABLED = process.env.NEXT_PUBLIC_AGENT_CHAT_WS !== "false";

export type WsChatSendOptions = {
  query: string;
  media?: ChatMediaIn[];
  toolConfirmed?: boolean;
  pendingToolSlug?: string;
  pendingToolParams?: Record<string, unknown>;
};

export type AgentChatWsCallbacks = {
  onDelta?: (text: string) => void;
  onStep?: (step: Record<string, unknown>) => void;
  onToolConfirmRequired?: (tool: { slug: string; name: string; description?: string | null; params: Record<string, unknown> }) => void;
  onGenerativeJob?: (job: GenerativeJobOut, phase: "queued" | "progress" | "done") => void;
  onError?: (message: string) => void;
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

export function buildAgentChatWsUrl(agentId: string, conversationId: string): string {
  const token = getAccessToken();
  const wsBase = apiBaseToWs(API_BASE.replace(/\/$/, ""));
  const q = new URLSearchParams({
    conversation_id: conversationId,
  });
  if (token) q.set("token", token);
  return `${wsBase}/agents/${agentId}/chat/ws?${q.toString()}`;
}

export class AgentChatWsClient {
  private ws: WebSocket | null = null;
  private pending: {
    resolve: (res: ChatResponse) => void;
    reject: (err: Error) => void;
    callbacks: AgentChatWsCallbacks;
  } | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

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
    const url = buildAgentChatWsUrl(this.agentId, this.conversationId);
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
      if (this.pending) {
        this.pending.reject(new Error("WebSocket 连接异常"));
        this.pending = null;
      }
    };
    socket.onclose = () => {
      this.ws = null;
      if (!this.intentionalClose && WS_ENABLED) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
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
    return new Promise((resolve, reject) => {
      this.pending = { resolve, reject, callbacks };
      const payload: Record<string, unknown> = {
        query: opts.query,
      };
      if (opts.media?.length) payload.media = opts.media;
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

  private handleMessage(raw: string) {
    let frame: WsEnvelope;
    try {
      frame = JSON.parse(raw) as WsEnvelope;
    } catch {
      return;
    }
    const { type, payload } = frame;
    const cb = this.pending?.callbacks;

    switch (type) {
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
        break;
      }
      default:
        break;
    }
  }
}
