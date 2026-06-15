/**
 * Custom compact dropdown for chat header model pickers.
 * Native <select> menus use OS styling; this matches the header's 10px bordered controls.
 */
import React, { useEffect, useRef, useState } from "react";

export interface ChatHeaderSelectOption {
  id: string;
  display: string;
  enabled: boolean;
}

interface ChatHeaderSelectProps {
  value: string;
  options: ChatHeaderSelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  wide?: boolean;
  title?: string;
}

const ChatHeaderSelect: React.FC<ChatHeaderSelectProps> = ({
  value,
  options,
  onChange,
  disabled = false,
  wide = false,
  title,
}) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = options.find((opt) => opt.id === value);

  useEffect(() => {
    if (!open) return;
    // Use click (not mousedown) for outside dismiss so option mousedown can close first.
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const triggerClass = [
    "chat-header-select",
    "chat-header-select-trigger",
    wide ? "chat-header-select--embed" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="chat-header-select-wrap" ref={rootRef}>
      <button
        type="button"
        className={triggerClass}
        disabled={disabled}
        title={title}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev);
        }}
      >
        <span className="chat-header-select-value truncate">
          {selected?.display ?? value}
        </span>
        <span className="chat-header-select-chevron" aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <ul className="chat-header-select-menu" role="listbox" aria-label={title}>
          {options.map((opt) => {
            const isSelected = opt.id === value;
            return (
              <li
                key={opt.id}
                role="option"
                aria-selected={isSelected}
                aria-disabled={!opt.enabled}
                title={opt.enabled ? undefined : "Not configured or unavailable"}
                className={[
                  isSelected ? "is-selected" : "",
                  !opt.enabled ? "is-disabled" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onMouseDown={(e) => {
                  if (!opt.enabled) return;
                  e.preventDefault();
                  onChange(opt.id);
                  setOpen(false);
                }}
              >
                {opt.display}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default ChatHeaderSelect;
