'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Building2, ClipboardList, FileText, Loader2, Package, Plus, ScanLine, Search, User, X } from 'lucide-react';
import { cn, formatObjectId } from '@/lib/utils';
import { FILTER_TYPES, TYPE_META } from '@/lib/erp-record';
import { type Row, rowStatus, rowTitle } from '@/lib/use-feed-lists';
import { RecordIcon } from '@/components/erp/detail-frame';
import { StatusBadge } from '@/components/erp/fields';
import { userInitials } from '@/components/erp/user-detail';
import type { ErpRecordType, Todo } from '@/types';

/** Was «+» anlegen kann – ein Anlageweg je Sorte. */
export type Creatable = 'article' | 'order' | 'person' | 'company' | 'document';

/** Wie viele Zeilen auf einmal gerendert werden; der Rest kommt beim Scrollen. */
const CHUNK = 50;

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick, todo }: {
  row: Row; sel: boolean; onClick: () => void;
  /** Was zu tun ist – die Zahl am Symbol (`lib/todo`). */
  todo?: Todo | null;
}) {
  const title = rowTitle(row);
  const badge = rowStatus(row);
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        // Der Feed ist eine Liste zum Überfliegen – die Trennung machen Weissraum und
        // Ausrichtung, nicht Fläche.
        'w-full flex items-center gap-3 px-3 py-3 mb-1 rounded-ds-md text-left transition-colors',
        sel ? 'bg-accent-soft' : 'hover:bg-bg-2',
      )}
    >
      {/* **Dieselbe Komponente wie im Detail-Kopf** – Symbol, Farbfamilie, Form und das
          Abweichungs-Zeichen kommen aus EINER Stelle; nur die Grösse unterscheidet sie. */}
      <RecordIcon
        type={row.type}
        size={28}
        photoUrl={row.type === 'user' ? row.data.photo_url : undefined}
        initials={row.type === 'user' ? userInitials(title ?? '', row.data.email) : undefined}
        deviation={row.type === 'order' && row.data.is_deviation}
        own={row.type === 'organization' && !!row.data.is_own}
        todo={todo}
      />
      <div className="min-w-0 flex-1">
        <div className={cn('text-sm font-semibold truncate', sel ? 'text-accent-ink' : title ? 'text-fg-1' : 'text-fg-4 italic')}>
          {title ?? (row.type === 'user' ? 'Kein Name' : 'Ohne Bezeichnung')}
        </div>
        {/* Zweite Zeile: Kennung + Zustand – dieselbe Pille wie im Detail-Kopf. */}
        <div className="flex items-center gap-2.5 mt-1">
          <span className="text-fg-4 tabular-nums" style={{ font: 'var(--mono-sm)' }}>{formatObjectId(row.objectId)}</span>
          {badge && <StatusBadge cfg={badge} size={11} />}
        </div>
      </div>
    </button>
  );
}

/** Suche + Scan – die eine Eingabe über der Liste. */
function SearchBar({ search, onSearch, onScan }: {
  search: string; onSearch: (q: string) => void; onScan: () => void;
}) {
  return (
    <div className="flex items-center gap-2.5 px-5 pt-4 pb-3.5">
      <div className="flex-1 min-w-0 flex items-center gap-2.5 rounded-ds-md border border-border-2 px-2.5 py-2">
        <Search size={17} className="flex-none text-fg-4" aria-hidden />
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Suchen…"
          aria-label="Datensätze suchen"
          className="flex-1 min-w-0 border-none outline-none bg-transparent text-sm text-fg-1 placeholder:text-fg-4"
        />
        {search && (
          <button type="button" onClick={() => onSearch('')} title="Eingabe löschen" aria-label="Eingabe löschen"
            className="flex-none w-8 h-8 rounded-ds-sm flex items-center justify-center bg-bg-3 text-fg-3 hover:text-fg-1 transition-colors">
            <X size={13} />
          </button>
        )}
        <button type="button" onClick={onScan} data-tip="Datensatz scannen" data-tip-pos="bottom"
          aria-label="Datensatz scannen"
          className="flex-none w-10 h-10 rounded-ds-sm flex items-center justify-center bg-bg-2 border border-border-1 text-fg-3 hover:text-fg-1 hover:bg-bg-3 transition-colors">
          <ScanLine size={18} />
        </button>
      </div>
    </div>
  );
}

