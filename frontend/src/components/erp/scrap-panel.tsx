'use client';

import { useMemo, useState } from 'react';
import { Trash2, Lock, CheckCircle2, Info, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order } from '@/types';
import { instanceStatusConfig, instanceLabel } from '@/lib/process';
import { StatusBadge } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';

type OrderInstance = NonNullable<Order['instances']>[number];

/**
 * Prozessschritt «Verschrotten» – die definierte Auflösung einer Abweichung: ein
 * defektes/nicht mehr benötigtes Teil verlässt den Bestand (disposition='scrapped').
 * Der Nutzer wählt genau die zu verschrottenden Instanzen (Durchfaller vorausgewählt)
 * und bestätigt. So gibt es keine „herumliegenden, undefinierten Teile".
 */
export function ScrapPanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  onOrderUpdated: (o: Order) => void;
}) {
  const disp = order.disposal;
  const done = !!disp?.done;
  const instances = useMemo(() => order.instances ?? [], [order.instances]);

  // Noch verschrottbar = nicht bereits verschrottet/verkauft/verbraucht.
  const scrappable = useMemo(
    () => instances.filter((i) => !['scrapped', 'sold', 'consumed'].includes(i.disposition ?? '')),
    [instances],
  );

  // Defekte (durchgefallene) Instanzen sind die typischen Verschrottungs-Kandidaten → vorwählen.
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(scrappable.filter((i) => i.quality === 'failed' && i.object_id != null).map((i) => i.object_id as number)),
  );
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(oid: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(oid)) next.delete(oid); else next.add(oid);
      return next;
    });
  }

  async function submit() {
    const ids = [...selected];
    if (ids.length === 0) { setError('Bitte mindestens eine Instanz wählen'); return; }
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderScrap(order.object_id as number,
        { instance_ids: ids, note: note.trim() || null, step_id: stepId ?? null }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Verschrotten');
    } finally { setSaving(false); }
  }

  if (stepState === 'locked') {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Lock size={14} /> Wird aktiv, sobald der vorherige Schritt erledigt ist.
        </div>
      </div>
    );
  }

  if (instances.length === 0) {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Info size={14} /> Noch keine Instanzen vorhanden.
        </div>
      </div>
    );
  }

  if (done) {
    const scrapped = instances.filter((i) => i.disposition === 'scrapped');
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#f1f5f9', color: '#475569' }}>
          <CheckCircle2 size={16} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>
            Verschrottung abgeschlossen{disp?.scrapped_count ? ` · ${disp.scrapped_count} Stück` : ''}
          </span>
          {disp?.scrapped_by_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{disp.scrapped_by_name}</span>}
        </div>
        {disp?.note && <div style={{ fontSize: 12, color: '#64748b' }}>Grund: {disp.note}</div>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {(scrapped.length ? scrapped : instances).map((i) => <InstanceRow key={i.id} instance={i} />)}
        </div>
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <Header />

      <div style={infoStyle}>
        <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Gewählte Instanzen werden <b>verschrottet</b> und verlassen den Bestand – dieser Schritt
          ist endgültig. Defekte Instanzen sind vorausgewählt.</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {scrappable.map((i) => {
          const oid = i.object_id as number;
          const sel = selected.has(oid);
          return (
            <label key={i.id} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', cursor: 'pointer',
              border: `1px solid ${sel ? '#fecaca' : '#f1f5f9'}`, borderRadius: 8,
              background: sel ? '#fef2f2' : '#fff',
            }}>
              <input type="checkbox" checked={sel} onChange={() => toggle(oid)} />
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(i.kind, i.quantity, order.article_unit ?? undefined)}</span>
              <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} />
            </label>
          );
        })}
      </div>

      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2}
        placeholder="Grund (optional) – z. B. Defekt, Bruch, Falschteil"
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-red-400 focus:border-transparent"
        style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      <button onClick={submit} disabled={saving || selected.size === 0}
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
          minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none', background: '#dc2626', color: '#fff',
          fontSize: 14, fontWeight: 700, cursor: saving || selected.size === 0 ? 'not-allowed' : 'pointer',
          opacity: saving || selected.size === 0 ? 0.55 : 1,
        }}>
        <Trash2 size={18} /> {saving ? 'Verschrottet…' : `Verschrotten${selected.size ? ` (${selected.size})` : ''}`}
      </button>
    </div>
  );
}

function InstanceRow({ instance }: { instance: OrderInstance }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
      <span style={{ fontSize: 12 }}><ObjId value={instance.object_id} /></span>
      <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(instance.kind)}</span>
      <StatusBadge cfg={instanceStatusConfig(instance.quality, instance.disposition, (instance.reserved_quantity ?? 0) > 0)} />
    </div>
  );
}

function Header() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Trash2 size={15} style={{ color: '#dc2626' }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Verschrotten</span>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
const infoStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px',
  background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, fontSize: 12, color: '#b91c1c',
};
