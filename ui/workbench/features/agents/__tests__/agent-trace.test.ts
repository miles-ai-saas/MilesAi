import { describe, it, expect } from "vitest";
import { listTraceTurns, defaultTraceTurnIndex, turnIndexForMessageIndex } from "@/features/agents/lib/agent-trace";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";

describe("listTraceTurns", () => {
  it("空消息列表返回空 turns", () => {
    expect(listTraceTurns([])).toEqual([]);
  });

  it("仅用户消息不产生 turn", () => {
    const msgs: ChatMessage[] = [{ role: "user", content: "hello" }];
    expect(listTraceTurns(msgs)).toEqual([]);
  });

  it("单轮对话产生一个 turn", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "你好" },
      { role: "assistant", content: "你好！有什么可以帮助你的？", steps: [{ type: "retrieve", hit_count: 2 }], traceId: "trace-1" },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns).toHaveLength(1);
    expect(turns[0].userQuery).toBe("你好");
    expect(turns[0].traceId).toBe("trace-1");
    expect(turns[0].steps).toHaveLength(1);
    expect(turns[0].turnIndex).toBe(0);
    expect(turns[0].messageIndex).toBe(1);
  });

  it("多轮对话正确关联 user → assistant", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "问题1" },
      { role: "assistant", content: "回答1" },
      { role: "user", content: "问题2" },
      { role: "assistant", content: "回答2" },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns).toHaveLength(2);
    expect(turns[0].userQuery).toBe("问题1");
    expect(turns[1].userQuery).toBe("问题2");
  });

  it("连续多条助手消息均关联到最近一条用户消息", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "提问" },
      { role: "assistant", content: "回答A" },
      { role: "assistant", content: "回答B" },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns).toHaveLength(2);
    expect(turns[0].userQuery).toBe("提问");
    expect(turns[1].userQuery).toBe("提问");
  });

  it("助手消息无 steps/traceId 时为空", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "提问" },
      { role: "assistant", content: "回答" },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns).toHaveLength(1);
    expect(turns[0].steps).toEqual([]);
    expect(turns[0].traceId).toBeUndefined();
  });

  it("助理预览截断 80 字符", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "提问" },
      { role: "assistant", content: "A".repeat(100) },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns[0].assistantPreview.length).toBe(81); // 80 chars + "…"
    expect(turns[0].assistantPreview.endsWith("…")).toBe(true);
  });

  it("系统消息被忽略", () => {
    // ChatMessage 运行时只有 user/assistant；此处构造类型外的脏数据（如服务端扩展 role），验证不会当作 turn
    const msgs: ChatMessage[] = [
      { role: "system", content: "系统提示" } as unknown as ChatMessage,
      { role: "user", content: "提问" },
      { role: "assistant", content: "回答" },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns).toHaveLength(1);
    expect(turns[0].userQuery).toBe("提问");
  });

  it("turnIndex 从 0 递增", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "Q1" },
      { role: "assistant", content: "A1" },
      { role: "user", content: "Q2" },
      { role: "assistant", content: "A2" },
      { role: "assistant", content: "A3" },
    ];
    const turns = listTraceTurns(msgs);
    expect(turns[0].turnIndex).toBe(0);
    expect(turns[1].turnIndex).toBe(1);
    expect(turns[2].turnIndex).toBe(2);
  });
});

describe("defaultTraceTurnIndex", () => {
  it("空列表返回 0", () => {
    expect(defaultTraceTurnIndex([])).toBe(0);
  });

  it("返回最后一轮的下标", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "Q1" },
      { role: "assistant", content: "A1" },
      { role: "user", content: "Q2" },
      { role: "assistant", content: "A2" },
    ];
    const turns = listTraceTurns(msgs);
    expect(defaultTraceTurnIndex(turns)).toBe(1);
  });
});

describe("turnIndexForMessageIndex", () => {
  it("非助手消息返回 null", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "Q" },
      { role: "assistant", content: "A" },
    ];
    expect(turnIndexForMessageIndex(msgs, 0)).toBeNull();
  });

  it("助手消息返回对应 turn index", () => {
    const msgs: ChatMessage[] = [
      { role: "user", content: "Q1" },
      { role: "assistant", content: "A1" },
      { role: "user", content: "Q2" },
      { role: "assistant", content: "A2" },
    ];
    expect(turnIndexForMessageIndex(msgs, 1)).toBe(0);
    expect(turnIndexForMessageIndex(msgs, 3)).toBe(1);
  });
});
