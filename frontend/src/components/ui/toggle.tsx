'use client';

import { cn } from '@/lib/utils';

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
  id?: string;
}

export function Toggle({ checked, onChange, label, description, disabled, id }: ToggleProps) {
  const toggleId = id || (label ? `toggle-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="flex items-start gap-3">
      <button
        type="button"
        role="switch"
        id={toggleId}
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
          'transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2',
          'focus-visible:ring-blue-500 focus-visible:ring-offset-2',
          checked ? 'bg-blue-600' : 'bg-slate-200',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0',
            'transition duration-200 ease-in-out',
            checked ? 'translate-x-5' : 'translate-x-0',
          )}
        />
      </button>
      {(label || description) && (
        <div>
          {label && (
            <label
              htmlFor={toggleId}
              className="block text-sm font-medium text-slate-700 cursor-pointer"
            >
              {label}
            </label>
          )}
          {description && <p className="text-sm text-slate-500">{description}</p>}
        </div>
      )}
    </div>
  );
}
