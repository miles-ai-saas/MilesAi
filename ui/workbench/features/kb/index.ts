/** 知识库 feature 对外入口（试点：features/ 目录结构）。 */

export { useKbPage, type KbPageVm } from "./hooks/use-kb-page";
export { useKbDetailPage, type KbDetailPageVm } from "./hooks/use-kb-detail-page";
export { useKbMeta } from "./hooks/use-kb-meta";

export { KbCatalogView } from "./components/KbCatalogView";
export { KbFormDialog } from "./components/KbFormDialog";
export { KbPageAlert } from "./components/KbPageAlert";
export { KbQuotaBar } from "./components/KbQuotaBar";

export { DocumentChunksDrawer } from "./components/DocumentChunksDrawer";
export { KbDetailDocumentsTab } from "./components/KbDetailDocumentsTab";
export { KbDetailHeader } from "./components/KbDetailHeader";
export { KbDetailLogsTab } from "./components/KbDetailLogsTab";
export { KbDetailSearchTab } from "./components/KbDetailSearchTab";
export { KbDetailSettingsDialog } from "./components/KbDetailSettingsDialog";
export { KbDetailSkeleton } from "./components/KbDetailSkeleton";

export { KB_PAGE_DESC, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP } from "./lib/kb-page-shared";
export { KB_DETAIL_TABS } from "./lib/kb-detail-shared";
export { retrievalModeLabel } from "./lib/kb-labels";
