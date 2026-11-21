'use client';

import { useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { qk } from '@/lib/queries';
import { ScanLine } from 'lucide-react';
import { SearchSelect, type SelectOption } from '@/components/erp/search-select';
import { useScan } from '@/components/scan/scan-provider';
import { LOOKUP_HINT, lookupHint, type ScanKind } from '@/lib/scan';
import { formatObjectId } from '@/lib/utils';
import { tell } from '@/lib/notice';

/** **Die Form, in der ein Datensatz genannt wird** – die der API (`object_id`); ein anders
 *  benanntes Namensfeld reicht der Aufrufer in `find` als `name` durch. */
interface ObjectOption {
  object_id: number;
  /** Wie der Datensatz heisst – **ohne** Nummer, die setzt dieses Feld davor. */
  name: string;
}

/**
 * **Das eine Referenzfeld: «welchen Datensatz meinst du?»** – gebaut auf `SearchSelect`.
 * Tippen sucht auf dem **Server** (Nummer oder Name, `services/lookup`), die **Kamera** sitzt
 * im Feld (`SearchSelect.action`); beide führen zur selben Wahl. Der Scanner ist dasselbe
 * Feld, nur gross (Platzhalter {@link LOOKUP_HINT}, Zeilenform, «nichts»-Zeile).
 *
 * Das Feld hält keinen eigenen Zustand: `value` ist die Nummer, `selected` der bekannte
 * Datensatz dazu. ►► **Kennt der Aufrufer ihn nicht** (vorausgefüllt aus einem Vorschlag, aus der
 * Adresse, aus einem Entwurf), fragt das Feld seine eigene Suche nach der Nummer – dieselbe wie
 * beim Tippen und Scannen. So steht jede Nummer mit ihrem Namen da, gleich woher sie kam. ◄◄
 */
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
  /** Was der Scanner im Zielrahmen nennt – die **Sorte**, nie eine Nummer. */
  scanLabel?: string;
  disabled?: boolean;
}) {
  const scan = useScan();
  // Die Nummer ohne bekannten Datensatz: einmal über die eigene Suche benennen.
  const unnamed = value != null && selected?.object_id !== value ? value : null;
  const named = useQuery({
    queryKey: qk.catalog('object-name', kind ?? '', label ?? '', unnamed),
    queryFn: () => find(String(unnamed)).then((rows) => rows.find((o) => o.object_id === unnamed) ?? null),
    enabled: unnamed != null,
    staleTime: Infinity,
    meta: { what: 'Name des Datensatzes' },
  });
  const known = selected?.object_id === value ? selected : named.data ?? null;

  // Nummer und Name getrennt übergeben, damit `SearchSelect` sie auszeichnen kann.
  const row = (o: ObjectOption): SelectOption => ({
    value: String(o.object_id),
    label: formatObjectId(o.object_id),
    name: o.name || undefined,
  });

  // Was gerade in der Liste steht, damit ein Klick die volle Option mitgibt (ein `ref`:
  // nur beim Klick gelesen, nie gerendert).
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

  /** **Der Scanner ist dieses Feld, nur gross**: dieselbe Suche, Existenzprüfung und «nichts»-Zeile. */
  function openScanner() {
    scan({
      steps: [{
        label: scanLabel ?? label ?? 'Objekt',
        kind,
        suggest: (q: string) => find(q)
          .then((rows) => rows.map((o) => ({ objectId: o.object_id, label: o.name }))),
        // Was es nicht gibt, kommt nicht durch.
        exists: (id: number) => find(String(id))
          .then((rows) => rows.some((o) => o.object_id === id)),
        emptyOption: emptyOption ? { label: emptyOption, pick: () => onChange(null, null) } : undefined,
      }],
      onComplete: (ids) => {
        const id = ids[0];
        if (id == null) return;
        find(String(id))
          .then((rows) => onChange(id, rows.find((o) => o.object_id === id) ?? null))
          .catch((e: unknown) => { tell('Name des Datensatzes')(e); onChange(id, null); });
      },
    });
  }

  return (
    <SearchSelect
      label={label}
      required={required}
      value={value == null ? '' : String(value)}
      onChange={pick}
      options={known ? [row(known)]
        : value != null ? [{ value: String(value), label: formatObjectId(value) }]
          : []}
      search={search}
      emptyOption={emptyOption}
      // ►►► **Die Sorte steht GENAU EINMAL** ◄◄◄ – in der Beschriftung, sonst im Platzhalter.
      placeholder={placeholder ?? (label ? LOOKUP_HINT : lookupHint(scanLabel))}
      action={{
        icon: <ScanLine size={15} />,
        label: 'Scannen',
        disabled,
        onClick: openScanner,
      }}
    />
  );
}
