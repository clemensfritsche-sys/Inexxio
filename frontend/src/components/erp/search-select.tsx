'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { useSearch } from '@/lib/use-search';
import { FieldAction, Label, inputCls } from '@/components/erp/controls';

/**
 * **Eine Zeile der Auswahl – und ihre Form ist die des Scanners.**
 *
 * `label` ist die Hauptangabe (bei einem Datensatz seine Objektnummer), `name` die leise
 * daneben. Getrennt, weil dieselbe Zeile in **beiden** Oberflächen gleich aussehen soll:
 * `100000123 · Regal B`, die Nummer tabellarisch, der Name gedämpft. Als ein fertiger
 * String liesse sich das nicht auszeichnen – und der Dialog sähe anders aus als das Feld,
 * aus dem er kommt.
 *
 * Ohne `name` bleibt alles wie bisher: eine schlichte Zeile (Aufzählungen, «nichts»).
 */
export interface SelectOption { value: string; label: string; name?: string }

/** Wie eine Zeile als **Text** aussieht – im geschlossenen Feld und beim Filtern. */
const optionText = (o: SelectOption) => (o.name ? `${o.label} · ${o.name}` : o.label);

/** Durchsuchbare Referenz-Auswahl (Combobox). Filtert Optionen per Tippen –
 *  z. B. «003» findet die Objektnummer 100000003. */
/**
 * Neueste zuerst: Datensatz-Auswahlen zeigen die **grösste Nummer oben**. Objektnummern
 * werden aufsteigend vergeben – wer einen Datensatz referenziert, meint fast immer einen
 * der zuletzt angelegten, nicht den ältesten von tausend. Greift nur, wenn ALLE Werte
 * Zahlen sind (sonst bleibt die vom Aufrufer gewählte Reihenfolge unangetastet).
 */
function newestFirst(options: SelectOption[]): SelectOption[] {
  const isNum = (v: string) => v !== '' && Number.isFinite(Number(v));
  const numeric = options.filter((o) => isNum(o.value));
  // Nicht-numerische Einträge sind Platzhalter («— wählen —», «Standard erben») und
  // bleiben vorn. Mehr als einer davon heisst: die Liste ist gemischt (z. B. Standort-
  // Ziele wie `user:100000002`) – dann bleibt die Reihenfolge des Aufrufers unangetastet.
  const others = options.filter((o) => !isNum(o.value));
  if (numeric.length < 2 || others.length > 1) return options;
  return [...others, ...numeric.sort((a, b) => Number(b.value) - Number(a.value))];
}

/** Wo die Vorschlagsliste steht – in Bildschirm-Koordinaten, weil sie `fixed` hängt. */
type ListBox = { left: number; top: number; width: number; maxHeight: number };

