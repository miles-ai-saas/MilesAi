import { describe, expect, it, vi } from "vitest";
import {
  AGENTS_CHAT_PATH,
  agentsChatUrlMatches,
  buildAgentsChatHref,
  replaceAgentsChat,
} from "@/features/agents/lib/agents-chat-href";

describe("agents-chat-href", () => {
  it("uses trailing slash path", () => {
    expect(AGENTS_CHAT_PATH).toBe("/workbench/agents/chat/");
    expect(buildAgentsChatHref({ agent: "a1" })).toBe("/workbench/agents/chat/?agent=a1");
    expect(buildAgentsChatHref()).toBe("/workbench/agents/chat/");
  });

  it("skips empty params", () => {
    expect(buildAgentsChatHref({ agent: "a1", tab: null, conv: "" })).toBe("/workbench/agents/chat/?agent=a1");
  });

  it("matches current url ignoring trailing slash differences", () => {
    const href = "/workbench/agents/chat/?agent=a1&conv=c1";
    window.history.replaceState({}, "", href);
    expect(agentsChatUrlMatches(href)).toBe(true);
    expect(agentsChatUrlMatches("/workbench/agents/chat?agent=a1&conv=c1")).toBe(true);
    expect(agentsChatUrlMatches("/workbench/agents/chat/?agent=a1&conv=c2")).toBe(false);
  });

  it("replaceAgentsChat uses history.replaceState on same path", () => {
    window.history.replaceState({}, "", "/workbench/agents/chat/");
    const router = { replace: vi.fn(), push: vi.fn() };
    replaceAgentsChat(router, { agent: "a1", conv: "c1" });
    expect(router.replace).not.toHaveBeenCalled();
    expect(window.location.search).toContain("agent=a1");
  });
});
