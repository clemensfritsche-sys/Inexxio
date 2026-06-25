'use client';

import { useEffect, useState } from 'react';
import { Boxes, ArrowLeft, FileText, Link2, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceReference } from '@/types';
import { instanceStatusConfig, instanceKindLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { ObjectLabel } from '@/components/scan/object-label';

type TabKey = 'stammdaten' | 'verwendung';

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}
function localDateTime(iso: string): string {
  return new Date(iso).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' });
}

export function InstanceDetail({ record, onBack, onRefresh }: { record: Instance; onBack: () => void; onRefresh?: () => void }) {
  const [tab, setTab] = useState<TabKey>('stammdaten');
  const [refs, setRefs] = useState<InstanceReference[] | null>(null);
  const [inst, setInst] = useState<Instance>(record);
  const [confirmScrap, setConfirmScrap] = useState(false);
  const [scrapBusy, setScrapBusy] = useState(false);

  useEffect(() => {
    if (tab !== 'verwendung' || refs !== null || inst.object_id == null) return;
    api.getInstanceReferences(inst.object_id).then(setRefs).catch(() => setRefs([]));
  }, [tab, refs, inst.object_id]);

  // Verschrotten (manuell): aus Bestand/FIFO raus, bleibt sichtbar. Nicht für verbaute Instanzen.
  const canScrap = inst.is_active && !['consumed', 'scrapped'].includes(inst.disposition);
  async function scrap() {
    if (inst.object_id == null) return;
    setScrapBusy(true);
    try {
      setInst(await api.scrapInstance(inst.object_id));
      setConfirmScrap(false);
      onRefresh?.();
    } catch { /* ignore */ } finally { setScrapBusy(false); }
  }

  return (
    <div className="flex flex-col h-full">
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Boxes size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>{instanceKindLabel(inst.kind)}</div>
            <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <StatusBadge cfg={instanceStatusConfig(inst.quality, inst.disposition)} />
              {canScrap && (confirmScrap ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, color: '#dc2626' }}>Verschrotten?</span>
                  <button onClick={scrap} disabled={scrapBusy} style={{ padding: '2px 10px', borderRadius: 6, border: 'none', background: '#dc2626', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>Ja</button>
                  <button onClick={() => setConfirmScrap(false)} style={{ padding: '2px 10px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', color: '#475569', fontSize: 12, cursor: 'pointer' }}>Nein</button>
                </span>
              ) : (
                <button onClick={() => setConfirmScrap(true)} title="Instanz verschrotten"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px', borderRadius: 6, border: '1px solid #fecaca', background: '#fff', color: '#dc2626', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                  <Trash2 size={12} /> Verschrotten
                </button>
              ))}
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(inst.object_id ?? null)}</div>
          </div>
        </div>

        {/* Reiter */}
        <div style={{ display: 'flex', gap: 2, marginTop: 12 }}>
          {([['stammdaten', 'Stammdaten', FileText], ['verwendung', 'Verwendung', Link2]] as const).map(([key, label, Icon]) => {
            const active = tab === key;
            return (
              <button key={key} onClick={() => setTab(key)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  color: active ? '#2563eb' : '#64748b', background: 'none', border: 'none',
                  borderBottom: `2px solid ${active ? '#2563eb' : 'transparent'}`, marginBottom: -13 }}>
                <Icon size={14} /> {label}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        {tab === 'stammdaten' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            <RowNode k="Artikel">
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                {inst.article_object_id != null && <ObjId value={inst.article_object_id} />}
                {inst.article_name && <span style={{ color: '#64748b', fontWeight: 400 }}>{inst.article_name}</span>}
                {!inst.article_object_id && !inst.article_name && '—'}
              </span>
            </RowNode>
            <Row k="Art" v={instanceKindLabel(inst.kind)} />
            <Row k="Menge" v={String(inst.quantity)} />
            {inst.serial_number && <Row k="Seriennummer" v={inst.serial_number} />}
            <RowNode k="Aus Auftrag">{inst.order_object_id != null ? <ObjId value={inst.order_object_id} /> : '—'}</RowNode>
            {inst.reserved_for_order_object_id != null && (
              <RowNode k="Reserviert für"><ObjId value={inst.reserved_for_order_object_id} /></RowNode>
            )}
            <RowNode k="Standort">
              {inst.location_id != null ? (
                <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                  <ObjId value={inst.location_id} />
                  {inst.location_type === 'instance' && inst.physical_location_label && (
                    <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 400 }}>physisch: {inst.physical_location_label}</span>
                  )}
                </span>
              ) : 'Noch nicht festgelegt'}
            </RowNode>
            <Row k="Status" v={instanceStatusConfig(inst.quality, inst.disposition).label} />
            <Row k="Erstellt" v={localDate(inst.created_at)} />
          </div>
          {inst.object_id != null && (
            <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px' }}>
              <ObjectLabel objectId={inst.object_id} title={inst.article_name ?? undefined} subtitle={instanceKindLabel(inst.kind)} />
            </div>
          )}
          </div>
        ) : (
          <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 2 }}>
              Verwendungsnachweise
            </div>
            {refs === null ? (
              <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>
            ) : refs.length === 0 ? (
              <div style={{ fontSize: 13, color: '#94a3b8' }}>Diese Instanz ist nirgends weiter referenziert.</div>
            ) : refs.map((r, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{r.kind}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8' }}>{localDateTime(r.at)}</div>
                </div>
                <span style={{ fontSize: 12 }}><ObjId value={r.object_id} /></span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{k}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  );
}

function RowNode({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{k}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{children}</span>
    </div>
  );
}
