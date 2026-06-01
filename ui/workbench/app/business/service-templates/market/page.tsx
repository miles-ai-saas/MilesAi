import { redirect } from "next/navigation";

/** 旧路径兼容：/business/service-templates/market → /business/template-market */
export default function ServiceTemplatesMarketRedirectPage() {
  redirect("/business/template-market");
}
