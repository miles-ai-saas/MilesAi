"use client";

export type CardActionItem = {
  label: string;
  onClick: () => void;
  variant?: "default" | "primary" | "danger";
  disabled?: boolean;
};

type Props = {
  actions?: CardActionItem[];
  onView?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  deleteLabel?: string;
};

const variantClass: Record<NonNullable<CardActionItem["variant"]>, string> = {
  default: "text-ink-muted hover:text-ink",
  primary: "text-brand font-medium hover:underline",
  danger: "text-red-600 hover:underline",
};

export function CardActions({
  actions = [],
  onView,
  onEdit,
  onDelete,
  deleteLabel = "删除",
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {actions.map((a) => (
        <button
          key={a.label}
          type="button"
          disabled={a.disabled}
          className={`text-xs disabled:cursor-not-allowed disabled:opacity-40 ${variantClass[a.variant ?? "default"]}`}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            a.onClick();
          }}
        >
          {a.label}
        </button>
      ))}
      {onView && (
        <button
          type="button"
          className="text-xs text-brand hover:underline"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onView();
          }}
        >
          查看
        </button>
      )}
      {onEdit && (
        <button
          type="button"
          className="text-xs text-ink-muted hover:text-ink"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onEdit();
          }}
        >
          编辑
        </button>
      )}
      {onDelete && (
        <button
          type="button"
          className="text-xs text-red-600 hover:underline"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDelete();
          }}
        >
          {deleteLabel}
        </button>
      )}
    </div>
  );
}
