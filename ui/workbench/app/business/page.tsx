/** 业务中心入口重定向。 */

import { redirect } from "next/navigation";

export default function BusinessHomePage() {
  redirect("/business/dashboard");
}
