'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Plus, ScanLine, Search, X } from 'lucide-react';
import { cn, formatObjectId } from '@/lib/utils';
import { FILTER_TYPES, TYPE_META } from '@/lib/erp-record';
import { type Row, rowStatus, rowTitle } from '@/lib/use-feed-lists';
import { useUnfinished } from '@/lib/assistant';
import { ERP_HEAD_H, RecordIcon } from '@/components/erp/detail-frame';
import { StatusBadge } from '@/components/erp/fields';
import { userInitials } from '@/components/erp/user-detail';
import type { ErpRecordType, Todo } from '@/types';
import { Skeleton } from './skeleton';
import { Haltung } from './haltung';

/** Was «+» anlegen kann – ein Anlageweg je Sorte (`capture/capture-sheet.CREATE`). */
export type Creatable = 'article' | 'order' | 'person' | 'company' | 'document';

/** Wie viele Zeilen auf einmal gerendert werden; der Rest kommt beim Scrollen. */
const CHUNK = 50;

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick, todo, mine }: {
  row: Row; sel: boolean; onClick: () => void;
  /** Was zu tun ist – das rote Zeichen am Symbol (`lib/todo`). */
  todo?: Todo | null;
  /** **Meine eine Aufgabe** – die Zeile steht zuoberst, mit einer Linie darunter. */
  mine?: boolean;
}) {
  const title = rowTitle(row);
  const badge = rowStatus(row);
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        // Der Feed ist eine Liste zum Überfliegen – die Trennung machen Weissraum und
        // Ausrichtung, nicht Fläche. Eine Zeile geht über die ganze Breite (kein Kasten in der
        // Liste); die gewählte liegt auf dem hellen Ton ihrer Art – derselbe Ton wie ihr Symbol.
        'w-full flex items-center gap-3 px-5 py-3 text-left transition-colors',
        !sel && 'hover:bg-bg-2',
        mine && 'border-b border-border-1',
      )}
      style={sel ? { background: TYPE_META[row.type].bg } : undefined}
      aria-current={sel || undefined}
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
        <div className={cn('text-sm font-semibold truncate', title ? 'text-fg-1' : 'text-fg-4 italic')}>
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

/** Suche + Scan – die eine Eingabe über der Liste: eine graue Fläche wie die Felder im Konto,
 *  darin Lupe, Eingabe und der Scan als Symbol (kein Kasten im Kasten). */
function SearchBar({ search, onSearch, onScan }: {
  search: string; onSearch: (q: string) => void; onScan: () => void;
}) {
  return (
    <div className="flex items-center px-5 pt-4 pb-3">
      <div className="flex-1 min-w-0 h-11 flex items-center gap-2.5 rounded-ds-md bg-bg-2 pl-3 pr-1 focus-within:bg-bg-1 focus-within:ring-1 focus-within:ring-fg-1">
        <Search size={17} className="flex-none text-fg-4" aria-hidden />
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Suchen…"
          aria-label="Datensätze suchen"
          className="flex-1 min-w-0 border-none outline-none bg-transparent text-sm text-fg-1 placeholder:text-fg-4"
        />
        {search && (
          <button type="button" onClick={() => onSearch('')} data-tip="Eingabe löschen" aria-label="Eingabe löschen"
            className="flex-none w-8 h-8 rounded-ds-md flex items-center justify-center text-fg-4 hover:text-fg-1 transition-colors">
            <X size={13} />
          </button>
        )}
        <button type="button" onClick={onScan} data-tip="Datensatz scannen" data-tip-pos="bottom"
          aria-label="Datensatz scannen"
          className="flex-none w-9 h-9 rounded-ds-md flex items-center justify-center text-fg-3 hover:text-fg-1 hover:bg-bg-3 transition-colors">
          <ScanLine size={18} />
        </button>
      </div>
    </div>
  );
}

