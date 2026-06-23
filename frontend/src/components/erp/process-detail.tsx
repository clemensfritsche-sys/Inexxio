'use client';

import { useState } from 'react';
import { ArrowLeft, Layers, CheckCircle2, Ban, RotateCcw } from 'lucide-react';
import { api } from '@/lib/api';
import type { Process, ProcessSource, UserProfile } from '@/types';
import { ProcessSteps } from '@/components/erp/process-steps';
import { Segmented, TextField, ErrorText } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';

const SOURCE_OPTS = [
  { value: 'produce', label: 'Neu' }, { value: 'stock', label: 'Bestand' }, { value: 'instance', label: 'Instanz' },
];
const STATUS_CFG: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Entwurf', color: '#d97706', bg: '#fffbeb' },
  released: { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4' },
  inactive: { label: 'Inaktiv', color: '#475569', bg: '#f1f5f9' },
};

/** Standardprozess (global, gilt für jeden Artikel): anlegen, als «Standard» freigeben,
 *  Schritte definieren. Lebenszyklus: Entwurf → Freigegeben → Inaktiv. */
export function ProcessDetail({ record, suppliers, onSaved, onBack }: {
  record: Process | null;
  suppliers: UserProfile[];
  onSaved: (p: Process) => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [name, setName] = useState(record?.name ?? '');
  const [source, setSource] = useState<ProcessSource>((record?.source as ProcessSource) ?? 'produce');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const status = record?.status ?? 'draft';
  const editable = status === 'draft';

  async function create() {
    if (!name.trim()) { setError('Bitte einen Namen angeben'); return; }
    setSaving(true); setError(null);
    try { onSaved(await api.createStandardProcess({ name: name.trim(), source })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Anlegen'); }
    finally { setSaving(false); }
  }

  async function patch(data: Parameters<typeof api.updateStandardProcess>[1]) {
    if (!record?.object_id) return;
    setError(null);
    try { onSaved(await api.updateStandardProcess(record.object_id, data)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
  }

  if (isCreate) {
    return (
      <div style={{ padding: 20, maxWidth: 560 }}>
        <button onClick={onBack} style={backBtn}><ArrowLeft size={14} /> Zurück</button>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: '8px 0 16px' }}>Neuer Standardprozess</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <TextField label="Name (frei wählbar)" value={name} onChange={setName} required placeholder="z. B. Entnahme, Umlagern, Verschrotten, Sonderkontrolle" />
          <div>
            <Segmented label="Quelle (bestimmt das Verhalten)" value={source}
              onChange={(v) => setSource(v as ProcessSource)} options={SOURCE_OPTS} />
            <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
              Gilt automatisch für jeden Artikel. Nach dem Anlegen Schritte definieren und als «Standard» freigeben.
            </div>
          </div>
          {error && <ErrorText msg={error} />}
          <button onClick={create} disabled={saving} style={primary}>{saving ? 'Speichern…' : 'Anlegen'}</button>
        </div>
      </div>
    );
  }

  const cfg = STATUS_CFG[status] ?? STATUS_CFG.draft;
  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #f1f5f9' }}>
        <button onClick={onBack} style={backBtn}><ArrowLeft size={14} /> Zurück</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: '#f5f3ff', color: '#7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Layers size={18} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0f172a' }}>{record!.name}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
              <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: '#475569' }}>{fmtObjId(record!.object_id)}</span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 8px', borderRadius: 999, background: cfg.bg, color: cfg.color }}>{cfg.label} · Standard</span>
            </div>
          </div>
        </div>
        {/* Lebenszyklus */}
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          {status === 'draft' && <button onClick={() => patch({ status: 'released' })} style={action('#16a34a')}><CheckCircle2 size={14} /> Als Standard freigeben</button>}
          {status === 'released' && <button onClick={() => patch({ status: 'inactive' })} style={action('#dc2626')}><Ban size={14} /> Deaktivieren</button>}
          {status === 'inactive' && <button onClick={() => patch({ status: 'draft' })} style={action('#2563eb')}><RotateCcw size={14} /> In Entwurf</button>}
        </div>
        {error && <div style={{ marginTop: 8 }}><ErrorText msg={error} /></div>}
      </div>

      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {editable && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <TextField label="Name" value={name} onChange={setName} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => patch({ name: name.trim() })} style={primary}>Name speichern</button>
            </div>
            <Segmented label="Quelle" value={source} onChange={(v) => { setSource(v as ProcessSource); patch({ source: v as ProcessSource }); }} options={SOURCE_OPTS} />
          </div>
        )}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#94a3b8', marginBottom: 8 }}>Schritte</div>
          <ProcessSteps processId={record!.id} suppliers={suppliers} readOnly={!editable} />
        </div>
      </div>
    </div>
  );
}

const backBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, border: 'none', background: 'none',
  color: '#2563eb', cursor: 'pointer', fontSize: 13, fontWeight: 600, padding: 0,
};
const primary: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
function action(color: string): React.CSSProperties {
  return { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: `1px solid ${color}`, background: '#fff', color, fontSize: 13, fontWeight: 600, cursor: 'pointer' };
}
