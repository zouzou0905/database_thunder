import { ChevronDown, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export type SelectOption = { value: string; label: string };

export function AppleSelect({
  value,
  options,
  onChange,
  ariaLabel,
  compact = false,
  dropUp = false,
}: {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
  compact?: boolean;
  dropUp?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;

    function closeOnOutside(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className={compact ? "apple-select compact" : "apple-select"} ref={rootRef}>
      <button
        type="button"
        className={open ? "apple-select-trigger open" : "apple-select-trigger"}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.label ?? "请选择"}</span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className={dropUp ? "apple-select-menu drop-up" : "apple-select-menu"} role="listbox">
          {options.map((option) => (
            <button
              type="button"
              key={option.value}
              className={option.value === value ? "apple-select-option selected" : "apple-select-option"}
              role="option"
              aria-selected={option.value === value}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
