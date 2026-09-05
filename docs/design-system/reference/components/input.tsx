import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftAddon?: React.ReactNode;
  rightAddon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, leftAddon, rightAddon, className, id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 mb-1.5">
            {label}
            {props.required && <span className="ml-1 text-red-500">*</span>}
          </label>
        )}
        <div className="relative flex items-center">
          {leftAddon && (
            <div className="absolute left-3 flex items-center pointer-events-none text-slate-400">
              {leftAddon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'w-full border rounded-lg px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400',
              'focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow',
              error ? 'border-red-300 focus:ring-red-500' : 'border-slate-300',
              leftAddon && 'pl-10',
              rightAddon && 'pr-10',
              className,
            )}
            {...props}
          />
          {rightAddon && (
            <div className="absolute right-3 flex items-center pointer-events-none text-slate-400">
              {rightAddon}
            </div>
          )}
        </div>
        {error && <p className="mt-1.5 text-sm text-red-600">{error}</p>}
        {helperText && !error && <p className="mt-1.5 text-sm text-slate-500">{helperText}</p>}
      </div>
    );
  },
);

Input.displayName = 'Input';
