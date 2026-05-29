"use client";

import { ListFooter, type ListFooterProps } from "@milesai/ui-shared/ui/list-footer";

type Props = Omit<ListFooterProps, "emptyClassName"> & {
  emptyClassName?: string;
};

/**
 * 列表底部分页：绑定 `usePagedList` 的 page/total/size/setSize。
 */
export function ResourceListFooter({ emptyClassName = "py-12 text-center text-sm text-ink-faint", ...props }: Props) {
  return <ListFooter {...props} emptyClassName={emptyClassName} />;
}
