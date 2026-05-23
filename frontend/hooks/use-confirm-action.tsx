"use client";

import { useCallback, useState, type ReactNode } from "react";
import { ConfirmDialog } from "@/components/resource/ConfirmDialog";

export type ConfirmRequest = {
  title: string;
  description?: string;
  message?: ReactNode;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
};

export function useConfirmAction() {
  const [state, setState] = useState<ConfirmRequest | null>(null);
  const [loading, setLoading] = useState(false);

  const requestConfirm = useCallback((req: ConfirmRequest) => {
    setState(req);
  }, []);

  const close = useCallback(() => {
    if (!loading) setState(null);
  }, [loading]);

  const handleConfirm = useCallback(async () => {
    if (!state) return;
    setLoading(true);
    try {
      await state.onConfirm();
      setState(null);
    } finally {
      setLoading(false);
    }
  }, [state]);

  const confirmDialog = (
    <ConfirmDialog
      open={state !== null}
      title={state?.title ?? ""}
      description={state?.description}
      message={state?.message}
      confirmLabel={state?.confirmLabel}
      cancelLabel={state?.cancelLabel}
      destructive={state?.destructive}
      loading={loading}
      onClose={close}
      onConfirm={handleConfirm}
    >
      {state?.children}
    </ConfirmDialog>
  );

  return { requestConfirm, confirmDialog };
}
