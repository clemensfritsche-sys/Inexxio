'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { useSearch } from '@/lib/use-search';
import { FieldAction, Label, inputCls } from '@/components/erp/controls';

/**
 * **Eine Zeile der Auswahl – in der Form des Scanners**: `label` die Hauptangabe (Objektnummer,
 * tabellarisch), `name` leise daneben. Ohne `name` eine schlichte Zeile.
 */
export interface SelectOption { value: string; label: string; name?: string }

/** Wie eine Zeile als **Text** aussieht – im geschlossenen Feld und beim Filtern. */
const optionText = (o: SelectOption) => (o.name ? `${o.label} · ${o.name}` : o.label);

/** Durchsuchbare Referenz-Auswahl (Combobox). Filtert Optionen per Tippen –
 *  z. B. «003» findet die Objektnummer 100000003. */
/**
 * Neueste zuerst: die grösste Objektnummer oben – gemeint ist fast immer ein zuletzt angelegter
 * Datensatz. Greift nur, wenn ALLE Werte Zahlen sind.
 */
function newestFirst(options: SelectOption[]): SelectOption[] {
  const isNum = (v: string) => v !== '' && Number.isFinite(Number(v));
  const numeric = options.filter((o) => isNum(o.value));
  // Nicht-numerische Einträge (Platzhalter) bleiben vorn; mehr als einer heisst gemischte
  // Liste – dann bleibt die Reihenfolge des Aufrufers.
  const others = options.filter((o) => !isNum(o.value));
  if (numeric.length < 2 || others.length > 1) return options;
  return [...others, ...numeric.sort((a, b) => Number(b.value) - Number(a.value))];
}

/** Wo die Vorschlagsliste steht – in Bildschirm-Koordinaten, weil sie `fixed` hängt. */
type ListBox = { left: number; top: number; width: number; maxHeight: number };

// Die Masse der Liste an EINER Stelle. `LIST_Z` liegt über dem Dialog des Hauses (60) und
// unter dem Scan-Vollbild (100).
const LIST_GAP = 4;    // Luft zum Feld
const LIST_EDGE = 8;   // Luft zum Fensterrand
const LIST_MIN = 160;  // darunter lohnt sich das Aufklappen nach unten nicht mehr
const LIST_MAX = 240;
const LIST_Z = 70;

