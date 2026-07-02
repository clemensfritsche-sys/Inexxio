'use client';

import { useEffect, useMemo, useState } from 'react';
import { Undo2, Lock, CheckCircle2, Info, ScanLine, ClipboardCheck } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, StorageLocation, LocationType } from '@/types';
import { instanceStatusConfig, instanceLabel } from '@/lib/process';
import { StatusBadge, PanelHeader, SearchSelect } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { fmtObjId } from '@/components/erp/user-detail';
import { useScan } from '@/components/scan/scan-provider';

type OrderInstance = NonNullable<Order['instances']>[number];

/**
 * Prozessschritt «Rücknahme» (Retoure) – das **Spiegelbild des Verschrottens**: eine verkaufte
 * Instanz kommt zurück ins Lager (disposition ``sold`` → ``in_stock``). Optional geht sie erst
 * **zur Prüfung** (Qualität ``pending`` statt sofort wieder verkäuflich) und an einen wählbaren
 * Zielstandort (leer = automatischer Wareneingang). **Quittierung per Scan ist verbindlich:**
 * jede Instanz wird vor der Rücknahme physisch gescannt – so kommt nie das falsche Teil zurück.
 */
export function ReturnPanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  onOrderUpdated: (o: Order) => void;
}) {
  const rec = order.return_receipt;
  const done = !!rec?.done;
  const instances = useMemo(() => order.instances ?? [], [order.instances]);
  const scan = useScan();

  // Rückgebbar = noch verkauft (sold). Bereits Zurückgenommenes (in_stock) ist erledigt.
  const returnable = useMemo(
    () => instances.filter((i) => i.object_id != null && i.disposition === 'sold'),
    [instances],
  );

  const [scanned, setScanned] = useState<Set<number>>(new Set());
  // Je Instanz die zurückkommende Menge (Default = ganze Instanz) – Charge teilretournierbar.
  const [qtys, setQtys] = useState<Record<number, number>>({});
  const [toInspection, setToInspection] = useState(false);
  const [locKey, setLocKey] = useState('');            // "" = automatischer Wareneingang
  const [storageLocs, setStorageLocs] = useState<StorageLocation[]>([]);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Zielort-Auswahl erst laden, wenn der Schritt aktiv ist.
  useEffect(() => {
    if (stepState === 'locked' || done) return;
    api.getStorageLocations().then(setStorageLocs).catch(() => {});
  }, [stepState, done]);

  // Eine Instanz nach der anderen scannen (Verifikation gegen die Objektnummer).
  function runSequence(queue: OrderInstance[], acc: Set<number>) {
    if (queue.length === 0) return;
    const inst = queue[0];
    const oid = inst.object_id as number;
    scan({
      title: `Rücknahme · ${fmtObjId(oid)}`,
      steps: [{
        label: 'Instanz', hint: 'Zurückkommende Instanz scannen', expected: oid, kind: 'instance',
        candidates: [{ objectId: oid, label: instanceLabel(inst.kind) }],
      }],
      onComplete: () => {
        const next = new Set(acc); next.add(oid); setScanned(next);
        setQtys((q) => (q[oid] != null ? q : { ...q, [oid]: inst.quantity ?? 1 }));
        runSequence(queue.slice(1), next);
      },
    });
  }

  function startScan(only?: OrderInstance) {
    setError(null);
    const queue = only ? [only] : returnable.filter((i) => !scanned.has(i.object_id as number));
    if (queue.length) runSequence(queue, scanned);
  }

  async function submit() {
    const ids = [...scanned];
    if (ids.length === 0) { setError('Bitte zuerst die zurückkommenden Instanzen scannen'); return; }
    const items = ids.map((oid) => ({ instance_id: oid, quantity: qtys[oid] ?? null }));
    // Zielort: "type:id" oder leer (→ automatischer Wareneingang im Backend).
    const idx = locKey.indexOf(':');
    const location_type = idx > 0 ? (locKey.slice(0, idx) as LocationType) : null;
    const location_id = idx > 0 ? Number(locKey.slice(idx + 1)) : null;
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderReturn(order.object_id as number, {
        items, to_inspection: toInspection, location_type, location_id,
        note: note.trim() || null, step_id: stepId ?? null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler bei der Rücknahme');
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
          <Info size={14} /> Keine verkauften Instanzen für die Rücknahme vorhanden.
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#ecfeff', color: '#0e7490' }}>
          <CheckCircle2 size={16} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>
            Rücknahme abgeschlossen{rec?.returned_count ? ` · ${rec.returned_count} Stück` : ''}
            {rec?.to_inspection ? ' · zur Prüfung' : ''}
          </span>
          {rec?.received_by_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{rec.received_by_name}</span>}
        </div>
        {rec?.location_label && <div style={{ fontSize: 12, color: '#64748b' }}>Standort: {rec.location_label}</div>}
        {rec?.note && <div style={{ fontSize: 12, color: '#64748b' }}>Bemerkung: {rec.note}</div>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {instances.map((i) => <InstanceRow key={i.id} instance={i} />)}
        </div>
      </div>
    );
  }

  const allScanned = returnable.length > 0 && returnable.every((i) => scanned.has(i.object_id as number));
  const locOptions = [
    { value: '', label: 'Automatischer Wareneingang' },
    ...storageLocs.filter((l) => l.status === 'released' && l.object_id != null)
      .map((l) => ({ value: `lagerplatz:${l.object_id}`, label: `Lagerplatz ${fmtObjId(l.object_id)}` })),
  ];

  return (
    <div style={cardStyle}>
      <Header info="Jede Instanz wird vor der Rücknahme gescannt (Verifikation). Zurückgenommene Teile kommen wieder ins Lager – optional erst «zur Prüfung» (gesperrt, bis kontrolliert)." />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 280, overflowY: 'auto' }}>
        {returnable.map((i) => {
          const oid = i.object_id as number;
          const sel = scanned.has(oid);
          return (
            <div key={i.id} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
              border: `1px solid ${sel ? '#a5f3fc' : '#f1f5f9'}`, borderRadius: 8,
              background: sel ? '#ecfeff' : '#fff',
            }}>
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(i.kind, i.quantity, order.article_unit ?? undefined)}</span>
              {sel && (i.quantity ?? 1) > 1 && (
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
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 700, color: '#0e7490' }}>
                  <CheckCircle2 size={13} /> gescannt
                </span>
              ) : (
                <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} />
              )}
              <button onClick={() => startScan(i)} title="Diese Instanz scannen"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', color: '#0e7490', cursor: 'pointer', flexShrink: 0 }}>
                <ScanLine size={15} />
              </button>
            </div>
          );
        })}
      </div>

      {/* Zielstandort (optional) + «zur Prüfung» */}
      <SearchSelect label="Zielstandort" value={locKey} onChange={setLocKey} options={locOptions}
        placeholder="Automatischer Wareneingang" />
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer', color: '#0f172a' }}>
        <input type="checkbox" checked={toInspection} onChange={(e) => setToInspection(e.target.checked)} />
        <ClipboardCheck size={15} style={{ color: '#0e7490' }} />
        <span style={{ fontWeight: 600 }}>Erst zur Prüfung (gesperrt, bis kontrolliert)</span>
      </label>

      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2}
        placeholder="Bemerkung (optional) – z. B. Rücksendegrund"
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-cyan-400 focus:border-transparent"
        style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {scanned.size > 0 && (
        <button onClick={submit} disabled={saving}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
            minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none', background: '#0891b2', color: '#fff',
            fontSize: 14, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.55 : 1,
          }}>
          <Undo2 size={18} /> {saving ? 'Nimmt zurück…' : `Rücknahme buchen (${scanned.size})`}
        </button>
      )}
      {!allScanned && (
        <button onClick={() => startScan()} disabled={saving}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
            minHeight: 44, padding: '0 16px', borderRadius: 10, border: '1px solid #a5f3fc', background: '#fff', color: '#0e7490',
            fontSize: 14, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.55 : 1,
          }}>
          <ScanLine size={18} /> {scanned.size > 0 ? 'Weitere scannen' : 'Scannen & zurücknehmen'}
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
  return <PanelHeader icon={Undo2} title="Rücknahme" tone="#0891b2" info={info} />;
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
