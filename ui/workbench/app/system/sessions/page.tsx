"use client";

/** 当前用户登录会话：查看设备与强制下线。 */

import { SystemSessionsPageView } from "@/components/system-sessions/SystemSessionsPageView";
import { useSystemSessionsPage } from "@/hooks/use-system-sessions-page";

export default function SystemSessionsPage() {
  const vm = useSystemSessionsPage();
  return <SystemSessionsPageView vm={vm} />;
}
