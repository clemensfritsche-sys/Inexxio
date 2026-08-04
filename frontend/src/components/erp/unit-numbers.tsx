'use client';

/**
 * **Die Nummern der einzelnen Stücke** – 100000101-1 … -4.
 *
 * Eine Charge war bisher eine Menge unter EINER Nummer; welches Stück gemeint war, liess
 * sich nicht sagen. Jetzt trägt jedes seine eigene, etikettierbare Nummer (`services/
 * units.py`) – und weil dieselbe Aussage an vielen Stellen auftaucht (Instanz-Detail,
 * Auswahl, Positionen, Prozess-Kante), steht sie hier EINMAL.
 *
 * Gezeigt wird, was hineinpasst; der Rest steht als «+N» daneben und vollständig im Hover.
 * Bei genau einem Stück ist die Nummer die Objektnummer selbst – dann gibt es nichts zu
 * unterscheiden, und die Zeile nennt sie ohnehin schon (`hideSingle`).
 */

import { formatObjectId } from '@/lib/utils';

const S: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center', minWidth: 0 },
  chip: {
    fontSize: 10.5, fontWeight: 600, lineHeight: 1.4, letterSpacing: '0.01em',
    fontVariantNumeric: 'tabular-nums', padding: '1px 5px', borderRadius: 4,
    background: 'var(--bg-3)', color: 'var(--fg-3)', border: '1px solid var(--border-1)',
    whiteSpace: 'nowrap',
  },
  more: { fontSize: 10.5, fontWeight: 600, color: 'var(--fg-4)', whiteSpace: 'nowrap' },
};

/** Die Nummer lesbar machen: die Objektnummer 9-stellig, der Zusatz bleibt, wie er ist. */
function pretty(n: string): string {
  const [obj, suffix] = n.split('-');
  const head = /^\d+$/.test(obj) ? formatObjectId(Number(obj)) : obj;
  return suffix ? `${head}-${suffix}` : head;
}

export function UnitNumbers({
  units,
  count,
  max = 6,
  hideSingle = false,
  style,
}: {
  units?: string[] | null;
  /** Wie viele es insgesamt sind – die Liste ist serverseitig gekappt. */
  count?: number | null;
  max?: number;
  /** Bei genau einem Stück nichts zeigen (die Zeile nennt die Objektnummer bereits). */
  hideSingle?: boolean;
  style?: React.CSSProperties;
}) {
  const all = units ?? [];
  const total = count ?? all.length;
  if (!all.length || (hideSingle && total <= 1)) return null;
  const shown = all.slice(0, max);
  const rest = total - shown.length;
  return (
    <span style={{ ...S.wrap, ...style }} title={all.map(pretty).join(' · ')}>
      {shown.map((n) => (
        <span key={n} style={S.chip}>{pretty(n)}</span>
      ))}
      {rest > 0 && <span style={S.more}>+{rest}</span>}
    </span>
  );
}
