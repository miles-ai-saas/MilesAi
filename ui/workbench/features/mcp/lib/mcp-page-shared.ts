export const MCP_PAGE_DESC =
  "注册 Model Context Protocol 端点（HTTP / SSE / STDIO），同步远程工具列表；绑定到智能体后注入系统提示。SSE 请填写 GET 长连接地址。";

export function parseStdioArgs(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}
