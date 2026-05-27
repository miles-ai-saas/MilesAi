/** 根路径重定向至工作台概览（链路 §15，见 lib/chains.ts）。 */

import { redirect } from "next/navigation";

export default function Home() {
  redirect("/workbench/dashboard");
}
