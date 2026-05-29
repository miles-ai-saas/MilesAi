"use client";

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { McpServiceCard } from "@/features/mcp/components/McpServiceCard";
import { McpServiceDetailDialog } from "@/features/mcp/components/McpServiceDetailDialog";
import { McpServiceDialog } from "@/features/mcp/components/McpServiceDialog";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import type { McpPageVm } from "@/features/mcp/hooks/use-mcp-page";

const MCP_PAGE_DESC =
  "注册 Model Context Protocol 端点（HTTP / SSE / STDIO），同步远程工具列表；绑定到智能体后注入系统提示。SSE 请填写 GET 长连接地址。";

export function McpPageView({ vm }: { vm: McpPageVm }) {
  const {
    mcpMeta,
    activeTab,
    onTabChange,
    search,
    setSearch,
    msg,
    setMsg,
    list,
    filtered,
    pageStats,
    activeTabLabel,
    layoutTabs,
    dialogOpen,
    setDialogOpen,
    dialogMode,
    dialogTransport,
    editing,
    viewingLive,
    detailOpen,
    setDetailOpen,
    name,
    setName,
    description,
    setDescription,
    endpointUrl,
    setEndpointUrl,
    stdioCommand,
    setStdioCommand,
    stdioArgs,
    setStdioArgs,
    busy,
    syncingId,
    saveError,
    setSaveError,
    confirmDialog,
    openCreate,
    openEdit,
    openDetail,
    onDialogTransportChange,
    onSubmit,
    onSync,
    onDelete,
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="MCP 服务"
        description={MCP_PAGE_DESC}
        searchPlaceholder="搜索服务名称、描述或端点"
        search={search}
        onSearchChange={setSearch}
        tabs={layoutTabs}
        activeTab={activeTab}
        onTabChange={onTabChange}
        loading={list.loading}
        headerAction={
          <button type="button" className="btn-ghost shrink-0 text-sm" disabled={list.loading} onClick={() => void list.reload()}>
            {list.loading ? "刷新中…" : "刷新"}
          </button>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}

        <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatChip label="服务总数" value={String(list.total)} hint={`当前筛选：${activeTabLabel}`} />
          <StatChip label="本页已同步" value={String(pageStats.synced)} hint={`同步失败 ${pageStats.warn}（当前页）`} />
          <StatChip label="本页工具数" value={String(pageStats.tools)} hint="已缓存 tools/list" />
          <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索筛选影响" />
        </div>

        <AddResourceCard label="添加 MCP 服务" hint="支持 HTTP、SSE、STDIO；创建后同步 tools/list" onClick={() => openCreate("http")} />

        {!list.loading && filtered.length === 0 && (
          <p className="col-span-full py-12 text-center text-sm text-ink-faint">暂无匹配的 MCP 服务，点击「添加 MCP 服务」注册 HTTP / SSE / STDIO</p>
        )}

        {filtered.map((s) => (
          <McpServiceCard
            key={s.id}
            service={s}
            mcpMeta={mcpMeta}
            onDetail={() => openDetail(s)}
            onSync={() => void onSync(s.id)}
            onEdit={() => openEdit(s)}
            onDelete={() => onDelete(s)}
          />
        ))}
      </ResourceListLayout>

      <McpServiceDialog
        open={dialogOpen}
        mode={dialogMode}
        transport={dialogTransport}
        editing={editing}
        mcpMeta={mcpMeta}
        name={name}
        description={description}
        endpointUrl={endpointUrl}
        stdioCommand={stdioCommand}
        stdioArgs={stdioArgs}
        busy={busy}
        saveError={saveError}
        onClose={() => setDialogOpen(false)}
        onDismissError={() => setSaveError("")}
        onSubmit={() => void onSubmit()}
        onTransportChange={onDialogTransportChange}
        onNameChange={setName}
        onDescriptionChange={setDescription}
        onEndpointUrlChange={setEndpointUrl}
        onStdioCommandChange={setStdioCommand}
        onStdioArgsChange={setStdioArgs}
      />

      <McpServiceDetailDialog
        open={detailOpen}
        service={viewingLive}
        mcpMeta={mcpMeta}
        syncing={viewingLive ? syncingId === viewingLive.id : false}
        onClose={() => setDetailOpen(false)}
        onSync={viewingLive ? () => void onSync(viewingLive.id) : undefined}
        onEdit={viewingLive ? () => openEdit(viewingLive) : undefined}
        onDelete={viewingLive ? () => onDelete(viewingLive) : undefined}
      />

      {confirmDialog}
    </>
  );
}
