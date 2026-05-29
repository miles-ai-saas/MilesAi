"use client";

import { useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import type { ToolDialogMode } from "@/features/tools/lib/tool-create-dialog-shared";
import { buildCustomToolPayload, emptyToolForm, toolFormFromCustomTool, type ToolFormState } from "@/features/tools/lib/tools-form-shared";
import { slugFromName } from "@/features/tools/lib/tool-page-shared";
import type { CustomTool, ToolCatalogItem } from "@/lib/types";

type Params = {
  reloadCatalog: () => Promise<void>;
};

export function useToolsFormDialog({ reloadCatalog }: Params) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<ToolDialogMode>("create");
  const [editing, setEditing] = useState<CustomTool | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [form, setForm] = useState<ToolFormState>(emptyToolForm);

  const patchForm = (patch: Partial<ToolFormState>) => setForm((f) => ({ ...f, ...patch }));

  const openCreate = () => {
    setDialogMode("create");
    setEditing(null);
    setForm(emptyToolForm());
    setSaveError("");
    setDialogOpen(true);
  };

  const openEdit = async (item: ToolCatalogItem) => {
    if (!item.tool_id) return;
    const detail = (await api.listCustomTools(1, 100)).items.find((t) => t.id === item.tool_id);
    if (!detail) return;
    setDialogMode("edit");
    setSaveError("");
    setEditing(detail);
    setForm(toolFormFromCustomTool(detail));
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!form.name.trim() || !form.slug.trim()) return;
    if (form.toolKind === "http" && !form.url.trim()) return;
    if (form.toolKind === "script" && !form.scriptSource.trim()) return;

    const built = buildCustomToolPayload(form);
    if ("error" in built) {
      alert(built.error);
      return;
    }

    setBusy(true);
    setSaveError("");
    try {
      if (dialogMode === "edit" && editing) {
        await api.updateCustomTool(editing.id, built.payload);
      } else {
        await api.createCustomTool(built.payload);
      }
      setDialogOpen(false);
      await reloadCatalog();
    } catch (e) {
      setSaveError(getApiErrorMessage(e, "保存失败"));
    } finally {
      setBusy(false);
    }
  };

  const onNameChange = (v: string) => {
    patchForm({ name: v, ...(dialogMode === "create" ? { slug: slugFromName(v) } : {}) });
  };

  return {
    dialogOpen,
    setDialogOpen,
    dialogMode,
    editing,
    busy,
    saveError,
    setSaveError,
    form,
    patchForm,
    openCreate,
    openEdit,
    onSave,
    onNameChange,
    setToolKind: (v: ToolFormState["toolKind"]) => patchForm({ toolKind: v }),
    setSlug: (v: string) => patchForm({ slug: v }),
    setName: (v: string) => patchForm({ name: v }),
    setDescription: (v: string) => patchForm({ description: v }),
    setTagIds: (v: string[]) => patchForm({ tagIds: v }),
    setVersion: (v: string) => patchForm({ version: v }),
    setRequireConfirmation: (v: boolean) => patchForm({ requireConfirmation: v }),
    setParameters: (v: ToolFormState["parameters"]) => patchForm({ parameters: v }),
    setUrl: (v: string) => patchForm({ url: v }),
    setMethod: (v: string) => patchForm({ method: v }),
    setHeadersJson: (v: string) => patchForm({ headersJson: v }),
    setBodyMode: (v: ToolFormState["bodyMode"]) => patchForm({ bodyMode: v }),
    setTimeoutSec: (v: number) => patchForm({ timeoutSec: v }),
    setScriptSource: (v: string) => patchForm({ scriptSource: v }),
    toolKind: form.toolKind,
    slug: form.slug,
    name: form.name,
    description: form.description,
    tagIds: form.tagIds,
    version: form.version,
    requireConfirmation: form.requireConfirmation,
    parameters: form.parameters,
    url: form.url,
    method: form.method,
    headersJson: form.headersJson,
    bodyMode: form.bodyMode,
    timeoutSec: form.timeoutSec,
    scriptSource: form.scriptSource,
  };
}

export type ToolsFormDialog = ReturnType<typeof useToolsFormDialog>;
