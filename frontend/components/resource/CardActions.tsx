"use client";

type Props = {
  onEdit?: () => void;
  onDelete?: () => void;
  deleteLabel?: string;
};

export function CardActions({ onEdit, onDelete, deleteLabel = "删除" }: Props) {
  return (
    <div className="flex flex-wrap gap-3">
      {onEdit && (
        <button type="button" className="text-xs text-brand hover:underline" onClick={onEdit}>
          编辑
        </button>
      )}
      {onDelete && (
        <button type="button" className="text-xs text-red-600 hover:underline" onClick={onDelete}>
          {deleteLabel}
        </button>
      )}
    </div>
  );
}
