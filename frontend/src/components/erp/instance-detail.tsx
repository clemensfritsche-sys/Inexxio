'use client';

import { useEffect, useState } from 'react';
import { Boxes, ArrowLeft, FileText, ClipboardList, MapPin } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceOrderRef, LocationType } from '@/types';
import { instanceStatusConfig, LOCATION_META } from '@/lib/process';
import { orderStatusConfig } from '@/lib/order';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { ObjectLabel } from '@/components/scan/object-label';

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

// Auftrags-Modus → kurzes Label für die Auftragsliste der Instanz.
function modeLabel(mode: string): string {
  return mode === 'custom' ? 'Individueller Auftrag' : 'Artikel-Auftrag';
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
export function InstanceDetail({ record, onBack }: { record: Instance; onBack: () => void }) {
  const inst = record;
  const [orders, setOrders] = useState<InstanceOrderRef[] | null>(null);

  useEffect(() => {
    if (inst.object_id == null) return;
    let cancelled = false;
    api.getInstanceOrders(inst.object_id)
      .then((o) => { if (!cancelled) setOrders(o); })
      .catch(() => { if (!cancelled) setOrders([]); });
    return () => { cancelled = true; };
  }, [inst.object_id]);

  const LocIcon = LOCATION_META[(inst.location_type as LocationType)]?.icon ?? MapPin;

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
              <StatusBadge cfg={instanceStatusConfig(inst.quality, inst.disposition)} />
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
            Alle Aufträge, die diese Instanz angefasst haben – Herkunft zuerst.
          </div>
          {orders === null ? (
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>
          ) : orders.length === 0 ? (
            <div style={{ fontSize: 13, color: '#94a3b8' }}>Noch kein Auftrag hat diese Instanz verarbeitet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {orders.map((o) => (
                <div key={o.object_id} style={orderRow}>
                  <div style={{ minWidth: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <ObjId value={o.object_id} />
                      <span style={{ fontSize: 11, color: '#94a3b8' }}>{modeLabel(o.mode)}</span>
                    </div>
                    {o.roles.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {o.roles.map((r) => <span key={r} style={roleChip}>{r}</span>)}
                      </div>
                    )}
                  </div>
                  <StatusBadge cfg={orderStatusConfig(o.status)} />
                </div>
              ))}
            </div>
          )}
        </div>

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
const roleChip: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: '#475569', background: '#f1f5f9',
  padding: '1px 7px', borderRadius: 999,
};

function FactRow({ label, value, node }: { label: string; value?: string; node?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{node ?? value ?? '—'}</span>
    </div>
  );
}
