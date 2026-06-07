import { cn } from '@/lib/utils';
import { formatObjectId, relativeTime } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/badge';
import { Package, ClipboardList, Archive, Building2, User, Users, FileText } from 'lucide-react';
import type { UniversalObject, ObjectType } from '@/types';

const typeIcons: Record<ObjectType, React.ReactNode> = {
  item: <Package className="h-4 w-4" />,
  auftrag: <ClipboardList className="h-4 w-4" />,
  objekt: <Archive className="h-4 w-4" />,
  company: <Building2 className="h-4 w-4" />,
  contact: <User className="h-4 w-4" />,
  user: <Users className="h-4 w-4" />,
};

const typeLabels: Record<ObjectType, string> = {
  item: 'Artikel',
  auftrag: 'Auftrag',
  objekt: 'Objekt',
  company: 'Firma',
  contact: 'Kontakt',
  user: 'Benutzer',
};

const typeBgColors: Record<ObjectType, string> = {
  item: 'bg-blue-50 text-blue-600',
  auftrag: 'bg-amber-50 text-amber-600',
  objekt: 'bg-violet-50 text-violet-600',
  company: 'bg-green-50 text-green-600',
  contact: 'bg-slate-100 text-slate-600',
  user: 'bg-teal-50 text-teal-700',
};

interface ObjectRowProps {
  object: UniversalObject;
  selected?: boolean;
  onClick?: () => void;
}

export function ObjectRow({ object, selected, onClick }: ObjectRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0',
        selected && 'bg-blue-50 border-l-2 border-l-blue-600 hover:bg-blue-50',
      )}
    >
      {/* Type icon */}
      <div
        className={cn(
          'shrink-0 flex h-9 w-9 items-center justify-center rounded-lg mt-0.5',
          typeBgColors[object.object_type] ?? 'bg-slate-100 text-slate-600',
        )}
      >
        {typeIcons[object.object_type] ?? <FileText className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs font-mono text-slate-400 leading-none mb-0.5">
              {formatObjectId(object.id)}
            </p>
            <p
              className={cn(
                'text-sm font-medium leading-snug truncate',
                selected ? 'text-blue-700' : 'text-slate-900',
              )}
            >
              {object.title}
            </p>
            {object.subtitle && (
              <p className="text-xs text-slate-500 truncate mt-0.5">{object.subtitle}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 mt-1.5">
          <StatusBadge status={object.status} />
          <span className="text-xs text-slate-400">{relativeTime(object.created_at)}</span>
        </div>
      </div>
    </button>
  );
}

export { typeIcons, typeLabels, typeBgColors };
