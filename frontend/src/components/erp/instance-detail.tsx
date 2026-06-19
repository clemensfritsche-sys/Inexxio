'use client';

import { useEffect, useState } from 'react';
import { Boxes, ArrowLeft, FileText, Link2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceReference } from '@/types';
import { qcStatusConfig, instanceKindLabel } from '@/lib/process';
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

export function InstanceDetail({ record, onBack }: { record: Instance; onBack: () => void }) {
  const [tab, setTab] = useState<TabKey>('stammdaten');
  const [refs, setRefs] = useState<InstanceReference[] | null>(null);

  useEffect(() => {
    if (tab !== 'verwendung' || refs !== null || record.object_id == null) return;
    api.getInstanceReferences(record.object_id).then(setRefs).catch(() => setRefs([]));
  }, [tab, refs, record.object_id]);

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
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>{instanceKindLabel(record.kind)}</div>
            <div style={{ marginTop: 4 }}><StatusBadge cfg={qcStatusConfig(record.qc_status)} /></div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(record.object_id ?? null)}</div>
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
                {record.article_object_id != null && <ObjId value={record.article_object_id} />}
                {record.article_name && <span style={{ color: '#64748b', fontWeight: 400 }}>{record.article_name}</span>}
                {!record.article_object_id && !record.article_name && '—'}
              </span>
            </RowNode>
            <Row k="Art" v={instanceKindLabel(record.kind)} />
            <Row k="Menge" v={String(record.quantity)} />
            {record.serial_number && <Row k="Seriennummer" v={record.serial_number} />}
            <RowNode k="Aus Auftrag">{record.order_object_id != null ? <ObjId value={record.order_object_id} /> : '—'}</RowNode>
            <RowNode k="Standort">{record.location_id != null ? <ObjId value={record.location_id} /> : 'Kein Standort'}</RowNode>
            <Row k="Status" v={qcStatusConfig(record.qc_status).label} />
            <Row k="Erstellt" v={localDate(record.created_at)} />
          </div>
          {record.object_id != null && (
            <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px' }}>
              <ObjectLabel objectId={record.object_id} title={record.article_name ?? undefined} subtitle={instanceKindLabel(record.kind)} />
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
