'use client';

import { Boxes, ArrowLeft } from 'lucide-react';
import type { Instance } from '@/types';
import { qcStatusConfig, instanceKindLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { StatusBadge } from '@/components/erp/fields';

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function InstanceDetail({ record, onBack }: { record: Instance; onBack: () => void }) {
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
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>
              {instanceKindLabel(record.kind)}
            </div>
            <div style={{ marginTop: 4 }}><StatusBadge cfg={qcStatusConfig(record.qc_status)} /></div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(record.object_id ?? null)}</div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Row k="Artikel" v={record.article_name ?? '—'} />
          <Row k="Art" v={record.kind === 'batch' ? 'Charge' : 'Einzelteil'} />
          <Row k="Menge" v={String(record.quantity)} />
          {record.serial_number && <Row k="Seriennummer" v={record.serial_number} />}
          <Row k="Aus Auftrag" v={record.order_object_id != null ? fmtObjId(record.order_object_id) : '—'} />
          <Row k="Standort" v={record.location_label ?? 'Kein Standort'} />
          <Row k="QC-Status" v={qcStatusConfig(record.qc_status).label} />
          <Row k="Erstellt" v={localDate(record.created_at)} />
        </div>
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
