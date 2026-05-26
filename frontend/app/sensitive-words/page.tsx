"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** 旧路径兼容（链路 §13，见 lib/chains.ts）：跳转到合规页 */
export default function SensitiveWordsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/workbench/compliance");
  }, [router]);
  return <p className="text-ink-muted">正在跳转…</p>;
}