/** Typ-Filter – nur das Symbol in seiner Art-Farbe; aktiv auf dem hellen Ton, mit Wort und Anzahl. */
function TypeChips({ typeFilter, onTypeFilter, count }: {
  typeFilter: ErpRecordType | null; onTypeFilter: (t: ErpRecordType | null) => void;
  count: (t: ErpRecordType) => number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 px-4 pb-3 min-h-[52px]">
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
              'h-10 rounded-ds-md flex items-center justify-center gap-1.5 transition-colors',
              active ? 'px-3' : 'min-w-[40px] hover:bg-bg-2',
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

/**
 * **«+» = der Assistent** – öffnet das «+» (`capture/capture-sheet.tsx`): oben die Eingabe, darunter
 * das Gespräch und die offenen Gespräche, unten neu anlegen. Er schwebt über der Liste (Schatten
 * der schwebenden Ebene); der rote Schatten ist nur der Hover-Akzent des roten Knopfs.
 * **Die Zahl daran** sind meine offenen Gespräche – im ERP und aus Claude – und Aufnahmen, die nicht
 * abgeschrieben werden konnten (`useUnfinished`): im Rot der Aufgaben («zu tun», wie `TodoChip`),
 * mit weissem Rand, damit sie auf dem roten Knopf steht.
 */
function CaptureButton({ onCapture }: { onCapture: () => void }) {
  const unfiled = useUnfinished();
  const tip = unfiled.count
    ? `Assistent · ${unfiled.count} zu tun` : 'Assistent – sagen, was ist, oder neu anlegen';
  return (
    <div className="absolute left-5 bottom-5 z-20">
      <button
        type="button"
        onClick={onCapture}
        data-tip={tip}
        aria-label={tip}
        className="relative w-[54px] h-[54px] rounded-full bg-inexxio hover:bg-inexxio-deep text-fg-on-red shadow-ds-md hover:shadow-ds-red flex items-center justify-center transition-all hover:-translate-y-0.5"
      >
        <Plus size={24} />
        {unfiled.count > 0 && (
          <span aria-hidden className="erp-fab-count tabular-nums">
            {unfiled.count > 9 ? '9+' : unfiled.count}
          </span>
        )}
      </button>
    </div>
  );
}

/**
 * ►►► **Die Liste des Feeds** – Suche, Typ-Filter, die Zeilen und «+». ◄◄◄ Gerendert wird
 * in Häppchen (`CHUNK`); erreicht man das Ende, kommen die nächsten Zeilen und – wo
 * Instanzen dazugehören – die nächste Seite vom Server (`onMore`).
 */
export function FeedPanel({ show, search, onSearch, typeFilter, onTypeFilter, rows, count, loading,
  more, onMore, isSelected, onSelect, todos, mine, staff, onScan, onCapture }: {
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
  /** Der Datensatz meiner einen Aufgabe – ohne Filter und Suche zuoberst (`services/tasks`). */
  mine: number | null;
  staff: boolean;
  onScan: () => void;
  /** «+» – das Blatt «Erfassen». */
  onCapture: () => void;
}) {
  const [visible, setVisible] = useState(CHUNK);
  // **Meine Aufgabe zuoberst** – nur ohne Filter und Suche; darunter der Feed wie immer.
  const top = !typeFilter && !search && mine != null ? rows.find((r) => r.objectId === mine) ?? null : null;
  const rest = top ? rows.filter((r) => r !== top) : rows;
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
      {/* Der Kopf des Feeds ist genau so hoch wie der Kopf eines Datensatzes (`ERP_HEAD_H`) –
          die Linie darunter läuft ohne Versatz in die Linie unter dem Kopf rechts. */}
      <div className="flex flex-col justify-end border-b border-border-1 flex-none"
        style={{ height: ERP_HEAD_H, boxSizing: 'border-box' }}>
        <SearchBar search={search} onSearch={onSearch} onScan={onScan} />
        <TypeChips typeFilter={typeFilter} onTypeFilter={onTypeFilter} count={count} />
      </div>
      <div className="flex-1 overflow-y-auto min-h-0 pb-24">
        {loading && <Skeleton rows={8} label="Datensätze werden geladen" style={{ padding: 16 }} />}
        {!loading && rows.length === 0 && (
          <div className="p-6 text-center text-sm text-fg-4">
            {search || typeFilter ? 'Keine Treffer' : 'Keine Datensätze'}
          </div>
        )}
        {/* Am Handy steht die Haltung oben in der Liste und scrollt mit weg (am Computer füllt
            sie den leeren Detailbereich) – nur ohne Suche und Filter. */}
        {!search && !typeFilter && <div className="md:hidden"><Haltung compact /></div>}
        {top && (
          <FeedItem key={`mine-${top.key}`} row={top} sel={isSelected(top)} onClick={() => onSelect(top)}
            todo={todos.get(top.objectId!)} mine />
        )}
        {rest.slice(0, visible).map((r) => (
          <FeedItem key={r.key} row={r} sel={isSelected(r)} onClick={() => onSelect(r)}
            todo={r.objectId != null ? todos.get(r.objectId) : null} />
        ))}
        {(visible < rest.length || more) && (
          <div ref={sentinel} className="flex items-center justify-center gap-2 p-3.5 text-fg-4 text-xs">
            <Loader2 size={15} className="animate-spin" />
            <span>Weitere werden geladen…</span>
          </div>
        )}
      </div>
      {staff && <CaptureButton onCapture={onCapture} />}
    </div>
  );
}
