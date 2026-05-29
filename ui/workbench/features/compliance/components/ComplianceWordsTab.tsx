"use client";

import { ComplianceLibraryDetail } from "@/components/compliance/ComplianceLibraryDetail";
import { ComplianceScanBindingsPanel } from "@/components/compliance/ComplianceScanBindingsPanel";
import { WordLibraryDialog } from "@/components/compliance/WordLibraryDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { CompliancePageVm } from "@/hooks/use-compliance-page";
import { COMPLIANCE_MAIN_TABS, COMPLIANCE_PAGE_DESC } from "@/lib/compliance-page-shared";

export function ComplianceWordsTab({ vm }: { vm: CompliancePageVm }) {
  const {
    tab,
    onTabChange,
    search,
    setSearch,
    libraryId,
    libraries,
    filteredLibs,
    activeLibrary,
    complianceMeta,
    libDialogOpen,
    setLibDialogOpen,
    editingLib,
    confirmDialog,
    openLibrary,
    closeLibrary,
    reloadLibraries,
    onDeleteLibrary,
    openCreateLib,
    openEditLib,
  } = vm;

  if (libraryId && !activeLibrary) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-ink-muted">加载词库…</div>;
  }

  if (libraryId && activeLibrary) {
    return (
      <ResourceListLayout
        title="合规与安全"
        description={COMPLIANCE_PAGE_DESC}
        search=""
        onSearchChange={() => {}}
        showSearch={false}
        tabs={COMPLIANCE_MAIN_TABS}
        activeTab={tab}
        onTabChange={(k) => vm.setTab(k as typeof tab)}
      >
        <ComplianceLibraryDetail
          library={activeLibrary}
          sensitiveActions={complianceMeta?.sensitive_actions}
          onBack={closeLibrary}
          onLibraryChange={reloadLibraries}
        />
      </ResourceListLayout>
    );
  }

  return (
    <>
      <ResourceListLayout
        title="合规与安全"
        description={COMPLIANCE_PAGE_DESC}
        searchPlaceholder="搜索词库名称"
        search={search}
        onSearchChange={setSearch}
        tabs={COMPLIANCE_MAIN_TABS}
        activeTab={tab}
        onTabChange={onTabChange}
        loading={libraries.loading && !libraryId}
        headerAction={
          <button type="button" className="btn-sm-primary" onClick={openCreateLib}>
            新建词库
          </button>
        }
        footer={
          !libraries.loading && !libraryId ? (
            <ResourceListFooter
              page={libraries.page}
              size={libraries.size}
              total={libraries.total}
              onPageChange={libraries.setPage}
              onSizeChange={libraries.setSize}
            />
          ) : null
        }
      >
        <ComplianceScanBindingsPanel onSaved={reloadLibraries} />
        <AddResourceCard label="新建词库" hint="创建后可添加词条并勾选参与扫描" onClick={openCreateLib} />
        {filteredLibs.map((lib) => (
          <ResourceItemCard
            key={lib.id}
            title={lib.name}
            description={lib.description ?? "点击管理库内敏感词条"}
            badge={lib.is_active ? "启用" : "停用"}
            muted={!lib.is_active}
            onClick={() => openLibrary(lib.id)}
            meta={<span className="tabular-nums text-ink-muted">{lib.word_count} 条词条</span>}
            actions={
              <CardActions
                onView={() => openLibrary(lib.id)}
                onEdit={() => openEditLib(lib)}
                onDelete={() => onDeleteLibrary(lib)}
              />
            }
          />
        ))}
      </ResourceListLayout>

      <WordLibraryDialog open={libDialogOpen} library={editingLib} onClose={() => setLibDialogOpen(false)} onSaved={reloadLibraries} />
      {confirmDialog}
    </>
  );
}
