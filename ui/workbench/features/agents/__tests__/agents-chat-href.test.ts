import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  AGENTS_CHAT_PATH,
  agentsChatUrlMatches,
  buildAgentsChatHref,
  pushAgentsChatForAgent,
  replaceAgentsChat,
} from "@/features/agents/lib/agents-chat-href";

describe("agents-chat-href", () => {
  beforeEach(() => {
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

  it("replaceAgentsChat updates query via history.replaceState", () => {
    window.history.replaceState(null, "", "/workbench/agents/chat/");
    replaceAgentsChat({ agent: "a1" });
    expect(window.location.search).toBe("?agent=a1");
    replaceAgentsChat({ agent: "a1", conv: "c1" });
    expect(window.location.search).toContain("agent=a1");
    expect(window.location.search).toContain("conv=c1");
  });

  it("pushAgentsChatForAgent includes agent only", () => {
    window.history.replaceState(null, "", "/workbench/agents/");
    const router = { push: vi.fn() };
    pushAgentsChatForAgent(router, "agent-x");
    expect(router.push).toHaveBeenCalledWith("/workbench/agents/chat/?agent=agent-x");
  });
});
