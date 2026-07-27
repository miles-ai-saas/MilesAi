import { buildAgentsChatHref, agentsChatUrlMatches, AGENTS_CHAT_PATH } from "@/features/agents/lib/agents-chat-href";

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
    // jsdom location defaults; stub via history if available
    window.history.replaceState({}, "", href);
    expect(agentsChatUrlMatches(href)).toBe(true);
    expect(agentsChatUrlMatches("/workbench/agents/chat?agent=a1&conv=c1")).toBe(true);
    expect(agentsChatUrlMatches("/workbench/agents/chat/?agent=a1&conv=c2")).toBe(false);
  });
});
