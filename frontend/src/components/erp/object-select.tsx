'use client';

import { useCallback, useRef } from 'react';
import { ScanLine } from 'lucide-react';
import { SearchSelect } from '@/components/erp/fields';
import { useScan } from '@/components/scan/scan-provider';
import type { ScanKind } from '@/lib/scan';
import { formatObjectId } from '@/lib/utils';

/**
 * **Das eine Referenzfeld: «welchen Datensatz meinst du?»**
 *
 * Es gab dieselbe Frage in **vier** Bauarten – ein Auswahlfeld mit Server-Suche, eines mit
 * fertigen Optionen, ein natives `<select>` über alle Artikel des Hauses (nicht
 * durchsuchbar, tausend Knoten je Zeile) und den Scanner mit seiner eigenen Suche. Wer
 * «100000743» tippte, fand je nach Stelle etwas oder nichts (Testnotiz #738).
 *
 * Hier ist es eines: tippen sucht auf dem **Server** – Nummer **oder** Name, dieselbe
 * Bedingung, die das Backend an jeder Stelle stellt (`services/lookup`) –, und rechts im
 * Feld steht die **Kamera**. Beide Wege führen zur selben Wahl.
 *
 * **Kamera und Tastatur stehen nebeneinander, keines ersetzt das andere.** Der Scanner
 * zuerst und die Eingabe darunter wäre am Band richtig und am Schreibtisch ein Umweg;
 * umgekehrt genauso. Wer scannt, trifft; wer tippt, sucht – und der Scanner bekommt
 * dieselbe Suche mit (`suggest`), damit auch dort «00787» etwas findet.
 *
 * **Gebaut AUF `SearchSelect`, nicht daneben.** Ein zweites Auswahlfeld wäre der erste
 * Weg, der beim nächsten Feld ausläuft; hier kommt nur die Kamera dazu.
 *
 * **Wer die Wahl besitzt, besitzt auch ihre Angaben.** Das Feld hält keinen eigenen
 * Zustand: `value` ist die Nummer (die Wahrheit des Entwurfs), `selected` der bekannte
 * Datensatz dazu. Ein Aufrufer, der ohnehin mehr über ihn wissen muss (Serialisierung,
 * Vorlage, Grund), lädt ihn genau einmal – statt dass dieses Feld ihn ein zweites Mal holt.
 */
/**
 * **Die Form, in der ein Datensatz genannt wird** – bewusst die der API (`object_id`),
 * nicht eine eigene: eine zweite Schreibweise wäre eine Übersetzung an jeder Aufrufstelle,
 * und `ArticleOption` & Co. passen so ohne eine Zeile Umbau.
 *
 * Wer sein Namensfeld anders nennt (`PlaceRef.label`), reicht es in `find` als `name`
 * durch – ein Mapping, das dort steht, wo der Unterschied entsteht.
 */
export interface ObjectOption {
  object_id: number;
  /** Wie der Datensatz heisst – **ohne** Nummer, die setzt dieses Feld davor. */
  name: string;
}

export function ObjectSelect<T extends ObjectOption>({
  label, value, selected, onChange, find, kind, placeholder, emptyOption, required,
  scanLabel, disabled,
}: {
  label?: string;
  /** Objektnummer des gewählten Datensatzes – `null`, solange keiner gewählt ist. */
  value: number | null;
  /** Der gewählte Datensatz, soweit bekannt. Fehlt er, steht nur die Nummer da – nie ein
   *  erfundener Name. */
  selected?: T | null;
  onChange: (objectId: number | null, option: T | null) => void;
  /** **Worin gesucht wird.** Der Aufrufer besitzt die Suche – dieses Feld baut keine zweite. */
  find: (query: string) => Promise<T[]>;
  /** Erwarteter Objekttyp → Symbol im Scanner. */
  kind?: ScanKind;
  placeholder?: string;
  /** Steht «nichts» zur Wahl, gehört es in die Liste – siehe `SearchSelect.emptyOption`. */
  emptyOption?: string;
  required?: boolean;
  /** Was der Scanner im Zielrahmen nennt – die **Sorte**, nie eine Nummer (#737). */
  scanLabel?: string;
  disabled?: boolean;
}) {
  const scan = useScan();

  const text = (o: ObjectOption) =>
    o.name ? `${formatObjectId(o.object_id)} · ${o.name}` : formatObjectId(o.object_id);

  // **Was gerade in der Liste steht**, damit ein Klick die volle Option mitgibt – sie
  // steckt in der Antwort, die der Nutzer ansieht, und muss nicht erneut geholt werden.
  // Bewusst ein `ref`: es wird nur beim Klick gelesen und nie gerendert; als State löste
  // jede Tastatureingabe ein zweites Rendern aus.
  const shown = useRef<T[]>([]);

  const search = useCallback(
    (q: string) => find(q).then((rows) => {
      shown.current = rows;
      return rows.map((o) => ({ value: String(o.object_id), label: text(o) }));
    }),
    [find],
  );

  function pick(v: string) {
    if (!v) { onChange(null, null); return; }
    const id = Number(v);
    onChange(id, shown.current.find((o) => o.object_id === id) ?? null);
  }

  return (
    <div className="flex items-end gap-2">
      <div className="flex-1 min-w-0">
        <SearchSelect
          label={label}
          required={required}
          value={value == null ? '' : String(value)}
          onChange={pick}
          options={selected ? [{ value: String(selected.object_id), label: text(selected) }]
            : value != null ? [{ value: String(value), label: formatObjectId(value) }]
              : []}
          search={search}
          emptyOption={emptyOption}
          placeholder={placeholder ?? 'Objektnummer oder Name'}
        />
      </div>
      <button
        type="button"
        className="erp-idbtn"
        data-tip="Scannen"
        aria-label="Scannen"
        disabled={disabled}
        onClick={() => scan({
          steps: [{
            // **Die Sorte, nie die Nummer** – die hängt der Scanner selbst an (#737).
            label: scanLabel ?? label ?? 'Objektnummer',
            kind,
            // **Dieselbe Suche wie im Feld daneben** (#730/#732): ein freier Scan-Schritt
            // ohne Vorschlagsquelle bietet nichts an – wer «00787» tippt, sieht nichts,
            // obwohl es die Nummer gibt.
            suggest: (q: string) => find(q)
              .then((rows) => rows.map((o) => ({ objectId: o.object_id, label: o.name })))
              .catch(() => []),
            // **Was es nicht gibt, kommt nicht durch**: sonst wird der Rahmen grün und
            // beim Aufrufer passiert stillschweigend nichts.
            exists: (id: number) => find(String(id))
              .then((rows) => rows.some((o) => o.object_id === id))
              .catch(() => false),
          }],
          onComplete: (ids) => {
            const id = ids[0];
            if (id == null) return;
            find(String(id))
              .then((rows) => onChange(id, rows.find((o) => o.object_id === id) ?? null))
              .catch(() => onChange(id, null));
          },
        })}
      >
        <ScanLine size={15} />
      </button>
    </div>
  );
}
