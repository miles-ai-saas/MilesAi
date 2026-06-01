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
  const [editingInfo, setEditingInfo] = useState(false);
  const [savingInfo, setSavingInfo] = useState(false);
  const [infoForm, setInfoForm] = useState({
    name: "",
    contract_no: "",
    type: "service",
    status: "draft",
    signed_date: "",
    start_date: "",
    end_date: "",
    total_amount: "",
    payment_terms: "",
    description: "",
  });

  const syncInfoForm = useCallback((data: BizContract) => {
    setInfoForm({
      name: data.name,
      contract_no: data.contract_no ?? "",
      type: data.type,
      status: data.status,
      signed_date: data.signed_date ?? "",
      start_date: data.start_date ?? "",
      end_date: data.end_date ?? "",
      total_amount: data.total_amount != null ? String(data.total_amount) : "",
      payment_terms: data.payment_terms ?? "",
      description: data.description ?? "",
    });
  }, []);

  const resetLocalState = useCallback(() => {
    setContract(null);
    setPayments([]);
    setError("");
    setTab("info");
    setEditingInfo(false);
  }, []);

  const loadContract = useCallback(async () => {
    if (!contractId) return null;
    const data = await api.getContract(contractId);
    setContract(data);
    syncInfoForm(data);
    return data;
  }, [contractId, syncInfoForm]);

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

  const saveContractInfo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contractId || !infoForm.name.trim()) return;
    setSavingInfo(true);
    try {
      const updated = await api.updateContract(contractId, {
        name: infoForm.name.trim(),
        contract_no: infoForm.contract_no.trim() || undefined,
        type: infoForm.type,
        status: infoForm.status,
        signed_date: infoForm.signed_date || undefined,
        start_date: infoForm.start_date || undefined,
        end_date: infoForm.end_date || undefined,
        total_amount: infoForm.total_amount ? Number(infoForm.total_amount) : undefined,
        payment_terms: infoForm.payment_terms.trim() || undefined,
        description: infoForm.description.trim() || undefined,
      });
      setContract(updated);
      syncInfoForm(updated);
      setEditingInfo(false);
      onMutated?.();
    } finally {
      setSavingInfo(false);
    }
  };

  return {
    contract,
    payments,
    loading,
    error,
    tab,
    handleTabChange,
    loadPayments,
    onMutated,
    editingInfo,
    setEditingInfo,
    infoForm,
    setInfoForm,
    savingInfo,
    saveContractInfo,
  };
}

export type ContractDetailPageVm = ReturnType<typeof useContractDetailPage>;
