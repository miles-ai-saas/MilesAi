"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import type { CustomTool } from "@/lib/types";

type CatalogItem = {
  source: string;
  name: string;
  description?: string | null;
  tool_id?: string | null;
  mcp_service_name?: string | null;
};

export default function ToolsPage() {
  const { ready } = useRequireAuth();
  const [tab, setTab] = useState<"all" | "custom">("all");
  const [search, setSearch] = useState("");
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [testTool, setTestTool] = useState<CatalogItem | null>(null);
  const [testParams, setTestParams] = useState('{"expression": "1+2*3"}');
  const [testResult, setTestResult] = useState("");
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [url, setUrl] = useState("");
  const [method, setMethod] = useState("POST");

  const list = usePagedList(useCallback((p, s) => api.listCustomTools(p, s), []), {
    enabled: ready && tab === "custom",
  });

  useEffect(() => {
    if (!ready) return;
    api.listToolCatalog().then(setCatalog);
  }, [ready]);

  const filteredCatalog = useMemo(
    () => filterBySearch(catalog, search, (t) => `${t.name} ${t.description ?? ""} ${t.source}`),
    [catalog, search],
  );
  const filteredCustom = useMemo(
    () => filterBySearch(list.items, search, (t) => `${t.name} ${t.description ?? ""}`),
    [list.items, search],
  );

  const onCreate = async () => {
    if (!name.trim()) return;
    await api.createCustomTool(name.trim(), desc, {
      url: url.trim(),
      method,
    });
    setName("");
    setDesc("");
    setUrl("");
    setDialogOpen(false);
    await list.reload();
    setCatalog(await api.listToolCatalog());
  };

  const runTest = async () => {
    if (!testTool) return;
    let params: Record<string, unknown> = {};
    try {
      params = JSON.parse(testParams || "{}");
    } catch {
      setTestResult("参数 JSON 格式错误");
      return;
    }
    try {
      if (testTool.source === "mcp" && testTool.mcp_service_name) {
        const mcpList = await api.listMcpServices(1, 100);
        const svc = mcpList.items.find((s) => s.name === testTool.mcp_service_name);
        if (!svc) {
          setTestResult("未找到 MCP 服务");
          return;
        }
        const res = await api.invokeMcpTool(svc.id, testTool.name, params);
        setTestResult(JSON.stringify(res.output, null, 2));
      } else {
        const res = await api.invokeTool(
          testTool.name,
          params,
          testTool.tool_id || undefined,
        );
        setTestResult(JSON.stringify(res.output, null, 2));
      }
    } catch (e) {
      setTestResult(e instanceof Error ? e.message : "调用失败");
    }
  };

  return (
    <>
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("all")}
          className={`rounded-lg px-3 py-1.5 text-sm ${
            tab === "all" ? "bg-brand-light font-medium text-brand" : "text-ink-muted"
          }`}
        >
          工具目录
        </button>
        <button
          type="button"
          onClick={() => setTab("custom")}
          className={`rounded-lg px-3 py-1.5 text-sm ${
            tab === "custom" ? "bg-brand-light font-medium text-brand" : "text-ink-muted"
          }`}
        >
          自定义 HTTP
        </button>
      </div>

      {tab === "all" && (
        <ResourceListLayout
          title="工具"
          description="内置工具、自定义 HTTP 与 MCP 同步工具的统一目录，可供技能包引用。"
          searchPlaceholder="搜索工具"
          search={search}
          onSearchChange={setSearch}
          loading={false}
        >
          {filteredCatalog.map((t) => (
            <ResourceItemCard
              key={`${t.source}-${t.name}-${t.tool_id ?? ""}`}
              title={t.name}
              description={t.description ?? "—"}
              badge={t.source === "builtin" ? "内置" : t.source === "mcp" ? "MCP" : "自定义"}
              meta={
                t.mcp_service_name ? <span>来自 {t.mcp_service_name}</span> : undefined
              }
              actions={
                <button
                  type="button"
                  className="text-xs text-brand hover:underline"
                  onClick={() => {
                    setTestTool(t);
                    setTestParams(
                      t.name === "calculator"
                        ? '{"expression": "1+2*3"}'
                        : t.name === "knowledge_search"
                          ? '{"query": "示例", "kb_id": ""}'
                          : "{}",
                    );
                    setTestResult("");
                    setTestOpen(true);
                  }}
                >
                  试调用
                </button>
              }
            />
          ))}
        </ResourceListLayout>
      )}

      {tab === "custom" && (
        <ResourceListLayout
          title="自定义 HTTP 工具"
          description="注册 HTTP 端点，在流程或试调用中通过工具名执行。"
          searchPlaceholder="搜索工具"
          search={search}
          onSearchChange={setSearch}
          loading={list.loading}
          footer={
            !list.loading ? (
              <ResourceListFooter
                page={list.page}
                size={list.size}
                total={list.total}
                onPageChange={list.setPage}
              />
            ) : null
          }
        >
          <AddResourceCard
            label="添加自定义工具"
            hint="配置 URL 与 HTTP 方法"
            onClick={() => setDialogOpen(true)}
          />
          {filteredCustom.map((t: CustomTool) => (
            <ResourceItemCard
              key={t.id}
              title={t.name}
              description={
                (t.config as { url?: string })?.url || t.description || "自定义 HTTP 工具"
              }
              badge={t.is_active ? "启用" : "停用"}
              actions={
                <span className="flex gap-2">
                  <button
                    type="button"
                    className="text-xs text-brand hover:underline"
                    onClick={() => {
                      setTestTool({
                        source: "custom",
                        name: t.name,
                        tool_id: t.id,
                      });
                      setTestParams("{}");
                      setTestOpen(true);
                    }}
                  >
                    试调用
                  </button>
                  <button
                    type="button"
                    className="text-xs text-red-600 hover:underline"
                    onClick={async () => {
                      await api.deleteCustomTool(t.id);
                      await list.reload();
                      setCatalog(await api.listToolCatalog());
                    }}
                  >
                    删除
                  </button>
                </span>
              }
            />
          ))}
        </ResourceListLayout>
      )}

      <ResourceDialog
        open={dialogOpen}
        title="添加自定义 HTTP 工具"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onCreate}>
              添加
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="描述"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <select
          className="input-field w-full"
          value={method}
          onChange={(e) => setMethod(e.target.value)}
        >
          <option value="GET">GET</option>
          <option value="POST">POST</option>
          <option value="PUT">PUT</option>
        </select>
      </ResourceDialog>

      <ResourceDialog
        open={testOpen}
        title={testTool ? `试调用 · ${testTool.name}` : "试调用"}
        onClose={() => setTestOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setTestOpen(false)}>
              关闭
            </button>
            <button type="button" className="btn-primary" onClick={runTest}>
              执行
            </button>
          </>
        }
      >
        <textarea
          className="input-field min-h-[100px] w-full font-mono text-xs"
          value={testParams}
          onChange={(e) => setTestParams(e.target.value)}
        />
        {testResult && (
          <pre className="mt-3 max-h-48 overflow-auto rounded bg-surface-muted p-3 text-xs">
            {testResult}
          </pre>
        )}
      </ResourceDialog>
    </>
  );
}
