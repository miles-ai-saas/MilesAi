"use client";

import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useSystemUsersForm } from "@/hooks/use-system-users-form";
import { useSystemUsersList } from "@/hooks/use-system-users-list";
import { useSystemUsersSelection } from "@/hooks/use-system-users-selection";

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
