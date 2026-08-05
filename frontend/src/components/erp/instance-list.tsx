'use client';

/**
 * **Der Bestand eines Artikels – auf einen Blick** (Testnotiz #600).
 *
 * Die Frage lautet nicht «welche Datensätze gibt es», sondern **«was läuft?»**. Darum drei
 * Entscheidungen, und alle drei folgen aus dem, was seit den Stück-Nummern möglich ist:
 *
 *     Eine Zeile ist ein STÜCK.   Der Zustand gehört zur Menge, nicht zum Datensatz: eine
 *                                 Charge à 4 kann ein verschrottetes, zwei freigegebene
 *                                 und ein laufendes Stück tragen. Genau das ist der Grund,
 *                                 warum FIFO an der Instanz-Badge vorbeischaut – hier steht
 *                                 es Teil für Teil, für Einzelteil und Charge gleich.
 *     Gruppiert statt gefiltert.  Ein Filter versteckt; gefragt war das Gegenteil. Die
 *                                 Zustände stehen untereinander, jeder mit seiner Summe –
 *                                 damit sieht man alles, ohne zu klicken.
 *     FIFO ist die Reihenfolge.   Innerhalb eines Zustands zuerst, was als Nächstes
 *                                 hinausgeht (Freigabe-Datum). Das ist die operative
 *                                 Wahrheit eines Lagers; «neueste zuerst» ist die des Feeds.
 */

import { useEffect, useMemo, useState } from 'react';
import { Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceUnit } from '@/types';
import { instanceStatusConfig, formatQty } from '@/lib/process';
import { instanceStatus } from '@/lib/record-status';

import { useErpNav } from '@/components/erp/obj-id';
import { Placeholder } from '@/components/erp/fields';
import { UnitList } from '@/components/erp/unit-numbers';
import { formatObjectId } from '@/lib/utils';

type Cfg = ReturnType<typeof instanceStatusConfig>;

/** Ein Zustand mit allem, was in ihm liegt – die Gruppe der Liste. */
type Group = { key: string; cfg: Cfg; qty: number; rows: { inst: Instance; units: InstanceUnit[] }[] };

/** Der Zustand EINES Stücks – dieselbe Projektion wie überall (`instanceStatusConfig`). */
function unitCfg(u: InstanceUnit): Cfg {
  return instanceStatusConfig(u.quality, u.disposition, u.order_object_id != null);
}

/**
 * Die Stücke aller Instanzen nach Zustand gruppieren – FIFO innerhalb der Gruppe.
 *
 * Trägt eine Instanz (noch) keine Stück-Daten, steht sie als EIN Eintrag mit ihrer Menge
 * da: tolerant lesen, nie raten.
 */
function group(items: Instance[]): Group[] {
  // **FIFO-Basis ist die Freigabe des STÜCKS** (`in_stock_since`) – dieselbe Zeit, nach der
  // der Server sortiert (`units.fifo_since` → `inventory.fifo_candidates`). Eine Charge kann
  // Teile von heute und von vor vier Wochen tragen; massgeblich ist das älteste, das man
  // ihr entnehmen könnte. Ohne Freigabe (noch im Prozess) gilt die Entstehung.
  const since = (i: Instance) => {
    const t = (i.units ?? []).map((u) => u.in_stock_since).filter(Boolean) as string[];
    return t.length ? t.sort()[0] : String(i.created_at ?? '');
  };
  const fifo = [...items].sort((a, b) =>
    since(a).localeCompare(since(b)) || (a.object_id ?? 0) - (b.object_id ?? 0));
  const out: Group[] = [];
  for (const inst of fifo) {
    const units = inst.units ?? [];
    const buckets = new Map<string, InstanceUnit[]>();
    if (units.length === 0) {
      buckets.set(instanceStatus(inst).label, []);
    } else {
      for (const u of units) {
        const k = unitCfg(u).label;
        buckets.set(k, [...(buckets.get(k) ?? []), u]);
      }
    }
    for (const [key, us] of buckets) {
      const cfg = us.length ? unitCfg(us[0]) : instanceStatus(inst);
      const qty = us.length ? us.reduce((n, u) => n + Number(u.quantity ?? 0), 0)
        : Number(inst.quantity ?? 0);
      const g = out.find((x) => x.key === key);
      if (g) { g.qty += qty; g.rows.push({ inst, units: us }); }
      else out.push({ key, cfg, qty, rows: [{ inst, units: us }] });
    }
  }
  // Gute Zustände zuerst, Probleme zuletzt – dieselbe Ampel-Ordnung wie im Status-Fluss.
  const rank = (c: Cfg) => (c.color === 'var(--success)' ? 0 : c.color === 'var(--warning)' ? 1 : 2);
  return out.sort((a, b) => rank(a.cfg) - rank(b.cfg) || a.key.localeCompare(b.key));
}

