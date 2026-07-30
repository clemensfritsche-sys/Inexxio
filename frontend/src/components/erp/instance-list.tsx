'use client';

import { useEffect, useState } from 'react';
import { Boxes, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance } from '@/types';
import { instanceStatusConfig, instanceLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { useErpNav } from '@/components/erp/obj-id';
import { StatusBadge, Placeholder } from '@/components/erp/fields';
import { TYPE_META } from '@/lib/erp-record';

// Farbidentität des Datensatztyps aus der EINEN Quelle (statt hier hart kodiert).
const INST = TYPE_META.instance;

export function InstanceList({ articleObjectId, unit }: { articleObjectId: number | null; unit?: string }) {
  const [items, setItems] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(false);
  // Dezenter Status-Filter (Notiz #288, analog zum Typ-Filter im ERP-Feed) – null = «Alle».
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const nav = useErpNav();

  useEffect(() => {
    if (articleObjectId == null) return;
    setLoading(true);
    setStatusFilter(null);   // beim Artikelwechsel den Filter zurücksetzen
    api.getArticleInstances(articleObjectId)
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [articleObjectId]);

  const statusOf = (i: Instance) =>
    instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0);

  if (articleObjectId == null) {
    return <Placeholder icon={Boxes} title="Bestand" text="Artikel zuerst speichern – danach erscheinen hier die Instanzen." />;
  }
  if (loading) {
    return <div style={{ fontSize: 13, color: 'var(--fg-4)', padding: 12 }}>Laden…</div>;
  }
  if (items.length === 0) {
    return <Placeholder icon={Boxes} title="Kein Bestand" text="Instanzen entstehen bei der Serialisierung eines freigegebenen Auftrags." />;
  }

  // **Neueste zuerst** (wie im Feed: Objektnummern werden aufsteigend vergeben, gemeint ist
  // fast immer die zuletzt entstandene Instanz). Ein Suchfeld gab es hier zwischenzeitlich –
  // es ist wieder entfallen (Notiz #157): der Bestand EINES Artikels ist die kurze Liste, für
  // die es keine Suche braucht; gesucht wird im Feed.
  const sorted = [...items].sort((a, b) => (b.object_id ?? 0) - (a.object_id ?? 0));

  // Vorhandene Status (in stabiler Reihenfolge) + Anzahl je Status – für die Filter-Chips.
  const groups: { label: string; cfg: ReturnType<typeof statusOf>; count: number }[] = [];
  for (const i of sorted) {
    const cfg = statusOf(i);
    const g = groups.find((x) => x.label === cfg.label);
    if (g) g.count += 1;
    else groups.push({ label: cfg.label, cfg, count: 1 });
  }
  const shown = statusFilter === null ? sorted : sorted.filter((i) => statusOf(i).label === statusFilter);

  return (
    // Zentriert und breiter: auf einem 3440er-Schirm klebte die Liste sonst links
    // in einer 720-px-Spalte. Die Überschrift «Bestand» steht bereits im Reiter darüber.
    <div style={{ maxWidth: 980, marginInline: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Status-Filter (nur, wenn es mehr als einen Status gibt) – dezent, Punkt + Wort + Anzahl. */}
      {groups.length > 1 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <FilterChip label="Alle" count={items.length} active={statusFilter === null}
            onClick={() => setStatusFilter(null)} />
          {groups.map((g) => (
            <FilterChip key={g.label} label={g.label} count={g.count} dot={g.cfg.color}
              active={statusFilter === g.label} onClick={() => setStatusFilter(g.label)} />
          ))}
        </div>
      )}
      <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden', background: '#fff' }}>
        {shown.map((i, idx) => (
          <button
            key={i.id}
            className="erp-orow"
            onClick={() => i.object_id != null && nav?.(i.object_id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, width: '100%', padding: '13px 16px',
              background: '#fff', border: 'none', borderBottom: idx === shown.length - 1 ? 'none' : '1px solid var(--border-1)',
              cursor: 'pointer', font: 'inherit', textAlign: 'left',
            }}
          >
            <div style={{ width: 34, height: 34, borderRadius: 'var(--r-sm)', background: INST.bg, color: INST.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
              <Boxes size={16} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>
                {instanceLabel(i.kind, i.quantity, unit)}
              </div>
              <div style={{ font: 'var(--mono-sm)', color: 'var(--fg-3)', fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>
                {fmtObjId(i.object_id)}
              </div>
            </div>
            <StatusBadge cfg={statusOf(i)} size={11} />
            <span style={{ color: 'var(--fg-4)', display: 'flex', flex: 'none' }}><ChevronRight size={18} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** Dezenter Filter-Chip (Notiz #288): Punkt (Status-Farbe) + Wort + Anzahl, aktiv = accent-soft. */
function FilterChip({ label, count, dot, active, onClick }: {
  label: string; count: number; dot?: string; active: boolean; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', cursor: 'pointer',
        borderRadius: 999, font: '600 12px var(--font-body)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border-1)'}`,
        background: active ? 'var(--accent-soft)' : '#fff',
        color: active ? 'var(--accent-ink)' : 'var(--fg-2)',
      }}>
      {dot && <span style={{ width: 7, height: 7, borderRadius: 999, background: dot, flex: 'none' }} />}
      {label}
      <span className="ix-tnum" style={{ color: 'var(--fg-4)', fontWeight: 500 }}>{count}</span>
    </button>
  );
}
