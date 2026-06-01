"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ClientDetailView } from "@/features/clients/components/ClientDetailView";
import { useClientDetailPage } from "@/features/clients/hooks/use-client-detail-page";

type Props = {
  clientId: string | null;
  onClose: () => void;
  onMutated?: () => void;
};

export function ClientDetailDialog({ clientId, onClose, onMutated }: Props) {
  const vm = useClientDetailPage(clientId ?? "", { onMutated });

  return (
    <ResourceDialog
      open={Boolean(clientId)}
      title={vm.client?.name ?? "客户详情"}
      description={vm.client?.short_name ?? undefined}
      onClose={onClose}
      size="lg"
    >
      <ClientDetailView vm={vm} embedded onClose={onClose} />
    </ResourceDialog>
  );
}
