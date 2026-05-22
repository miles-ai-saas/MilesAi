export const CHAT_LEFT_SIDEBAR_EXPANDED = "18rem";
export const CHAT_LEFT_SIDEBAR_COLLAPSED = "3rem";
export const CHAT_RIGHT_RAIL_EXPANDED = "10rem";
export const CHAT_RIGHT_RAIL_COLLAPSED = "3rem";

export const CHAT_SIDEBAR_STORAGE_KEY = "agents-chat-sidebar";

export type ChatSidebarPrefs = {
  leftCollapsed?: boolean;
  rightCollapsed?: boolean;
  leftTab?: "agents" | "sessions";
};

export function loadChatSidebarPrefs(): ChatSidebarPrefs {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(CHAT_SIDEBAR_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatSidebarPrefs) : {};
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