// Die Masse der Liste an EINER Stelle. `LIST_Z` liegt über dem Dialog des Hauses (60) und
// unter dem Scan-Vollbild (100): eine Wahl, die sich über den Scanner legte, verdeckte
// genau das Bild, aus dem sie entsteht.
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
   * **Eine Handlung AM Feld, nicht daneben.**
   *
   * Sie sitzt am rechten Innenrand und ersetzt dort das Zierzeichen (Chevron ↔ Lupe):
   * ein Bedienelement mit zwei Eingängen statt zweier Bedienelemente für eine Frage. Der
   * Chevron sagt «hier ist eine Liste» – dasselbe sagt der Klick, und er sagt es beim
   * Ausprobieren; eine echte Aktion ist der Platz wert.
   *
   * Ohne die Angabe bleibt alles wie bisher.
   */
  action?: { icon: ReactNode; label: string; onClick: () => void; disabled?: boolean };
  /**
   * **«Nichts» ist eine Wahl – also steht sie in der Liste.**
   *
   * Ist dieser Text gesetzt, führt die Liste ihn als **erste Zeile** mit dem Wert `''`,
   * und ein leeres Feld zeigt ihn an, statt einen Platzhalter zu zeigen. Damit steht die
   * getroffene Entscheidung da, nicht ihr Fehlen.
   *
   * Es ersetzt drei Notbehelfe, die sonst nebeneinander wachsen: einen erklärenden
   * Platzhalter («leer lassen für …»), einen Erklärsatz darunter und einen
   * X-Knopf daneben, mit dem man eine Wahl wieder wegnimmt. Drei Stellen für eine
   * Aussage – und keine davon ist die Liste, in der man wählt (Testnotizen #734–#736).
   *
   * Ohne die Angabe bleibt alles wie bisher: leer heisst «noch nicht gewählt».
   */
  emptyOption?: string;
  /**
   * **Wo die Auswahl zu gross für eine Liste ist: suchen statt mitgeben.**
   *
   * Ohne diese Angabe bleibt alles wie bisher – die Optionen kommen fertig, gefiltert
   * wird im Browser. Mit ihr fragt das Feld beim Tippen den Server; `options` trägt dann
   * nur noch die **gewählte** Option, damit die Anzeige stimmt.
   *
   * Dieselbe Bauart wie beim Scanner (`candidates` ↔ `suggest`): eine Komponente, zwei
   * Quellen. Ein zweites Auswahlfeld «mit Suche» wäre ein zweiter Weg zu derselben Sache
   * – und der erste, der beim nächsten Feld auseinanderläuft.
   */
  search?: (query: string) => Promise<SelectOption[]>;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<ListBox | null>(null);
  // Die Leer-Zeile steht **vor** der Sortierung und bleibt vorn: `newestFirst` lässt
  // nicht-numerische Werte ohnehin an Ort und Stelle.
  const all = emptyOption ? [{ value: '', label: emptyOption }, ...options] : options;
  const selected = all.find((o) => o.value === value);
  const ordered = newestFirst(all);

  // Entprellt, mit Veralterungs-Schutz – die eine Suche des Hauses (`useSearch`).
  const { hits: found, pending } = useSearch(query, search);

  // ►►► **Die Liste steht am Feld – aber nicht IN ihm** (Testnotiz #909). ◄◄◄
  //
  // Gemeldet war: *«wenn ich hier etwas suche und auswählen möchte, dann geht das nicht
  // wirklich gut, da es von der Ebene her zu tief ist.»* – Sie lag als
  // `position: absolute` **im** Feld und damit in jedem Rahmen darüber: ein Vorfahr mit
  // `overflow: hidden` schnitt sie ab, ein Nachbar mit höherem Stapelplatz legte sich
  // darüber. `z-index` hilft dagegen nicht: er gilt nur **innerhalb** des Stapelkontexts,
  // in dem das Element steht – und einen solchen erzeugt jede Karte mit `transform`,
  // `filter` oder eigenem `z-index`.
  //
  // Also verlässt die Liste den Baum: sie hängt an `document.body` und steht `fixed` an
  // der gemessenen Stelle des Feldes. Damit gibt es keinen Vorfahren mehr, der sie
  // schneiden oder überdecken könnte – die Robustheit ist konstruktiv statt geprüft.
  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const below = window.innerHeight - r.bottom - LIST_GAP - LIST_EDGE;
    const above = r.top - LIST_GAP - LIST_EDGE;
    // **Nach oben nur, wenn es unten wirklich eng wird** – ein Feld, dessen Liste mal so
    // und mal so aufklappt, lässt sich nicht blind bedienen.
    const up = below < LIST_MIN && above > below;
    const maxHeight = Math.max(LIST_MIN, Math.min(LIST_MAX, up ? above : below));
    setBox({
      left: r.left, width: r.width, maxHeight,
      top: up ? Math.max(LIST_EDGE, r.top - LIST_GAP - maxHeight) : r.bottom + LIST_GAP,
    });
  }, []);

  // **Gemessen wird VOR dem Zeichnen** (`useLayoutEffect`) – sonst blitzt die Liste
  // einen Bild lang an der linken oberen Ecke auf.
  useLayoutEffect(() => {
    if (!open) { setBox(null); return; }
    measure();
    // `capture: true`, damit auch **innere** Scroll-Container melden: die Karte scrollt,
    // das Feld wandert, die Liste muss mit. Ohne das bliebe sie stehen, wo sie war.
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
      // Die Liste ist **kein** Nachfahre des Feldes mehr – ohne diese zweite Frage
      // schlösse `mousedown` sie, bevor der Klick auf eine Zeile ankommt: die Zeile wäre
      // aus dem Baum, das `click`-Ereignis fiele aus, und die Wahl ginge ins Leere.
      if (ref.current?.contains(t) || listRef.current?.contains(t)) return;
      setOpen(false); setQuery('');
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  // **Esc schliesst** – dieselbe Taste wie überall im Haus; eine Liste, die über allem
  // liegt, braucht einen Weg heraus, der keine Maus verlangt.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { setOpen(false); setQuery(''); }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const q = query.trim().toLowerCase();
  // Sucht das Feld serverseitig, ist die Antwort die Liste – ein zweiter Filter darüber
  // würde wegwerfen, was der Server gerade als Treffer benannt hat.
  const empty = emptyOption ? [{ value: '', label: emptyOption }] : [];
  const filtered = search
    // Sucht das Feld serverseitig, ist die Antwort die Liste – ein zweiter Filter darüber
    // würde wegwerfen, was der Server gerade als Treffer benannt hat. Die Leer-Zeile ist
    // keine Server-Antwort und bleibt darum immer erreichbar: sie ist die Rücknahme.
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
 * **Die eine Zeilenform einer Datensatz-Auswahl.**
 *
 * Nummer tabellarisch und kräftig, Name leise daneben – identisch im Feld und in der
 * Suchleiste des Scanners (`components/scan/scan-dialog.tsx`). Wer hier etwas ändert,
 * ändert es dort mit; deshalb steht sie als Bauteil da und nicht zweimal als JSX.
 *
 * Ohne `name` ist es eine schlichte Zeile – die «nichts»-Wahl etwa ist keine Nummer und
 * sieht darum auch nicht wie eine aus.
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
