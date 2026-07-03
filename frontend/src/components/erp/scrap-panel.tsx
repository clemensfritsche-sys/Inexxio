'use client';

import { useMemo, useState } from 'react';
import { Trash2, Lock, CheckCircle2, Info, ScanLine } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderInstance } from '@/types';
import { instanceStatusConfig, instanceLabel } from '@/lib/process';
import { StatusBadge, PanelHeader } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { fmtObjId } from '@/components/erp/user-detail';
import { useScan } from '@/components/scan/scan-provider';


/**
 * Prozessschritt «Verschrotten» – die definierte Auflösung einer Abweichung: ein
 * defektes/nicht mehr benötigtes Teil verlässt den Bestand (disposition='scrapped').
 * **Quittierung per Scan ist verbindlich:** jede Instanz wird vor dem Verschrotten
 * physisch gescannt (kein blosses Anklicken) – so wird nie das falsche Teil ausgeschleust.
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
  const scan = useScan();

  // Noch verschrottbar = nicht bereits verschrottet/verbaut. Normalerweise sind auch VERKAUFTE
  // Teile «raus»; bei einer Retoure/Erstattung (reason='return') sind die verkauften Instanzen
  // aber das Subjekt – ein defekt zurückgekommenes Teil kann direkt verschrottet werden.
  const scrappable = useMemo(
    () => instances.filter((i) => i.object_id != null && (order.reason === 'return'
      ? !['scrapped', 'consumed'].includes(i.disposition ?? '')
      : !['scrapped', 'sold', 'consumed'].includes(i.disposition ?? ''))),
    [instances, order.reason],
  );

  const [scanned, setScanned] = useState<Set<number>>(new Set());
  // Je gescannter Instanz die zu verschrottende Menge (Default = ganze Instanz). Für Chargen
  // (Menge > 1) editierbar – analog Ressourcen-Teilentnahme: nur die Menge sinkt.
  const [qtys, setQtys] = useState<Record<number, number>>({});
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Eine Instanz nach der anderen scannen (Verifikation gegen die Objektnummer). Jede
  // bestätigte Instanz wandert in die «gescannt»-Menge; danach folgt die nächste.
  function runSequence(queue: OrderInstance[], acc: Set<number>) {
    if (queue.length === 0) return;
    const inst = queue[0];
    const oid = inst.object_id as number;
    scan({
      title: `Verschrotten · ${fmtObjId(oid)}`,
      steps: [{
        label: 'Instanz', hint: 'Zu verschrottende Instanz scannen', expected: oid, kind: 'instance',
        candidates: [{ objectId: oid, label: instanceLabel(inst.kind) }],
      }],
      onComplete: () => {
        const next = new Set(acc); next.add(oid); setScanned(next);
        setQtys((q) => (q[oid] != null ? q : { ...q, [oid]: inst.quantity ?? 1 }));   // Default = ganze Menge
        runSequence(queue.slice(1), next);
      },
    });
  }

  function startScan(only?: OrderInstance) {
    setError(null);
    const queue = only ? [only] : scrappable.filter((i) => !scanned.has(i.object_id as number));
    if (queue.length) runSequence(queue, scanned);
  }

  async function submit() {
    const ids = [...scanned];
    if (ids.length === 0) { setError('Bitte zuerst die zu verschrottenden Instanzen scannen'); return; }
    // Je Instanz die (ggf. reduzierte) Teilmenge mitgeben – Charge wird teilverschrottet.
    const items = ids.map((oid) => ({ instance_id: oid, quantity: qtys[oid] ?? null }));
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderScrap(order.object_id as number,
        { items, note: note.trim() || null, step_id: stepId ?? null }));
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

  const allScanned = scrappable.length > 0 && scrappable.every((i) => scanned.has(i.object_id as number));

  return (
    <div style={cardStyle}>
      <Header info="Jede Instanz wird vor dem Verschrotten gescannt (Verifikation). Gescannte Instanzen werden mit «Verschrotten» endgültig aus dem Bestand genommen." />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {scrappable.map((i) => {
          const oid = i.object_id as number;
          const sel = scanned.has(oid);
          return (
            <div key={i.id} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
              border: `1px solid ${sel ? '#fecaca' : '#f1f5f9'}`, borderRadius: 8,
              background: sel ? '#fef2f2' : '#fff',
            }}>
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(i.kind, i.quantity, order.article_unit ?? undefined)}</span>
              {sel && (i.quantity ?? 1) > 1 && (
                // Charge: Teilmenge zum Verschrotten wählen (1 … volle Menge).
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#64748b' }}>
                  <input type="number" min={1} max={i.quantity ?? 1}
                    value={qtys[oid] ?? i.quantity ?? 1}
                    onChange={(e) => {
                      const v = Math.max(1, Math.min(i.quantity ?? 1, Number(e.target.value) || 1));
                      setQtys((q) => ({ ...q, [oid]: v }));
                    }}
                    style={{ width: 52, padding: '3px 6px', fontSize: 12, border: '1px solid #e2e8f0', borderRadius: 6, textAlign: 'right' }} />
                  <span>/ {i.quantity}</span>
                </span>
              )}
              {sel ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 700, color: '#dc2626' }}>
                  <CheckCircle2 size={13} /> gescannt
                </span>
              ) : (
                <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} />
              )}
              <button onClick={() => startScan(i)} title="Diese Instanz scannen"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', color: '#dc2626', cursor: 'pointer', flexShrink: 0 }}>
                <ScanLine size={15} />
              </button>
            </div>
          );
        })}
      </div>

      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2}
        placeholder="Grund (optional) – z. B. Defekt, Bruch, Falschteil"
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-red-400 focus:border-transparent"
        style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {scanned.size > 0 && (
        <button onClick={submit} disabled={saving}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
            minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none', background: '#dc2626', color: '#fff',
            fontSize: 14, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.55 : 1,
          }}>
          <Trash2 size={18} /> {saving ? 'Verschrottet…' : `Verschrotten (${scanned.size})`}
        </button>
      )}
      {!allScanned && (
        <button onClick={() => startScan()} disabled={saving}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
            minHeight: 44, padding: '0 16px', borderRadius: 10, border: '1px solid #fecaca', background: '#fff', color: '#dc2626',
            fontSize: 14, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.55 : 1,
          }}>
          <ScanLine size={18} /> {scanned.size > 0 ? 'Weitere scannen' : 'Scannen & verschrotten'}
        </button>
      )}
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

function Header({ info }: { info?: string }) {
  return <PanelHeader icon={Trash2} title="Verschrotten" tone="#dc2626" info={info} />;
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
