"use client";

import { useEffect } from "react";
import { ossFormFromConfig } from "@/lib/system-config-shared";
import { useSystemConfigInfra } from "@/hooks/use-system-config-infra";
import { useSystemConfigLoad } from "@/hooks/use-system-config-load";
import { useSystemConfigOss } from "@/hooks/use-system-config-oss";

export function useSystemConfigPage() {
  const load = useSystemConfigLoad();
  const oss = useSystemConfigOss(load);
  const infra = useSystemConfigInfra(load);

  useEffect(() => {
    if (load.oss) oss.setOssForm(ossFormFromConfig(load.oss));
  }, [load.oss, oss.setOssForm]);

  return {
    user: load.user,
    infra: load.infra,
    oss: load.oss,
    ossForm: oss.ossForm,
    setOssForm: oss.setOssForm,
    ossTesting: oss.ossTesting,
    ossSaving: oss.ossSaving,
    values: load.values,
    setValues: load.setValues,
    msg: load.msg,
    testing: infra.testing,
    testingId: infra.testingId,
    byCategory: load.byCategory,
    onSave: load.onSave,
    onSaveOss: oss.onSaveOss,
    onTestOss: oss.onTestOss,
    onTestAll: infra.onTestAll,
    onTestOne: infra.onTestOne,
  };
}

export type SystemConfigPageVm = ReturnType<typeof useSystemConfigPage>;
