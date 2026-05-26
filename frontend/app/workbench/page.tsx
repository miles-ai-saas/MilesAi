/** `/workbench` 重定向至概览（链路 §15）。 */

import { redirect } from "next/navigation";

export default function WorkbenchIndexPage() {
  redirect("/workbench/dashboard");
}
