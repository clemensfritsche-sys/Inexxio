'use client';

import { useState } from 'react';
import { ArrowLeft, Layers, CheckCircle2, Ban, RotateCcw, RefreshCcw, Star } from 'lucide-react';
import { api } from '@/lib/api';
import type { Process, UserProfile } from '@/types';
import { ProcessSteps } from '@/components/erp/process-steps';
import { TextField, ErrorText, StatusBadge } from '@/components/erp/fields';
import { sourceLabel, processStatusConfig } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';

/** Unscheinbares Favoriten-Sternchen: markiert einen Prozess als «Standard» (gilt für
 *  ALLE Artikel). Default aus – in aller Regel ist ein Prozess artikelbezogen. */
function StarToggle({ on, onClick, disabled }: { on: boolean; onClick?: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled || !onClick}
      title={on ? 'Standard – gilt für alle Artikel (Stern entfernt die Markierung)' : 'Als Standard markieren (gilt für alle Artikel)'}
      style={{ border: 'none', background: 'none', cursor: (disabled || !onClick) ? 'default' : 'pointer', padding: 2, lineHeight: 0, flexShrink: 0 }}>
      <Star size={16} fill={on ? '#f59e0b' : 'none'} color={on ? '#f59e0b' : '#cbd5e1'} strokeWidth={2} />
    </button>
  );
}

/** Prozess als eigenständiges Objekt (Feed «Prozesse»): anlegen, Schritte definieren,
 *  freigeben/deaktivieren/ersetzen. Es gibt **keine** Quellen-/Richtungswahl – die Lager-
 *  Richtung ergibt sich aus den Schritten. «Standard» ist ein seltenes Favoriten-Sternchen. */
export function ProcessDetail({ record, suppliers, onSaved, onBack }: {
  record: Process | null;
  suppliers: UserProfile[];
  onSaved: (p: Process) => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [name, setName] = useState(record?.name ?? '');
  const [isStandard, setIsStandard] = useState<boolean>(record?.is_standard ?? false);
  const [stepCount, setStepCount] = useState<number>(record?.step_count ?? 0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const status = record?.status ?? 'draft';
  const editable = status === 'draft';

  async function create() {
    if (!name.trim()) { setError('Bitte einen Namen angeben'); return; }
    setSaving(true); setError(null);
    try { onSaved(await api.createProcess({ name: name.trim(), is_standard: isStandard })); }
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
          <TextField label="Name (frei wählbar)" value={name} onChange={setName} required placeholder="z. B. Entstehung, Verkauf, Wartung, Umlagern" />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <StarToggle on={isStandard} onClick={() => setIsStandard((v) => !v)} />
            <span style={{ fontSize: 13, color: '#475569' }}>Als <b>Standard</b> markieren — gilt automatisch für alle Artikel <span style={{ color: '#94a3b8' }}>(selten)</span></span>
          </label>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            Keine Quellen-/Richtungswahl: ob der Prozess Bestand erhöht, mindert oder neutral
            ist, ergibt sich automatisch aus den Schritten (nach dem Anlegen definieren).
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 15, fontWeight: 700, color: '#0f172a' }}>{record!.name}</span>
              <StarToggle on={record!.is_standard} onClick={editable ? () => patch({ is_standard: !record!.is_standard }) : undefined} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: '#475569' }}>{fmtObjId(record!.object_id)}</span>
              <StatusBadge cfg={processStatusConfig(status)} />
              <span style={{ fontSize: 11, color: '#94a3b8' }}>Subjekt: {sourceLabel(record!.source)}</span>
              {record!.linked_article_count > 0 && (
                <span style={{ fontSize: 11, color: '#94a3b8' }}>· bei {record!.linked_article_count} Artikel{record!.linked_article_count === 1 ? '' : 'n'}</span>
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
          </div>
        )}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#94a3b8', marginBottom: 8 }}>
            Schritte <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>— bestimmen die Richtung des Prozesses</span>
          </div>
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
