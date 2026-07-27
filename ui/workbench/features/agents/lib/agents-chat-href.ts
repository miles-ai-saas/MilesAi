/** 对话页路由（静态导出 trailingSlash: true，须带尾斜杠）。 */

import { ensureActiveSession } from "@/features/agents/lib/chat-sessions";

export const AGENTS_CHAT_PATH = "/workbench/agents/chat/";

export function buildAgentsChatHref(params?: URLSearchParams | Record<string, string | null | undefined>): string {
  let q: URLSearchParams;
  if (!params) {
    q = new URLSearchParams();
  } else if (params instanceof URLSearchParams) {
    q = params;
  } else {
    q = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value != null && value !== "") q.set(key, value);
    }
  }
  const qs = q.toString();
  return qs ? `${AGENTS_CHAT_PATH}?${qs}` : AGENTS_CHAT_PATH;
}

function normalizePathname(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) return pathname.slice(0, -1);
  return pathname || "/";
}

/** 当前浏览器地址与目标 href 的 path + query 是否一致（避免 replace 死循环）。 */
export function agentsChatUrlMatches(href: string): boolean {
  if (typeof window === "undefined") return false;
  const next = new URL(href, window.location.origin);
  if (normalizePathname(window.location.pathname) !== normalizePathname(next.pathname)) {
    return false;
  }
  const cur = new URLSearchParams(window.location.search);
  const want = new URLSearchParams(next.search);
  const keys = new Set([...cur.keys(), ...want.keys()]);
  for (const key of keys) {
    if ((cur.get(key) ?? "") !== (want.get(key) ?? "")) return false;
  }
  return true;
}

/**
 * 更新对话页 URL。
 * 只使用 history.replaceState，禁止 router.replace：
 * 静态导出下 useSearchParams + Suspense 会因 router 改 query 整页 remount，
 * 进而重复 listAgents / 重建会话，形成请求循环。
 */
export function replaceAgentsChat(
  _router: { replace: (href: string) => void },
  params?: URLSearchParams | Record<string, string | null | undefined>,
): void {
  if (typeof window === "undefined") return;
  const href = buildAgentsChatHref(params);
  if (agentsChatUrlMatches(href)) return;
  window.history.replaceState(window.history.state, "", href);
}

export function pushAgentsChat(
  router: { push: (href: string) => void },
  params?: URLSearchParams | Record<string, string | null | undefined>,
): void {
  const href = buildAgentsChatHref(params);
  if (agentsChatUrlMatches(href)) return;
  router.push(href);
}

/**
 * 从智能体列表进对话：先解析本地活跃会话，URL 立刻带上 agent+conv，
 * 避免进页后才 replaceState（失败/卡住时地址栏会停在裸 /chat/）。
 */
export function pushAgentsChatForAgent(
  router: { push: (href: string) => void },
  agentId: string,
  extra?: Record<string, string | null | undefined>,
): void {
  if (!agentId) {
    pushAgentsChat(router);
    return;
  }
  const session = ensureActiveSession(agentId);
  pushAgentsChat(router, { agent: agentId, conv: session.id, ...extra });
}
