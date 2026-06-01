"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizContract, BizPayment } from "@/lib/types";

type Options = {
  onMutated?: () => void;
};

export function useContractDetailPage(contractId: string | null, options?: Options) {
  const onMutated = options?.onMutated;
  const [contract, setContract] = useState<BizContract | null>(null);
  const [payments, setPayments] = useState<BizPayment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"info" | "payments">("info");

  const resetLocalState = useCallback(() => {
    setContract(null);
    setPayments([]);
    setError("");
    setTab("info");
  }, []);

  const loadContract = useCallback(async () => {
    if (!contractId) return null;
    const data = await api.getContract(contractId);
    setContract(data);
    return data;
  }, [contractId]);

  const loadPayments = useCallback(async () => {
    if (!contractId) return;
    setPayments(await api.listPayments(contractId));
  }, [contractId]);

  useEffect(() => {
    if (!contractId) {
      resetLocalState();
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    loadContract()
      .catch((e) => setError(e?.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [contractId, loadContract, resetLocalState]);

  const handleTabChange = useCallback(
    (t: "info" | "payments") => {
      setTab(t);
      if (t === "payments") void loadPayments();
    },
    [loadPayments],
  );

  return {
    contract,
    payments,
    loading,
    error,
    tab,
    handleTabChange,
    loadPayments,
    onMutated,
  };
}

export type ContractDetailPageVm = ReturnType<typeof useContractDetailPage>;
