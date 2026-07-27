/** 对话页路由（静态导出 trailingSlash: true，须带尾斜杠）。 */

export const AGENTS_CHAT_PATH = "/workbench/agents/chat/";

/** 最近一次打开的智能体（入口只恢复 agent；conv 等用户选会话后再写入 URL）。 */
const LAST_CHAT_KEY = "agents-chat-last-v1";

export type LastAgentsChat = { agentId: string; convId?: string };

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

export function rememberLastAgentsChat(agentId: string, convId?: string | null): void {
  if (typeof window === "undefined" || !agentId) return;
  try {
    const payload: LastAgentsChat = { agentId };
    if (convId) payload.convId = convId;
    localStorage.setItem(LAST_CHAT_KEY, JSON.stringify(payload));
  } catch {
    /* ignore quota */
  }
}

export function loadLastAgentsChat(): LastAgentsChat | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LAST_CHAT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LastAgentsChat;
    if (!parsed?.agentId) return null;
    return {
      agentId: String(parsed.agentId),
      ...(parsed.convId ? { convId: String(parsed.convId) } : {}),
    };
  } catch {
    return null;
  }
}

/**
 * 导航/快捷入口：只恢复最近 agent，不带 conv。
 * 进页后先拉会话列表，用户点选会话后再写入 conv。
 */
export function resolveAgentsChatEntryHref(
  extra?: Record<string, string | null | undefined>,
): string {
  const last = loadLastAgentsChat();
  if (last?.agentId) {
    return buildAgentsChatHref({ agent: last.agentId, ...extra });
  }
  return buildAgentsChatHref(extra);
}

export function isAgentsChatNavHref(href: string): boolean {
  const path = href.split("?")[0] ?? href;
  return normalizePathname(path) === normalizePathname(AGENTS_CHAT_PATH);
}

/**
 * 更新对话页 URL。
 *
 * 必须让 Next App Router 感知 query 变化：
 * - 若传入带 `__NA` 的 `history.state`，Next 的 replaceState patch 会当成内部调用，
 *   跳过 ACTION_RESTORE，地址栏参数随后会被 canonical URL 冲掉。
 * - 传入 `null` 时会走 copyNextJsInternalHistoryState + ACTION_RESTORE，
 *   useSearchParams 与地址栏保持一致。
 *
 * 禁止 router.replace：静态导出下 Suspense+useSearchParams 会因改 query 整页 remount；
 * 由 history.replaceState 触发的单次 RESTORE 可接受，且须用 agentsChatUrlMatches 防抖。
 */
export function replaceAgentsChat(
  _router: { replace: (href: string) => void },
  params?: URLSearchParams | Record<string, string | null | undefined>,
): void {
  if (typeof window === "undefined") return;
  const href = buildAgentsChatHref(params);
  if (agentsChatUrlMatches(href)) return;
  const agent = params instanceof URLSearchParams ? params.get("agent") : params?.agent;
  const conv = params instanceof URLSearchParams ? params.get("conv") : params?.conv;
  if (agent) rememberLastAgentsChat(agent, conv || null);
  // 故意传 null，不要传 window.history.state（见上方注释）
  window.history.replaceState(null, "", href);
}

export function pushAgentsChat(
  router: { push: (href: string) => void },
  params?: URLSearchParams | Record<string, string | null | undefined>,
): void {
  const href = buildAgentsChatHref(params);
  if (agentsChatUrlMatches(href)) return;
  const agent = params instanceof URLSearchParams ? params.get("agent") : params?.agent;
  const conv = params instanceof URLSearchParams ? params.get("conv") : params?.conv;
  if (agent) rememberLastAgentsChat(agent, conv || null);
  router.push(href);
}

/**
 * 从智能体列表进对话：URL 只带 agent，进页后加载会话列表；
 * 用户选择（或新建）会话后再写入 conv 并拉详情。
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
  pushAgentsChat(router, { agent: agentId, ...extra, conv: null });
}
