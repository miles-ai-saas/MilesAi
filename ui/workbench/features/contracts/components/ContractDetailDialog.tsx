"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ContractDetailView } from "@/features/contracts/components/ContractDetailView";
import { useContractDetailPage } from "@/features/contracts/hooks/use-contract-detail-page";
import { CONTRACT_TYPE_LABELS } from "@/features/contracts/lib/contract-labels";

type Props = {
  contractId: string | null;
  onClose: () => void;
  onMutated?: () => void;
};

export function ContractDetailDialog({ contractId, onClose, onMutated }: Props) {
  const vm = useContractDetailPage(contractId, { onMutated });
  const contract = vm.contract;

  const description = contract
    ? [CONTRACT_TYPE_LABELS[contract.type] ?? contract.type, contract.contract_no].filter(Boolean).join(" · ")
    : undefined;

  return (
    <ResourceDialog
      open={Boolean(contractId)}
      title={contract?.name ?? "合同详情"}
      description={description}
      onClose={onClose}
      size="drawer"
    >
      <ContractDetailView vm={vm} embedded />
    </ResourceDialog>
  );
}
