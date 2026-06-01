"use client";

/** 兼容旧链接：重定向至客户列表（新建改为弹窗）。 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function NewClientRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/business/clients");
  }, [router]);

  return null;
}
