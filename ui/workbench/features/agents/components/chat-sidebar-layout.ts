/** 对话侧栏折叠偏好 localStorage（链路 §5）。 */

/** 左栏：智能体列 + 会话列（展开）；折叠后仅智能体头像列 */
export const CHAT_AGENT_COLUMN = "11rem";
export const CHAT_AGENT_COLUMN_COMPACT = "3rem";
export const CHAT_SESSION_COLUMN = "13rem";
export const CHAT_LEFT_SIDEBAR_EXPANDED = "24rem";
export const CHAT_LEFT_SIDEBAR_COLLAPSED = "3rem";
/** 调试台右侧轨道略宽，便于 Tab 文案 */
export const CHAT_RIGHT_RAIL_EXPANDED = "11.5rem";
export const CHAT_RIGHT_RAIL_COLLAPSED = "3rem";

export const CHAT_SIDEBAR_STORAGE_KEY = "agents-chat-sidebar";

export type ChatSidebarPrefs = {
  leftCollapsed?: boolean;
  rightCollapsed?: boolean;
  /** 已选智能体时智能体列仅头像（会话列占满剩余宽度） */
  agentsColumnCompact?: boolean;
  /** 隐藏左右侧栏，主区全宽对话 */
  focusMode?: boolean;
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
      agentsColumnCompact: parsed.agentsColumnCompact,
      focusMode: parsed.focusMode,
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
