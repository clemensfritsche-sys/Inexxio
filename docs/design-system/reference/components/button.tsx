'use client';

import { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'text-white border border-transparent disabled:opacity-50',
  secondary:
    'bg-white border border-[#D0CDCA] hover:bg-[#FAFAF8] text-[#2D2D30] disabled:opacity-50',
  ghost:
    'bg-transparent hover:bg-[#F4F2EF] text-[#2D2D30] border border-transparent disabled:opacity-50',
  danger:
    'bg-red-600 hover:bg-red-700 text-white border border-transparent disabled:opacity-50',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm rounded-md gap-1.5',
  md: 'px-4 py-2.5 text-sm rounded-lg gap-2',
  lg: 'px-6 py-3 text-base rounded-lg gap-2',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      leftIcon,
      rightIcon,
      className,
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        style={variant === 'primary' ? { background: '#E51A14' } : undefined}
        onMouseEnter={(e) => {
          if (variant === 'primary' && !(disabled || loading)) {
            (e.currentTarget as HTMLButtonElement).style.background = '#B3120F';
          }
        }}
        onMouseLeave={(e) => {
          if (variant === 'primary') {
            (e.currentTarget as HTMLButtonElement).style.background = '#E51A14';
          }
        }}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed',
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : leftIcon ? (
          <span className="shrink-0">{leftIcon}</span>
        ) : null}
        {children}
        {!loading && rightIcon ? <span className="shrink-0">{rightIcon}</span> : null}
      </button>
    );
  },
);

Button.displayName = 'Button';
