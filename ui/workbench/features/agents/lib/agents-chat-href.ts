/** 对话页路由（静态导出 trailingSlash: true，须带尾斜杠）。 */

export const AGENTS_CHAT_PATH = "/workbench/agents/chat/";

export type AgentsChatQuery = {
  agent?: string | null;
  conv?: string | null;
  tab?: string | null;
  prompt?: string | null;
};

export function buildAgentsChatHref(params?: AgentsChatQuery | URLSearchParams): string {
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
 * 更新对话页 query。
 * 使用 history.replaceState(null, …)：让 Next 同步 useSearchParams，又避免 router.replace 整页 remount 循环。
 * 切勿传入带 `__NA` 的 history.state（会被当成内部调用而跳过路由同步）。
 */
export function replaceAgentsChat(params?: AgentsChatQuery | URLSearchParams): void {
  if (typeof window === "undefined") return;
  const href = buildAgentsChatHref(params);
  if (agentsChatUrlMatches(href)) return;
  window.history.replaceState(null, "", href);
}

export function pushAgentsChat(router: { push: (href: string) => void }, params?: AgentsChatQuery | URLSearchParams): void {
  const href = buildAgentsChatHref(params);
  if (agentsChatUrlMatches(href)) return;
  router.push(href);
}

/** 从智能体列表进对话：只带 agent。 */
export function pushAgentsChatForAgent(router: { push: (href: string) => void }, agentId: string, extra?: Omit<AgentsChatQuery, "agent" | "conv">): void {
  if (!agentId) {
    pushAgentsChat(router);
    return;
  }
  pushAgentsChat(router, { ...extra, agent: agentId });
}
