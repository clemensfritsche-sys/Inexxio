'use client';

import { useCallback, useRef } from 'react';
import { ScanLine } from 'lucide-react';
import { SearchSelect, type SelectOption } from '@/components/erp/fields';
import { useScan } from '@/components/scan/scan-provider';
import { LOOKUP_HINT, type ScanKind } from '@/lib/scan';
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
 * **Nebeneinander heisst aber nicht zwei Bedienelemente.** Die Kamera sitzt am rechten
 * **Innenrand des Feldes** (`SearchSelect.action`) statt als eigener Knopf daneben: EIN
 * Bedienelement mit zwei Eingängen. Sie ersetzt dort das Zierzeichen – dass es eine Liste
 * gibt, sagt der Klick, und eine echte Aktion ist den Platz wert.
 *
 * **Und der Dialog ist sichtbar dasselbe Feld, nur gross:** derselbe Platzhalter
 * ({@link LOOKUP_HINT}), dieselbe Zeilenform (`100000123 · Regal B`, Nummer tabellarisch)
 * und dieselbe «nichts»-Zeile. Sie kommen nicht aus zwei Formulierungen, sondern aus
 * einer – sonst liefe die Frage «warum gibt es das zweimal» wieder auf.
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

  // **Die Zeile des Scanners**: Nummer als Hauptangabe, Name leise daneben. Getrennt
  // übergeben, damit `SearchSelect` sie auszeichnen kann – als fertiger String wäre die
  // Nummer nur Text, und die beiden Oberflächen sähen wieder verschieden aus.
  const row = (o: ObjectOption): SelectOption => ({
    value: String(o.object_id),
    label: formatObjectId(o.object_id),
    name: o.name || undefined,
  });

  // **Was gerade in der Liste steht**, damit ein Klick die volle Option mitgibt – sie
  // steckt in der Antwort, die der Nutzer ansieht, und muss nicht erneut geholt werden.
  // Bewusst ein `ref`: es wird nur beim Klick gelesen und nie gerendert; als State löste
  // jede Tastatureingabe ein zweites Rendern aus.
  const shown = useRef<T[]>([]);

  const search = useCallback(
    (q: string) => find(q).then((rows) => {
      shown.current = rows;
      return rows.map(row);
    }),
    [find],
  );

  function pick(v: string) {
    if (!v) { onChange(null, null); return; }
    const id = Number(v);
    onChange(id, shown.current.find((o) => o.object_id === id) ?? null);
  }

  /**
   * **Der Scanner ist dieses Feld, nur gross** – also bekommt er alles, was das Feld hat:
   * dieselbe Suche, dieselbe Existenzprüfung und dieselbe «nichts»-Zeile. Fehlte Letztere,
   * müsste man ihn schliessen, um eine Entscheidung zu treffen, die daneben in der Liste
   * steht.
   */
  function openScanner() {
    scan({
      steps: [{
        // **Die Sorte, nie die Nummer** – die baut der Scanner selbst (#737).
        label: scanLabel ?? label ?? 'Objekt',
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
        emptyOption: emptyOption ? { label: emptyOption, pick: () => onChange(null, null) } : undefined,
      }],
      onComplete: (ids) => {
        const id = ids[0];
        if (id == null) return;
        find(String(id))
          .then((rows) => onChange(id, rows.find((o) => o.object_id === id) ?? null))
          .catch(() => onChange(id, null));
      },
    });
  }

  return (
    <SearchSelect
      label={label}
      required={required}
      value={value == null ? '' : String(value)}
      onChange={pick}
      options={selected ? [row(selected)]
        : value != null ? [{ value: String(value), label: formatObjectId(value) }]
          : []}
      search={search}
      emptyOption={emptyOption}
      placeholder={placeholder ?? LOOKUP_HINT}
      action={{
        icon: <ScanLine size={15} />,
        label: 'Scannen',
        disabled,
        onClick: openScanner,
      }}
    />
  );
}
