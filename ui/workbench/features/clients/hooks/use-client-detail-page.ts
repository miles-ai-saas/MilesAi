"use client";

import { useCallback, useEffect, useState } from "react";
import { useBizDetailTab } from "@/features/business/lib/use-biz-detail-tab";
import { api } from "@/lib/api";
import type { BizClient, BizClientContact, BizContract, BizOpportunity, BizProject } from "@/lib/types";

const VALID_TABS = ["info", "related", "contacts"] as const;
export type ClientDetailTab = (typeof VALID_TABS)[number];

type ContactForm = {
  name: string;
  title: string;
  phone: string;
  email: string;
  is_primary: boolean;
};

type ClientEditForm = {
  name: string;
  short_name: string;
  industry: string;
  confidentiality_level: string;
  address: string;
  remark: string;
};

const emptyContactForm = (): ContactForm => ({
  name: "", title: "", phone: "", email: "", is_primary: false,
});

type Options = {
  onMutated?: () => void;
};

export function useClientDetailPage(clientId: string, options?: Options) {
  const onMutated = options?.onMutated;
  const { tab, handleTabChange } = useBizDetailTab(
    "/business/clients",
    clientId,
    VALID_TABS,
    "info",
  );
  const [client, setClient] = useState<BizClient | null>(null);
  const [projects, setProjects] = useState<BizProject[]>([]);
  const [opportunities, setOpportunities] = useState<BizOpportunity[]>([]);
  const [contracts, setContracts] = useState<BizContract[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [contactForm, setContactForm] = useState<ContactForm>(emptyContactForm);
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [savingContact, setSavingContact] = useState(false);
  const [editingClient, setEditingClient] = useState(false);
  const [clientForm, setClientForm] = useState<ClientEditForm>({
    name: "", short_name: "", industry: "enterprise", confidentiality_level: "normal", address: "", remark: "",
  });
  const [savingClient, setSavingClient] = useState(false);

  const resetLocalState = useCallback(() => {
    setClient(null);
    setProjects([]);
    setOpportunities([]);
    setContracts([]);
    setError("");
    setContactForm(emptyContactForm());
    setEditingContactId(null);
    setEditingClient(false);
  }, []);

  const loadClient = useCallback(async () => {
    const data = await api.getClient(clientId);
    setClient(data);
    setClientForm({
      name: data.name,
      short_name: data.short_name ?? "",
      industry: data.industry ?? "enterprise",
      confidentiality_level: data.confidentiality_level,
      address: data.address ?? "",
      remark: data.remark ?? "",
    });
    return data;
  }, [clientId]);

  const loadRelated = useCallback(async () => {
    const [proj, opp, con] = await Promise.all([
      api.listProjects(1, 50, clientId),
      api.listOpportunities(1, 50, clientId),
      api.listContracts(1, 50, undefined, undefined, clientId),
    ]);
    setProjects(proj.items);
    setOpportunities(opp.items);
    setContracts(con.items);
  }, [clientId]);

  useEffect(() => {
    if (!clientId || clientId === "_") {
      setLoading(false);
      setError("缺少客户 ID");
      setClient(null);
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([loadClient(), loadRelated()])
      .catch((e) => setError(e?.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [clientId, loadClient, loadRelated]);

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
    if (!clientId || !contactForm.name.trim()) return;
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
      onMutated?.();
    } finally {
      setSavingContact(false);
    }
  };

  const handleDeleteContact = async (contactId: string) => {
    if (!clientId || !window.confirm("确定删除该联系人？")) return;
    await api.deleteContact(clientId, contactId);
    if (editingContactId === contactId) resetContactForm();
    await loadClient();
    onMutated?.();
  };

  const handleClientSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientId || !clientForm.name.trim()) return;
    setSavingClient(true);
    try {
      await api.updateClient(clientId, {
        name: clientForm.name.trim(),
        short_name: clientForm.short_name.trim() || undefined,
        industry: clientForm.industry || undefined,
        confidentiality_level: clientForm.confidentiality_level,
        address: clientForm.address.trim() || undefined,
        remark: clientForm.remark.trim() || undefined,
      });
      await loadClient();
      setEditingClient(false);
      onMutated?.();
    } finally {
      setSavingClient(false);
    }
  };

  return {
    client, projects, opportunities, contracts, loading, error, tab, handleTabChange,
    contactForm, setContactForm,
    editingContactId, savingContact, resetContactForm, startEditContact,
    handleContactSubmit, handleDeleteContact,
    editingClient, setEditingClient, clientForm, setClientForm,
    savingClient, handleClientSubmit,
  };
}

export type ClientDetailPageVm = ReturnType<typeof useClientDetailPage>;
