'use client';

import { useState } from 'react';
import { ArrowLeft, Layers, CheckCircle2, Ban, RotateCcw, RefreshCcw } from 'lucide-react';
import { api } from '@/lib/api';
import type { Process, ProcessSource, UserProfile } from '@/types';
import { ProcessSteps } from '@/components/erp/process-steps';
import { Segmented, TextField, ErrorText, StatusBadge } from '@/components/erp/fields';
import { PROCESS_SOURCE_META, sourceLabel, processStatusConfig, stockEffectConfig } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';

const SOURCE_OPTS = [
  { value: 'produce', label: 'Neu' }, { value: 'stock', label: 'Bestand' }, { value: 'instance', label: 'Instanz' },
];
const STD_OPTS = [
  { value: 'false', label: 'Artikelbezogen' }, { value: 'true', label: 'Standard (alle Artikel)' },
];

/** Prozess als eigenständiges Objekt (Feed «Prozesse»): anlegen, Schritte definieren,
 *  freigeben/deaktivieren/ersetzen. ``is_standard`` ist nur bei der Anlage wählbar.
 *  Artikel referenzieren den Prozess über ihre Prozessstückliste. */
export function ProcessDetail({ record, suppliers, onSaved, onBack }: {
  record: Process | null;
  suppliers: UserProfile[];
  onSaved: (p: Process) => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [name, setName] = useState(record?.name ?? '');
  const [source, setSource] = useState<ProcessSource>((record?.source as ProcessSource) ?? 'produce');
  const [isStandard, setIsStandard] = useState<boolean>(record?.is_standard ?? false);
  const [stepCount, setStepCount] = useState<number>(record?.step_count ?? 0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const status = record?.status ?? 'draft';
  const editable = status === 'draft';

  async function create() {
    if (!name.trim()) { setError('Bitte einen Namen angeben'); return; }
    setSaving(true); setError(null);
    try { onSaved(await api.createProcess({ name: name.trim(), source, is_standard: isStandard })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Anlegen'); }
    finally { setSaving(false); }
  }

  async function patch(data: Parameters<typeof api.updateProcess>[1]) {
    if (!record?.object_id) return;
    setError(null);
    try { onSaved(await api.updateProcess(record.object_id, data)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
  }

  async function replace() {
    if (!record?.object_id) return;
    setError(null);
    try { onSaved(await api.replaceProcess(record.object_id)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Ersetzen fehlgeschlagen'); }
  }

  if (isCreate) {
    return (
      <div style={{ padding: 20, maxWidth: 560 }}>
        <button onClick={onBack} style={backBtn}><ArrowLeft size={14} /> Zurück</button>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: '8px 0 16px' }}>Neuer Prozess</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <TextField label="Name (frei wählbar)" value={name} onChange={setName} required placeholder="z. B. Entnahme, Umlagern, Verschrotten, Sonderkontrolle" />
          <div>
            <Segmented label="Quelle = Subjekt (Richtung wird abgeleitet, nicht gewählt)" value={source}
              onChange={(v) => setSource(v as ProcessSource)} options={SOURCE_OPTS} />
            <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>{PROCESS_SOURCE_META[source].hint}</div>
          </div>
          <div>
            <Segmented label="Geltung (nur bei der Anlage wählbar)" value={String(isStandard)}
              onChange={(v) => setIsStandard(v === 'true')} options={STD_OPTS} />
            <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
              {isStandard
                ? 'Standard: gilt automatisch für jeden Artikel (geerbt) – kein Link nötig.'
                : 'Artikelbezogen: über die Prozessstückliste einem oder mehreren Artikeln zuordnen.'}
            </div>
          </div>
          {error && <ErrorText msg={error} />}
          <button onClick={create} disabled={saving} style={primary}>{saving ? 'Speichern…' : 'Anlegen'}</button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #f1f5f9' }}>
        <button onClick={onBack} style={backBtn}><ArrowLeft size={14} /> Zurück</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: '#f5f3ff', color: '#7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Layers size={18} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0f172a' }}>{record!.name}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: '#475569' }}>{fmtObjId(record!.object_id)}</span>
              <StatusBadge cfg={processStatusConfig(status)} />
              <StatusBadge cfg={stockEffectConfig(record!.stock_effect)} />
              <span style={{ fontSize: 10, fontWeight: 700, color: '#64748b', background: '#f1f5f9', padding: '1px 6px', borderRadius: 999 }}>{sourceLabel(record!.source)}</span>
              {record!.is_standard && <span style={{ fontSize: 10, fontWeight: 700, color: '#7c3aed', background: '#f5f3ff', padding: '1px 6px', borderRadius: 999 }}>Standard</span>}
              {record!.linked_article_count > 0 && (
                <span style={{ fontSize: 10, fontWeight: 700, color: '#0369a1', background: '#e0f2fe', padding: '1px 6px', borderRadius: 999 }}>
                  bei {record!.linked_article_count} Artikel{record!.linked_article_count === 1 ? '' : 'n'}
                </span>
              )}
            </div>
          </div>
        </div>
        {/* Lebenszyklus */}
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          {status === 'draft' && (
            <button onClick={() => patch({ status: 'released' })} disabled={stepCount === 0}
              title={stepCount === 0 ? 'Erst einen Schritt hinzufügen' : undefined}
              style={action('#16a34a', stepCount === 0)}><CheckCircle2 size={14} /> Freigeben</button>
          )}
          {status === 'released' && (
            <>
              <button onClick={replace} style={action('#475569')}><RefreshCcw size={14} /> Ersetzen</button>
              <button onClick={() => patch({ status: 'inactive' })} style={action('#dc2626')}><Ban size={14} /> Deaktivieren</button>
            </>
          )}
          {status === 'inactive' && <button onClick={() => patch({ status: 'released' })} style={action('#2563eb')}><RotateCcw size={14} /> Reaktivieren</button>}
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
            <Segmented label="Geltung" value={String(isStandard)}
              onChange={(v) => { const b = v === 'true'; setIsStandard(b); patch({ is_standard: b }); }} options={STD_OPTS} />
          </div>
        )}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#94a3b8', marginBottom: 8 }}>Schritte</div>
          <ProcessSteps processId={record!.id} suppliers={suppliers} readOnly={!editable} onStepsCount={setStepCount} />
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
function action(color: string, disabled = false): React.CSSProperties {
  return { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: `1px solid ${disabled ? '#cbd5e1' : color}`, background: '#fff', color: disabled ? '#cbd5e1' : color, fontSize: 13, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer' };
}
