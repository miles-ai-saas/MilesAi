/** 内置模型目录 feature 对外入口。 */

export { useModelCatalogPage, type ModelCatalogPageVm } from "./hooks/use-model-catalog-page";
export { useModelCatalogDetailPage, type ModelCatalogDetailPageVm } from "./hooks/use-model-catalog-detail-page";

export { ModelCatalogPageView } from "./components/ModelCatalogPageView";
export { ModelCatalogDetailPageView } from "./components/ModelCatalogDetailPageView";
export { ModelCatalogEditor } from "./components/ModelCatalogEditor";

export { emptyForm, fromRow, toPayload, type ModelCatalogFormValues } from "./lib/form-utils";

export { default as ModelCatalogDetailContent } from "./components/ModelCatalogDetailContent";
