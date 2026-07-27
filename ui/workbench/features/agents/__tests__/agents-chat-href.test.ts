import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  AGENTS_CHAT_PATH,
  agentsChatUrlMatches,
  buildAgentsChatHref,
  isAgentsChatNavHref,
  loadLastAgentsChat,
  rememberLastAgentsChat,
  replaceAgentsChat,
  resolveAgentsChatEntryHref,
} from "@/features/agents/lib/agents-chat-href";

describe("agents-chat-href", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState(null, "", "/");
  });

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
    window.history.replaceState(null, "", href);
    expect(agentsChatUrlMatches(href)).toBe(true);
    expect(agentsChatUrlMatches("/workbench/agents/chat?agent=a1&conv=c1")).toBe(true);
    expect(agentsChatUrlMatches("/workbench/agents/chat/?agent=a1&conv=c2")).toBe(false);
  });

  it("replaceAgentsChat uses history.replaceState and remembers agent", () => {
    window.history.replaceState(null, "", "/workbench/agents/chat/");
    const router = { replace: vi.fn(), push: vi.fn() };
    replaceAgentsChat(router, { agent: "a1" });
    expect(router.replace).not.toHaveBeenCalled();
    expect(window.location.search).toBe("?agent=a1");
    expect(loadLastAgentsChat()).toEqual({ agentId: "a1" });
  });

  it("replaceAgentsChat with conv remembers both", () => {
    window.history.replaceState(null, "", "/workbench/agents/chat/?agent=a1");
    const router = { replace: vi.fn(), push: vi.fn() };
    replaceAgentsChat(router, { agent: "a1", conv: "c1" });
    expect(window.location.search).toContain("conv=c1");
    expect(loadLastAgentsChat()).toEqual({ agentId: "a1", convId: "c1" });
  });

  it("resolveAgentsChatEntryHref only restores agent", () => {
    expect(resolveAgentsChatEntryHref()).toBe(AGENTS_CHAT_PATH);
    rememberLastAgentsChat("agent-x", "conv-y");
    expect(resolveAgentsChatEntryHref()).toBe("/workbench/agents/chat/?agent=agent-x");
    expect(isAgentsChatNavHref("/workbench/agents/chat/")).toBe(true);
    expect(isAgentsChatNavHref("/workbench/agents")).toBe(false);
  });

  it("pushAgentsChatForAgent includes agent only", async () => {
    window.history.replaceState(null, "", "/workbench/agents/");
    const { pushAgentsChatForAgent } = await import("@/features/agents/lib/agents-chat-href");
    const router = { replace: vi.fn(), push: vi.fn() };
    pushAgentsChatForAgent(router, "agent-x");
    expect(router.push).toHaveBeenCalledWith("/workbench/agents/chat/?agent=agent-x");
    expect(loadLastAgentsChat()).toEqual({ agentId: "agent-x" });
  });
});
