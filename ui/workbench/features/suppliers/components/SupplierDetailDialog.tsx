"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { SupplierDetailView } from "@/features/suppliers/components/SupplierDetailView";
import { useSupplierDetailPage } from "@/features/suppliers/hooks/use-supplier-detail-page";

type Props = {
  supplierId: string | null;
  onClose: () => void;
  onMutated?: () => void;
};

export function SupplierDetailDialog({ supplierId, onClose, onMutated }: Props) {
  const vm = useSupplierDetailPage(supplierId, { onMutated });

  return (
    <ResourceDialog
      open={Boolean(supplierId)}
      title={vm.supplier?.name ?? "供应商详情"}
      description={vm.supplier?.short_name ?? undefined}
      onClose={onClose}
      size="drawer"
    >
      <SupplierDetailView vm={vm} embedded onClose={onClose} />
    </ResourceDialog>
  );
}
