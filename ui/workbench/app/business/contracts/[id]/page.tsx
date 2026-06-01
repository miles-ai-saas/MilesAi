"use client";

/** 兼容旧链接：重定向至列表页详情抽屉（`?id=`）。 */

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ContractDetailRedirectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/business/contracts?id=${encodeURIComponent(id)}`);
  }, [id, router]);

  return null;
}