/** Typ-Filter – Symbol zuerst, aktiv mit Wort und Anzahl (Farbe = Typ). */
function TypeChips({ typeFilter, onTypeFilter, count }: {
  typeFilter: ErpRecordType | null; onTypeFilter: (t: ErpRecordType | null) => void;
  count: (t: ErpRecordType) => number;
}) {
  return (
    <div className="flex flex-wrap gap-1.5 px-5 pb-4 border-b border-border-1">
      {FILTER_TYPES.filter((t) => count(t)).map((t) => {
        const active = typeFilter === t;
        const meta = TYPE_META[t];
        const Icon = meta.icon;
        return (
          <button
            key={t}
            type="button"
            onClick={() => onTypeFilter(active ? null : t)}
            aria-label={`Nur ${meta.label} zeigen (${count(t)})`}
            aria-pressed={active}
            data-tip={`${meta.label} · ${count(t)}`}
            data-tip-pos="bottom"
            {...(active ? { 'data-tip-hidden': '' } : {})}
            className={cn(
              'h-[42px] rounded-ds-md flex items-center justify-center gap-1.5 border transition-colors',
              active ? 'border-transparent px-3.5' : 'min-w-[42px] border-border-1 bg-bg-1 hover:bg-bg-2',
            )}
            style={active ? { background: meta.bg, color: meta.fg } : { color: meta.fg }}
          >
            <Icon size={18} />
            {active && (
              <>
                <span className="text-[13px] font-bold">{meta.label}</span>
                <span className="text-[12.5px] font-bold tabular-nums opacity-60">{count(t)}</span>
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}

const CREATE: { type: Creatable; label: string; icon: typeof Package }[] = [
  { type: 'article', label: 'Artikel', icon: Package },
  { type: 'order', label: 'Auftrag', icon: ClipboardList },
  { type: 'person', label: 'Person', icon: User },
  // Firmen legt jedes Personal an; «eigen» setzt nur ein Admin.
  { type: 'company', label: 'Unternehmen', icon: Building2 },
  // **Ein Anlageweg für jedes Dokument** – Scan, Datei, Verfassen.
  { type: 'document', label: 'Dokument', icon: FileText },
];

/** «+» – neuen Datensatz anlegen; das Menü öffnet nach oben, ein Klick daneben schliesst. */
function CreateButton({ onCreate }: { onCreate: (type: Creatable) => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);
  return (
    <div ref={box} className="absolute right-5 bottom-5 z-20">
      {open && (
        <div className="absolute right-0 bottom-[calc(100%+10px)] bg-bg-1 border border-border-1 rounded-ds-md shadow-ds-lg p-1 min-w-[170px]">
          {CREATE.map(({ type, label, icon: Icon }) => (
            <button key={type} type="button" onClick={() => { setOpen(false); onCreate(type); }} style={MENU_ITEM}>
              <Icon size={15} style={{ color: 'var(--fg-3)' }} /> {label}
            </button>
          ))}
        </div>
      )}
      {/* Er schwebt über der Liste (Schatten der schwebenden Ebene); der rote Schatten ist
          nur der Hover-Akzent des roten Knopfs (Design-System §3). */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        data-tip={open ? undefined : 'Neuen Datensatz anlegen'}
        aria-label="Neuen Datensatz anlegen"
        aria-expanded={open}
        className="w-[54px] h-[54px] rounded-full bg-inexxio hover:bg-inexxio-deep text-fg-on-red shadow-ds-md hover:shadow-ds-red flex items-center justify-center transition-all hover:-translate-y-0.5"
      >
        <Plus size={24} className={cn('transition-transform', open && 'rotate-45')} />
      </button>
    </div>
  );
}

const MENU_ITEM: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '9px 11px', borderRadius: 8, border: 'none', background: 'none',
  fontSize: 13, fontWeight: 600, color: 'var(--fg-2)', cursor: 'pointer', textAlign: 'left',
};

/**
 * ►►► **Die Liste des Feeds** – Suche, Typ-Filter, die Zeilen und «+». ◄◄◄ Gerendert wird
 * in Häppchen (`CHUNK`); erreicht man das Ende, kommen die nächsten Zeilen und – wo
 * Instanzen dazugehören – die nächste Seite vom Server (`onMore`).
 */
export function FeedPanel({ show, search, onSearch, typeFilter, onTypeFilter, rows, count, loading,
  more, onMore, isSelected, onSelect, todos, staff, onScan, onCreate }: {
  /** Schmal ist entweder die Liste oder das Detail zu sehen. */
  show: boolean;
  search: string; onSearch: (q: string) => void;
  typeFilter: ErpRecordType | null; onTypeFilter: (t: ErpRecordType | null) => void;
  rows: Row[];
  count: (t: ErpRecordType) => number;
  loading: boolean;
  /** Gibt es auf dem Server noch mehr (Instanzen)? */
  more: boolean;
  onMore: () => void;
  isSelected: (row: Row) => boolean;
  onSelect: (row: Row) => void;
  todos: Map<number, Todo>;
  staff: boolean;
  onScan: () => void;
  onCreate: (type: Creatable) => void;
}) {
  const [visible, setVisible] = useState(CHUNK);
  // Wechselt die Suche oder der Filter, beginnt die Liste wieder oben.
  useEffect(() => { setVisible(CHUNK); }, [typeFilter, search]);
  const next = useRef(() => {});
  next.current = () => { setVisible((c) => c + CHUNK); if (more) onMore(); };
  // Der Beobachter hängt per Callback-Ref am Ende der Liste (auch wenn es erst nach dem
  // Laden erscheint) und ruft den stets frischen Handler.
  const observer = useRef<IntersectionObserver | null>(null);
  const sentinel = useCallback((node: HTMLDivElement | null) => {
    observer.current?.disconnect();
    if (!node) return;
    observer.current = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) next.current(); }, { threshold: 0.1 });
    observer.current.observe(node);
  }, []);

  return (
    <div className={cn(
      // Die Anzeige (`flex` · `hidden`) steht nur in der Bedingung – `cn` mischt keine
      // Klassen, zwei widersprüchliche gälten nach ihrer Reihenfolge im CSS.
      'flex-shrink-0 border-r border-border-1 flex-col bg-bg-1 relative',
      'w-full md:w-[300px] lg:w-[336px]',
      show ? 'flex' : 'hidden md:flex',
    )}>
      <SearchBar search={search} onSearch={onSearch} onScan={onScan} />
      <TypeChips typeFilter={typeFilter} onTypeFilter={onTypeFilter} count={count} />
      <div className="flex-1 overflow-y-auto min-h-0 p-2 pb-24">
        {loading && <div className="p-6 text-center text-sm text-fg-4">Laden…</div>}
        {!loading && rows.length === 0 && (
          <div className="p-6 text-center text-sm text-fg-4">
            {search || typeFilter ? 'Keine Treffer' : 'Keine Datensätze'}
          </div>
        )}
        {rows.slice(0, visible).map((r) => (
          <FeedItem key={r.key} row={r} sel={isSelected(r)} onClick={() => onSelect(r)}
            todo={r.objectId != null ? todos.get(r.objectId) : null} />
        ))}
        {(visible < rows.length || more) && (
          <div ref={sentinel} className="flex items-center justify-center gap-2 p-3.5 text-fg-4 text-xs">
            <Loader2 size={15} className="animate-spin" />
            <span>Weitere werden geladen…</span>
          </div>
        )}
      </div>
      {staff && <CreateButton onCreate={onCreate} />}
    </div>
  );
}
