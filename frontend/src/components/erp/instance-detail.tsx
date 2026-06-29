'use client';

import { useEffect, useState } from 'react';
import { Boxes, ArrowLeft, FileText, ClipboardList, MapPin, AlertTriangle, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceOrderRef, LocationType } from '@/types';
import { instanceStatusConfig, LOCATION_META } from '@/lib/process';
import { orderStatusConfig } from '@/lib/order';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { ObjectLabel } from '@/components/scan/object-label';

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

/**
 * Instanz-Detail – bewusst EINE Ansicht (keine Reiter): Eine Instanz ist die
 * **Summe aller Prozesse**, und Prozesse werden ausschliesslich durch **Aufträge**
 * angestossen. Oben der Verweis auf die **Spezifikation** (Artikel, aus dem die
 * Instanz hervorging), darunter ein paar Eckdaten und die **vollständige Liste der
 * Aufträge**, die diese Instanz angefasst haben (chronologisch, jeder verlinkt).
 * Aktionen an einer Instanz (verschrotten, verkaufen, …) laufen ausschliesslich
 * über einen Auftrag – hier gibt es daher keine direkten Mutationen.
 */
export function InstanceDetail({ record, onBack, onChanged }: {
  record: Instance;
  onBack: () => void;
  onChanged?: () => void;   // Feed/Listen aktualisieren (z. B. nach Anlage einer Abweichung)
}) {
  const inst = record;
  const nav = useErpNav();
  const [orders, setOrders] = useState<InstanceOrderRef[] | null>(null);
  const [devBusy, setDevBusy] = useState(false);
  const [devErr, setDevErr] = useState<string | null>(null);

  useEffect(() => {
    if (inst.object_id == null) return;
    let cancelled = false;
    api.getInstanceOrders(inst.object_id)
      .then((o) => { if (!cancelled) setOrders(o); })
      .catch(() => { if (!cancelled) setOrders([]); });
    return () => { cancelled = true; };
  }, [inst.object_id]);

  const LocIcon = LOCATION_META[(inst.location_type as LocationType)]?.icon ?? MapPin;

  // Eine Abweichung an genau dieser Instanz läuft – wie jede Aktion – über einen Auftrag:
  // einen Unter-Auftrag am (Herkunfts-)Auftrag, der freigegeben/abgeschlossen ist.
  // «Herkunft zuerst» → bevorzugt der Ursprungsauftrag, der die Instanz erzeugt hat.
  const deviationParent = (orders ?? []).find((o) => o.status === 'released' || o.status === 'completed') ?? null;

  async function reportDeviation() {
    if (!deviationParent || inst.object_id == null) return;
    setDevBusy(true);
    setDevErr(null);
    try {
      const devi = await api.createDeviation(deviationParent.object_id, [inst.object_id]);
      onChanged?.();                                       // Auftrag-Feed sofort aktualisieren
      if (devi.object_id != null) nav?.(devi.object_id);   // zur neuen Abweichung springen
    } catch (e) {
      setDevErr(e instanceof Error ? e.message : 'Abweichung konnte nicht eröffnet werden');
    } finally {
      setDevBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Boxes size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Instanz</div>
            <div style={{ marginTop: 4 }}>
              <StatusBadge cfg={instanceStatusConfig(inst.quality, inst.disposition, (inst.reserved_quantity ?? 0) > 0)} />
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(inst.object_id ?? null)}</div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Spezifikation – die Vorlage (Artikel), aus der diese Instanz hervorging */}
        <div style={card}>
          <div style={sectionLabel}>Spezifikation</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FileText size={16} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#0F172A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {inst.article_name ?? 'Artikel'}
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>Artikel-Spezifikation öffnen</div>
            </div>
            {inst.article_object_id != null && <ObjId value={inst.article_object_id} />}
          </div>
        </div>

        {/* Eckdaten der Instanz */}
        <div style={card}>
          <FactRow label="Menge" value={String(inst.quantity)} />
          {(inst.reserved_quantity ?? 0) > 0 && (
            <FactRow label="Reserviert" value={`${inst.reserved_quantity} von ${inst.quantity}`} />
          )}
          {inst.serial_number && <FactRow label="Seriennummer" value={inst.serial_number} />}
          <FactRow
            label="Standort"
            node={
              inst.location_id != null ? (
                <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <LocIcon size={12} style={{ color: '#94a3b8' }} />
                    <ObjId value={inst.location_id} />
                    {inst.location_label && <span style={{ color: '#64748b', fontWeight: 400 }}>{inst.location_label}</span>}
                  </span>
                  {inst.location_type === 'instance' && inst.physical_location_label && (
                    <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 400 }}>physisch: {inst.physical_location_label}</span>
                  )}
                </span>
              ) : <span style={{ color: '#94a3b8' }}>Noch nicht festgelegt</span>
            }
          />
          <FactRow label="Erstellt" value={localDate(inst.created_at)} />
        </div>

        {/* Aufträge – jeder Prozess an dieser Instanz wurde durch einen Auftrag ausgelöst */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ClipboardList size={15} style={{ color: '#2563eb' }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A', flex: 1 }}>Aufträge</span>
            {orders && orders.length > 0 && <span style={{ fontSize: 12, color: '#94a3b8' }}>{orders.length}</span>}
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            Alle Aufträge, die diese Instanz angefasst haben – neueste zuerst.
          </div>
          {orders === null ? (
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>
          ) : orders.length === 0 ? (
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Noch kein Auftrag hat diese Instanz verarbeitet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[...orders].sort((a, b) => (b.object_id ?? 0) - (a.object_id ?? 0)).map((o) => (
                <div key={o.object_id} style={orderRow}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <ObjId value={o.object_id} />
                  </div>
                  <StatusBadge cfg={orderStatusConfig(o.status)} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Abweichung melden – ein Unter-Auftrag genau auf diese Instanz (Defekt,
            Nacharbeit, Reklamation – EIN Konzept). Nur wenn ein Herkunfts-/Bezugs-
            auftrag (freigegeben/abgeschlossen) existiert. */}
        {deviationParent && (
          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertTriangle size={15} style={{ color: '#d97706' }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A', flex: 1 }}>Abweichung</span>
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              Defekt oder Nacharbeit an dieser Instanz? Eröffnet einen Unter-Auftrag (Abweichung)
              am Auftrag <ObjId value={deviationParent.object_id} /> – dort legst du den Ablauf fest und gibst frei.
            </div>
            {devErr && <span style={{ fontSize: 12, color: '#dc2626' }}>{devErr}</span>}
            <button type="button" onClick={reportDeviation} disabled={devBusy}
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                alignSelf: 'flex-start', padding: '9px 16px', borderRadius: 8,
                border: '1px solid #fbbf24', background: devBusy ? '#fef3c7' : '#fffbeb',
                color: '#b45309', fontSize: 13, fontWeight: 700, cursor: devBusy ? 'default' : 'pointer',
              }}>
              {devBusy ? <Loader2 size={15} className="animate-spin" /> : <AlertTriangle size={15} />}
              Abweichung melden
            </button>
          </div>
        )}

        {/* Etikett / QR (scannbar) */}
        {inst.object_id != null && (
          <div style={card}>
            <ObjectLabel objectId={inst.object_id} title={inst.article_name ?? undefined} subtitle="Instanz" />
          </div>
        )}
      </div>
    </div>
  );
}

const card: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
const sectionLabel: React.CSSProperties = {
  fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8',
};
const orderRow: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
  border: '1px solid #f1f5f9', borderRadius: 8,
};

function FactRow({ label, value, node }: { label: string; value?: string; node?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{node ?? value ?? '—'}</span>
    </div>
  );
}
