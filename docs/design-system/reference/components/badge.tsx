import { cn } from '@/lib/utils';

export type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

export interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'bg-green-50 text-green-700 ring-green-600/20',
  warning: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  error: 'bg-red-50 text-red-700 ring-red-600/20',
  info: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  neutral: 'bg-slate-100 text-slate-600 ring-slate-500/20',
};

export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}

// Map ERP status strings to badge variants
export function statusToBadgeVariant(status: string): BadgeVariant {
  const lower = status.toLowerCase();
  if (
    ['freigegeben', 'aktiv', 'aktiv', 'lieferant', 'kunde', 'partner'].some((s) =>
      lower.includes(s),
    )
  )
    return 'success';
  if (['entwurf', 'interessent'].some((s) => lower.includes(s))) return 'neutral';
  if (['gesperrt', 'archiviert'].some((s) => lower.includes(s))) return 'warning';
  if (['ersetzt', 'inaktiv'].some((s) => lower.includes(s))) return 'error';
  return 'neutral';
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={statusToBadgeVariant(status)}>{status}</Badge>;
}
