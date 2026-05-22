/** 左栏：智能体列 + 会话列（展开）；折叠后仅智能体头像列 */
export const CHAT_AGENT_COLUMN = "11rem";
export const CHAT_SESSION_COLUMN = "13rem";
export const CHAT_LEFT_SIDEBAR_EXPANDED = "24rem";
export const CHAT_LEFT_SIDEBAR_COLLAPSED = "3rem";
export const CHAT_RIGHT_RAIL_EXPANDED = "10rem";
export const CHAT_RIGHT_RAIL_COLLAPSED = "3rem";

export const CHAT_SIDEBAR_STORAGE_KEY = "agents-chat-sidebar";

export type ChatSidebarPrefs = {
  leftCollapsed?: boolean;
  rightCollapsed?: boolean;
};

export function loadChatSidebarPrefs(): ChatSidebarPrefs {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(CHAT_SIDEBAR_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as ChatSidebarPrefs & { leftTab?: string };
    return {
      leftCollapsed: parsed.leftCollapsed,
      rightCollapsed: parsed.rightCollapsed,
    };
  } catch {
    return {};
  }
}

export function saveChatSidebarPrefs(prefs: ChatSidebarPrefs) {
  try {
    localStorage.setItem(CHAT_SIDEBAR_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}
