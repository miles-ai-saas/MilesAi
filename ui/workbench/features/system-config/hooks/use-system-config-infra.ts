"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SystemConfigLoadSlice } from "@/features/system-config/hooks/use-system-config-load";

export function useSystemConfigInfra({ setInfra, setMsg }: Pick<SystemConfigLoadSlice, "setInfra" | "setMsg">) {
  const [testing, setTesting] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const onTestAll = async () => {
    setTesting(true);
    setTestingId(null);
    try {
      const res = await api.testInfraConnection();
      setInfra((prev) => (prev ? { ...prev, components: res.results, healthy: res.results.every((c) => c.status === "ok") } : prev));
      setMsg("连接测试完成");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
    }
  };

  const onTestOne = async (componentId: string) => {
    setTesting(true);
    setTestingId(componentId);
    try {
      const res = await api.testInfraConnection([componentId]);
      const updated = res.results[0];
      if (updated) {
        setInfra((prev) =>
          prev
            ? {
                ...prev,
                components: prev.components.map((c) => (c.id === componentId ? updated : c)),
                healthy: prev.components.map((c) => (c.id === componentId ? updated : c)).every((c) => c.status === "ok"),
              }
            : prev,
        );
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
      setTestingId(null);
    }
  };

  return { testing, testingId, onTestAll, onTestOne };
}
