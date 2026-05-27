/** 系统管理入口重定向（链路 §7）。 */

import { redirect } from "next/navigation";

export default function SystemHomePage() {
  redirect("/system/users");
}
