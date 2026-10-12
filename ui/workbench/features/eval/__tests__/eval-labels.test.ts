import { describe, expect, it } from "vitest";
import { buildExpectedPayload, formatExpectedPreview, parseExpectedForm } from "../lib/eval-labels";

describe("parseExpectedForm", () => {
  it("parses exact / contains / rubric", () => {
    expect(parseExpectedForm({ exact: "答" })).toEqual({ mode: "exact", value: "答" });
    expect(parseExpectedForm({ contains: "含" })).toEqual({ mode: "contains", value: "含" });
    expect(parseExpectedForm({ rubric: "应礼貌" })).toEqual({ mode: "rubric", value: "应礼貌" });
    expect(parseExpectedForm({ contains_all: ["a"] })).toEqual({ mode: "none", value: "" });
  });
});

describe("buildExpectedPayload", () => {
  it("builds rubric and preserves _source", () => {
    const prev = { contains: "旧", _source: { call_id: "c1" } };
    expect(buildExpectedPayload("rubric", "  新标准  ", prev)).toEqual({
      rubric: "新标准",
      _source: { call_id: "c1" },
    });
  });

  it("returns null for empty", () => {
    expect(buildExpectedPayload("none", "x")).toBeNull();
    expect(buildExpectedPayload("contains", "  ")).toBeNull();
  });
});

describe("formatExpectedPreview", () => {
  it("labels rubric", () => {
    expect(formatExpectedPreview({ rubric: "完整准确" })).toContain("评分标准");
  });
});
