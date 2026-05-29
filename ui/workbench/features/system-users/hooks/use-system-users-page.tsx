"use client";

import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useSystemUsersForm } from "@/features/system-users/hooks/use-system-users-form";
import { useSystemUsersList } from "@/features/system-users/hooks/use-system-users-list";
import { useSystemUsersSelection } from "@/features/system-users/hooks/use-system-users-selection";

export function useSystemUsersPage() {
  const listSlice = useSystemUsersList();
  const { requestConfirm, confirmDialog } = useConfirmAction();
  const selection = useSystemUsersSelection(listSlice, requestConfirm);
  const form = useSystemUsersForm(listSlice, requestConfirm);

  return {
    currentUser: listSlice.currentUser,
    list: listSlice.list,
    roles: listSlice.roles,
    confirmDialog,
    ...selection,
    ...form,
  };
}

export type SystemUsersPageVm = ReturnType<typeof useSystemUsersPage>;
