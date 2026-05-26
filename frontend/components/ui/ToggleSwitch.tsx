"use client";

type Props = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
};

export function ToggleSwitch({ checked, onChange, label, disabled }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-[4.25rem] shrink-0 items-center rounded-full transition disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "bg-brand" : "bg-surface-muted"
      }`}
    >
      <span
        className={`inline-block h-5 w-5 rounded-full bg-surface shadow transition-transform ${
          checked ? "translate-x-[2.125rem]" : "translate-x-1"
        }`}
      />
      {label && (
        <span
          className={`pointer-events-none absolute inset-0 flex items-center text-[11px] font-medium ${
            checked ? "justify-start pl-2 text-brand-foreground" : "justify-end pr-2 text-ink-muted"
          }`}
        >
          {label}
        </span>
      )}
    </button>
  );
}
