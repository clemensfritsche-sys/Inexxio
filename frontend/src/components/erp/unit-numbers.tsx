'use client';

/**
 * **Ein Stück wird überall gleich genannt** – Nummer · Menge · Zustand (Testnotizen
 * #531/#532).
 *
 * Eine Charge war eine Menge unter EINER Nummer; welches Stück gemeint war, liess sich
 * nicht sagen. Jetzt trägt jedes Teil seine eigene, etikettierbare Nummer (`services/
 * units.py`) – **ohne Ausnahme**, auch ein Einzelteil (`…-1`). Und weil dieselbe Aussage
 * an vielen Stellen auftaucht (Instanz-Detail, Auswahl, Positionen, Prozess-Kante), steht
 * sie hier EINMAL, in zwei Dichten derselben Zeile:
 *
 *     UnitList   untereinander, ausgeschrieben – wo Platz ist (Instanz-Detail, Fluss)
 *     UnitChips  nebeneinander, kompakt – als Zusatz zu einer Zeile, die Menge und
 *                Zustand schon nennt (Auswahl, Positionen)
 *
 * Die Ampelfarbe kommt aus derselben Projektion wie überall (`instanceStatusConfig`) –
 * kein zweites Regelwerk.
 */

import type { InstanceUnit } from '@/types';
import { instanceStatusConfig } from '@/lib/process';
import { formatObjectId } from '@/lib/utils';

/** Die Nummer lesbar machen: die Objektnummer 9-stellig, der Zusatz bleibt, wie er ist. */
export function unitLabel(n: string): string {
  const [obj, suffix] = n.split('-');
  const head = /^\d+$/.test(obj) ? formatObjectId(Number(obj)) : obj;
  return suffix ? `${head}-${suffix}` : head;
}

/** Der Zustand eines Stücks – dieselbe Projektion wie an der Instanz selbst. */
function cfgOf(u: InstanceUnit) {
  return instanceStatusConfig(u.quality, u.disposition, u.order_object_id != null);
}

/** Die drei Angaben als Satz – für den Hover, wo nur eine Zeile Platz hat. */
function tip(u: InstanceUnit, unit?: string): string {
  const cfg = cfgOf(u);
  const qty = `${u.quantity}${unit ? ` ${unit}` : ''}`;
  const holder = u.order_object_id != null
    ? ` · Auftrag ${formatObjectId(u.order_object_id)}` : '';
  return `${unitLabel(u.number)} · ${qty} · ${cfg.label}${holder}`;
}

const S: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center', minWidth: 0 },
  chip: {
    display: 'inline-flex', alignItems: 'center', gap: 3,
    fontSize: 10.5, fontWeight: 600, lineHeight: 1.4, letterSpacing: '0.01em',
    fontVariantNumeric: 'tabular-nums', padding: '1px 5px', borderRadius: 4,
    border: '1px solid var(--border-1)', whiteSpace: 'nowrap',
  },
  more: { fontSize: 10.5, fontWeight: 600, color: 'var(--fg-4)', whiteSpace: 'nowrap' },
  list: { display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 },
  row: {
    display: 'grid', gridTemplateColumns: 'auto auto 1fr', gap: 8, alignItems: 'center',
    fontSize: 12, lineHeight: 1.5,
  },
  num: { font: 'var(--mono-sm)', color: 'var(--fg-2)', whiteSpace: 'nowrap' },
  qty: { fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)', whiteSpace: 'nowrap' },
  state: { display: 'inline-flex', alignItems: 'center', gap: 4, minWidth: 0 },
};

/**
 * **Die Stücke als Liste** – eine Zeile je Teil: Nummer · Menge · Zustand, aufsteigend
 * nach Nummer. Das ist die vollständige Form; sie steht dort, wo Platz ist.
 */
export function UnitList({
  units, unit, max, style, onOpen,
}: {
  units?: InstanceUnit[] | null;
  /** Mengeneinheit des Artikels (Stk, kg …). */
  unit?: string;
  /** Ab wie vielen Zeilen der Rest hinter «alle N anzeigen» liegt. */
  max?: number;
  style?: React.CSSProperties;
  /** Klick auf den Halter – öffnet dessen Datensatz. */
  onOpen?: (objectId: number) => void;
}) {
  const all = units ?? [];
  if (!all.length) return null;
  const shown = max != null && all.length > max ? all.slice(0, max) : all;
  return (
    <div style={{ ...S.list, ...style }}>
      {shown.map((u) => {
        const cfg = cfgOf(u);
        const Icon = cfg.icon;
        return (
          <div key={u.number} style={S.row} title={tip(u, unit)}>
            <span style={S.num}>{unitLabel(u.number)}</span>
            <span style={S.qty}>{u.quantity}{unit ? ` ${unit}` : ''}</span>
            <span style={{ ...S.state, color: cfg.color }}>
              {Icon && <Icon size={12} style={{ flexShrink: 0 }} />}
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{cfg.label}</span>
              {u.order_object_id != null && (
                <button type="button"
                  onClick={(e) => { e.stopPropagation(); onOpen?.(u.order_object_id as number); }}
                  style={{
                    font: 'var(--mono-sm)', color: 'var(--fg-4)', border: 'none',
                    background: 'none', padding: 0, cursor: onOpen ? 'pointer' : 'default',
                  }}>
                  {formatObjectId(u.order_object_id)}
                </button>
              )}
            </span>
          </div>
        );
      })}
      {shown.length < all.length && (
        <span style={S.more}>+{all.length - shown.length} weitere</span>
      )}
    </div>
  );
}

/**
 * **Die Stücke kompakt** – als Zusatz zu einer Zeile, die Menge und Zustand bereits nennt.
 * Der Chip trägt die Nummer und die Ampelfarbe; die Menge steht nur dabei, wenn sie etwas
 * sagt (eine nicht zählbare Charge trägt hier 2.5, ein Stück trägt 1 und schweigt).
 */
export function UnitChips({
  units, count, unit, max = 6, style,
}: {
  units?: InstanceUnit[] | null;
  /** Wie viele es insgesamt sind – die Liste ist serverseitig gekappt. */
  count?: number | null;
  unit?: string;
  max?: number;
  style?: React.CSSProperties;
}) {
  const all = units ?? [];
  if (!all.length) return null;
  const total = count ?? all.length;
  const shown = all.slice(0, max);
  const rest = total - shown.length;
  return (
    <span style={{ ...S.wrap, ...style }}>
      {shown.map((u) => {
        const cfg = cfgOf(u);
        return (
          <span key={u.number} title={tip(u, unit)}
            style={{ ...S.chip, background: cfg.bg, color: cfg.color }}>
            {unitLabel(u.number)}
            {u.quantity !== 1 && <span style={{ opacity: 0.8 }}>×{u.quantity}</span>}
          </span>
        );
      })}
      {rest > 0 && <span style={S.more}>+{rest}</span>}
    </span>
  );
}
