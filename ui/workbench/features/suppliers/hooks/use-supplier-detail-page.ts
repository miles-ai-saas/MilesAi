"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BizSupplier, BizSupplierContact } from "@/lib/types";

export function useSupplierDetailPage(supplierId: string) {
  const router = useRouter();
  const [supplier, setSupplier] = useState<BizSupplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contactForm, setContactForm] = useState({ name: "", title: "", phone: "", email: "", is_primary: false });
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [savingContact, setSavingContact] = useState(false);

  const load = useCallback(async () => {
    const data = await api.getSupplier(supplierId);
    setSupplier(data);
    return data;
  }, [supplierId]);

  useEffect(() => {
    load().catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [load]);

  const resetContactForm = () => {
    setContactForm({ name: "", title: "", phone: "", email: "", is_primary: false });
    setEditingContactId(null);
  };

  const startEditContact = (c: BizSupplierContact) => {
    setEditingContactId(c.id);
    setContactForm({ name: c.name, title: c.title ?? "", phone: c.phone ?? "", email: c.email ?? "", is_primary: c.is_primary });
  };

  const handleContactSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactForm.name.trim()) return;
    setSavingContact(true);
    try {
      const payload = {
        name: contactForm.name.trim(),
        title: contactForm.title.trim() || undefined,
        phone: contactForm.phone.trim() || undefined,
        email: contactForm.email.trim() || undefined,
        is_primary: contactForm.is_primary,
      };
      if (editingContactId) {
        await api.updateSupplierContact(supplierId, editingContactId, payload);
      } else {
        await api.createSupplierContact(supplierId, payload);
      }
      resetContactForm();
      await load();
    } finally {
      setSavingContact(false);
    }
  };

  const handleDeleteContact = async (contactId: string) => {
    if (!window.confirm("确定删除该联系人？")) return;
    await api.deleteSupplierContact(supplierId, contactId);
    await load();
  };

  return {
    router,
    supplier,
    loading,
    error,
    contactForm,
    setContactForm,
    editingContactId,
    savingContact,
    resetContactForm,
    startEditContact,
    handleContactSubmit,
    handleDeleteContact,
    reload: load,
  };
}

export type SupplierDetailPageVm = ReturnType<typeof useSupplierDetailPage>;