export function InstanceList({ articleObjectId, unit }: { articleObjectId: number | null; unit?: string }) {
  const [items, setItems] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(false);
  const nav = useErpNav();

  useEffect(() => {
    if (articleObjectId == null) return;
    setLoading(true);
    api.getArticleInstances(articleObjectId)
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [articleObjectId]);

  const groups = useMemo(() => group(items), [items]);

  if (articleObjectId == null) {
    return <Placeholder icon={Boxes} title="Bestand" text="Artikel zuerst speichern – danach erscheinen hier die Instanzen." />;
  }
  if (loading) {
    return <div style={{ fontSize: 13, color: 'var(--fg-4)', padding: 12 }}>Laden…</div>;
  }
  if (items.length === 0) {
    return <Placeholder icon={Boxes} title="Kein Bestand" text="Instanzen entstehen bei der Serialisierung eines freigegebenen Auftrags." />;
  }

  return (
    <div style={S.wrap}>
      {/* Keine Zusammenfassung darüber (#617): jede Gruppe trägt ihren Zustand und ihre
          Menge bereits im Kopf – eine Zeile, die dieselben Zahlen vorwegnimmt, sagt nichts
          Neues und macht den Bestand nur länger. */}
      {groups.map((g) => (
        <div key={g.key} style={S.group}>
          <div style={{ ...S.head, color: g.cfg.color }}>
            {g.cfg.icon && <g.cfg.icon size={13} style={{ flexShrink: 0 }} />}
            {g.key}
            <span className="ix-tnum" style={S.headQty}>
              {formatQty(g.qty)}{unit ? ` ${unit}` : ''}
            </span>
          </div>
          {g.rows.map(({ inst, units }, idx) => (
            <div key={`${inst.id}-${idx}`} style={{ ...S.row, borderTop: idx === 0 ? 'none' : '1px solid var(--border-1)' }}>
              <button type="button" style={S.obj}
                onClick={() => inst.object_id != null && nav?.(inst.object_id)}>
                {formatObjectId(inst.object_id)}
              </button>
              {units.length > 0 ? (
                <UnitList units={units} unit={unit} max={12} onOpen={(id) => nav?.(id)} />
              ) : (
                <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>
                  {formatQty(Number(inst.quantity ?? 0))}{unit ? ` ${unit}` : ''}
                </span>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  wrap: { maxWidth: 980, marginInline: 'auto', display: 'flex', flexDirection: 'column', gap: 14 },
  group: {
    border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', background: '#fff',
    overflow: 'hidden',
  },
  head: {
    display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px',
    font: '700 12px var(--font-body)', letterSpacing: '0.02em', textTransform: 'uppercase',
    borderBottom: '1px solid var(--border-1)', background: 'var(--bg-2)',
  },
  headQty: { marginLeft: 'auto', color: 'var(--fg-3)', fontWeight: 600, textTransform: 'none', letterSpacing: 0 },
  row: { display: 'flex', alignItems: 'flex-start', gap: 14, padding: '10px 16px' },
  obj: {
    font: 'var(--mono-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)',
    border: 'none', background: 'none', padding: 0, cursor: 'pointer', flex: 'none',
    lineHeight: 1.5,
  },
};
