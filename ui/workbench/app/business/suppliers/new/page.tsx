"use client";

/** 兼容旧链接：重定向至供应商列表（新建改为弹窗）。 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function NewSupplierRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/business/suppliers");
  }, [router]);

  return null;
}
