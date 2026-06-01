/** 业务仪表盘 feature 对外入口。 */

export { BusinessDashboardView, useBusinessDashboardPage, type BusinessDashboardPageVm } from "./components/BusinessDashboardView";
export { BizPageHero } from "./components/BizPageHero";
export { BusinessFlowStrip } from "./components/BusinessFlowStrip";
export { BUSINESS_MAIN_FLOW, BUSINESS_RESOURCE_FLOW, getFlowStep, type BusinessFlowStepId } from "./lib/business-flow";