export function SearchSelect({ label, value, onChange, options, required, placeholder,
                               search, emptyOption, action }: {
  label?: string; value: string; onChange: (v: string) => void;
  options: SelectOption[]; required?: boolean; placeholder?: string;
  /**
   * **Eine Handlung AM Feld, nicht daneben** – am rechten Innenrand anstelle des Chevrons.
   */
  action?: { icon: ReactNode; label: string; onClick: () => void; disabled?: boolean };
  /**
   * **«Nichts» ist eine Wahl – also steht sie in der Liste**: erste Zeile mit dem Wert `''`,
   * und ein leeres Feld zeigt sie an. Ohne die Angabe heisst leer «noch nicht gewählt».
   */
  emptyOption?: string;
  /**
   * **Wo die Auswahl zu gross für eine Liste ist: suchen statt mitgeben.** Mit ihr fragt das
   * Feld beim Tippen den Server; `options` trägt dann nur die gewählte Option. Dieselbe Bauart
   * wie beim Scanner (`candidates` ↔ `suggest`).
   */
  search?: (query: string) => Promise<SelectOption[]>;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<ListBox | null>(null);
  // Die Leer-Zeile steht vor der Sortierung und bleibt vorn.
  const all = emptyOption ? [{ value: '', label: emptyOption }, ...options] : options;
  const selected = all.find((o) => o.value === value);
  const ordered = newestFirst(all);

  // Entprellt, mit Veralterungs-Schutz – die eine Suche des Hauses (`useSearch`).
  const { hits: found, pending } = useSearch(query, search);

  // ►►► **Die Liste steht am Feld – aber nicht IN ihm.** ◄◄◄ Sie hängt an `document.body` und
  // steht `fixed` an der gemessenen Stelle des Feldes: kein Vorfahr mit `overflow: hidden`
  // oder eigenem Stapelkontext kann sie schneiden oder überdecken.
  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const below = window.innerHeight - r.bottom - LIST_GAP - LIST_EDGE;
    const above = r.top - LIST_GAP - LIST_EDGE;
    // Nach oben nur, wenn es unten wirklich eng wird.
    const up = below < LIST_MIN && above > below;
    const maxHeight = Math.max(LIST_MIN, Math.min(LIST_MAX, up ? above : below));
    setBox({
      left: r.left, width: r.width, maxHeight,
      top: up ? Math.max(LIST_EDGE, r.top - LIST_GAP - maxHeight) : r.bottom + LIST_GAP,
    });
  }, []);

  // Gemessen wird vor dem Zeichnen (`useLayoutEffect`) – sonst blitzt die Liste oben links auf.
  useLayoutEffect(() => {
    if (!open) { setBox(null); return; }
    measure();
    // `capture: true`, damit auch innere Scroll-Container melden – die Liste wandert mit.
    window.addEventListener('scroll', measure, true);
    window.addEventListener('resize', measure);
    return () => {
      window.removeEventListener('scroll', measure, true);
      window.removeEventListener('resize', measure);
    };
  }, [open, measure]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      // Die Liste ist kein Nachfahre des Feldes – ohne diese zweite Frage schlösse `mousedown`
      // sie, bevor der Klick auf eine Zeile ankommt.
      if (ref.current?.contains(t) || listRef.current?.contains(t)) return;
      setOpen(false); setQuery('');
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  // Esc schliesst – wie überall im Haus.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { setOpen(false); setQuery(''); }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const q = query.trim().toLowerCase();
  const empty = emptyOption ? [{ value: '', label: emptyOption }] : [];
  const filtered = search
    // Serverseitig ist die Antwort die Liste (kein zweiter Filter); die Leer-Zeile bleibt
    // als Rücknahme immer erreichbar.
    ? (q ? [...empty, ...found] : ordered)
    : (q ? ordered.filter((o) => optionText(o).toLowerCase().includes(q)) : ordered);

  function pick(v: string) { onChange(v); setOpen(false); setQuery(''); }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {label && <Label required={required}>{label}</Label>}
      <div style={{ position: 'relative' }}>
        <input
          value={open ? query : (selected ? optionText(selected) : '')}
          placeholder={placeholder ?? '— wählen —'}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onChange={(e) => { setQuery(e.target.value); if (!open) setOpen(true); }}
          className={inputCls}
          style={{ borderColor: 'var(--border-2)', paddingRight: action ? 34 : 28 }}
        />
        {action ? (
          // Die Liste schliesst, bevor die Aktion läuft – sie steht INNERHALB des Feldes,
          // also greift der Klick-daneben-Schliesser nicht.
          <FieldAction {...action}
            onClick={() => { setOpen(false); setQuery(''); action.onClick(); }} />
        ) : open
          ? <Search size={14} style={glyph} />
          : <ChevronDown size={14} style={glyph} />}
      </div>
      {open && box && createPortal(
        <div ref={listRef} style={{ position: 'fixed', zIndex: LIST_Z, left: box.left, top: box.top, width: box.width, maxHeight: box.maxHeight, overflowY: 'auto', background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-sm)', boxShadow: 'var(--shadow-lg)' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 13, color: 'var(--fg-4)' }}>
              {search && !q ? 'Nummer oder Name eingeben' : pending ? 'Sucht …' : 'Keine Treffer'}
            </div>
          ) : filtered.map((o) => (
            <button key={o.value} type="button" onClick={() => pick(o.value)}
              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, border: 'none',
                background: o.value === value ? 'var(--accent-soft)' : 'var(--bg-1)', color: o.value === value ? 'var(--accent-ink)' : 'var(--fg-1)', cursor: 'pointer' }}>
              <OptionRow option={o} />
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}

/**
 * **Die eine Zeilenform einer Datensatz-Auswahl** – identisch im Feld und in der Suchleiste
 * des Scanners (`components/scan/scan-dialog.tsx`). Ohne `name` eine schlichte Zeile.
 */
export function OptionRow({ option }: { option: SelectOption }) {
  if (!option.name) return <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{option.label}</span>;
  return (
    <>
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontVariantNumeric: 'tabular-nums', flex: 'none' }}>{option.label}</span>
      <span style={{ opacity: .75, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{option.name}</span>
    </>
  );
}

const glyph: React.CSSProperties = {
  position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)',
  color: 'var(--fg-4)', pointerEvents: 'none',
};
