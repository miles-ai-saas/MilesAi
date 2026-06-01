"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BizClient, BizClientContact } from "@/lib/types";

const INDUSTRY_LABELS: Record<string, string> = {
  government: "政府机关", enterprise: "企业", park: "园区",
  commercial: "商业综合体", tourism: "文旅", other: "其他",
};
const CONF_LABELS: Record<string, string> = {
  normal: "普通", internal: "内部", restricted: "涉密",
};

type ContactForm = {
  name: string;
  title: string;
  phone: string;
  email: string;
  is_primary: boolean;
};

const emptyContactForm = (): ContactForm => ({
  name: "", title: "", phone: "", email: "", is_primary: false,
});

export function useClientDetailPage(clientId: string) {
  const router = useRouter();
  const [client, setClient] = useState<BizClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contactForm, setContactForm] = useState<ContactForm>(emptyContactForm);
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [savingContact, setSavingContact] = useState(false);

  const loadClient = useCallback(async () => {
    const data = await api.getClient(clientId);
    setClient(data);
    return data;
  }, [clientId]);

  useEffect(() => {
    loadClient().catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [loadClient]);

  const resetContactForm = () => {
    setContactForm(emptyContactForm());
    setEditingContactId(null);
  };

  const startEditContact = (contact: BizClientContact) => {
    setEditingContactId(contact.id);
    setContactForm({
      name: contact.name,
      title: contact.title ?? "",
      phone: contact.phone ?? "",
      email: contact.email ?? "",
      is_primary: contact.is_primary,
    });
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
        await api.updateContact(clientId, editingContactId, payload);
      } else {
        await api.createContact(clientId, payload);
      }
      await loadClient();
      resetContactForm();
    } finally {
      setSavingContact(false);
    }
  };

  const handleDeleteContact = async (contactId: string) => {
    if (!window.confirm("确定删除该联系人？")) return;
    await api.deleteContact(clientId, contactId);
    if (editingContactId === contactId) resetContactForm();
    await loadClient();
  };

  return {
    router, client, loading, error, contactForm, setContactForm,
    editingContactId, savingContact, resetContactForm, startEditContact,
    handleContactSubmit, handleDeleteContact,
  };
}

export type ClientDetailPageVm = ReturnType<typeof useClientDetailPage>;
