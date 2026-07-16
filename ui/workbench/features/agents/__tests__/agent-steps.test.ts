import { describe, it, expect } from "vitest";
import { parseAgentSteps, buildStepsSummary, formatToolParams } from "@/features/agents/lib/agent-steps";

describe("parseAgentSteps", () => {
  it("空 steps 返回空数组", () => {
    expect(parseAgentSteps(undefined)).toEqual([]);
    expect(parseAgentSteps([])).toEqual([]);
  });

  it("解析 retrieve 步骤", () => {
    const steps = [{ type: "retrieve", hit_count: 5, top_score: 0.92 }];
    const result = parseAgentSteps(steps);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("retrieve");
    expect(result[0].title).toBe("检索知识库");
    expect(result[0].detail).toBe("命中 5 条 · 最高分 0.92");
    expect(result[0].status).toBe("neutral");
  });

  it("解析 generate 步骤", () => {
    const result = parseAgentSteps([{ type: "generate", hit_count: 3 }]);
    expect(result[0].title).toBe("生成回答");
    expect(result[0].detail).toBe("基于 3 条上下文");
  });

  it("解析 tool_call 步骤", () => {
    const result = parseAgentSteps([{ type: "tool_call", slug: "search", status: "success" }]);
    expect(result[0].title).toBe("调用工具 · search");
    expect(result[0].status).toBe("success");
  });

  it("解析子智能体 dispatch", () => {
    const result = parseAgentSteps([{ type: "subagent_dispatch", sub_agent_name: "代码助手", task: "写一个排序函数" }]);
    expect(result[0].title).toBe("委派 · 代码助手");
    expect(result[0].detail).toContain("写一个排序函数");
  });

  it("错误 step 推断 error 状态", () => {
    const result = parseAgentSteps([{ type: "tool_call", error: "timeout" }]);
    expect(result[0].status).toBe("error");
  });

  it("tool_confirmation_required 推断 pending 状态", () => {
    const result = parseAgentSteps([{ type: "tool_confirmation_required", slug: "delete" }]);
    expect(result[0].status).toBe("pending");
    expect(result[0].title).toBe("待确认 · delete");
  });

  it("fallback 推断 warning 状态", () => {
    const result = parseAgentSteps([{ type: "fallback" }]);
    expect(result[0].status).toBe("warning");
    expect(result[0].title).toBe("无足够依据");
  });

  it("unknown type 使用 type 字符串作标题", () => {
    const result = parseAgentSteps([{ type: "custom_thing" }]);
    expect(result[0].title).toBe("custom_thing");
    expect(result[0].status).toBe("neutral");
  });
});

describe("buildStepsSummary", () => {
  it("无相关步骤", () => {
    const parsed = parseAgentSteps([]);
    expect(buildStepsSummary(parsed)).toBe("共 0 步");
  });

  it("跳过 graph_start/planner 等 meta 步骤", () => {
    const parsed = parseAgentSteps([
      { type: "graph_start", engine: "langgraph" },
      { type: "planner", mode: "auto" },
      { type: "retrieve", hit_count: 3 },
    ]);
    const summary = buildStepsSummary(parsed);
    expect(summary).toContain("检索 3 条");
    expect(summary).not.toContain("启动流程图");
  });

  it("error 状态的 meta 步骤仍显示", () => {
    const parsed = parseAgentSteps([
      { type: "tool_agent", error: "no_tools" },
    ]);
    // tool_agent 在 SUMMARY_SKIP_TYPES 中，但有 error 状态所以仍显示
    expect(buildStepsSummary(parsed)).toContain("失败");
  });
});

describe("formatToolParams", () => {
  it("空参数", () => {
    expect(formatToolParams({})).toBe("（无参数）");
  });

  it("格式化简单参数", () => {
    const result = formatToolParams({ query: "hello", limit: 10 });
    expect(result).toContain('query="hello"');
    expect(result).toContain("limit=10");
  });

  it("截断过长值", () => {
    const result = formatToolParams({ text: "a".repeat(100) });
    expect(result.length).toBeLessThan(70);
  });
});
