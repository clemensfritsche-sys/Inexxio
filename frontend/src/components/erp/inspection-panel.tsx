'use client';

import { useState } from 'react';
import { ClipboardCheck, Lock, CheckCircle2, XCircle, Info, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import type { CaptureField, InspectionSampleInput, Order } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { Label } from '@/components/erp/fields';

type Val = string | number | boolean | undefined;

function measureOk(f: CaptureField, v: Val): boolean {
  if (v == null || v === '') return false;
  const n = Number(v);
  if (!Number.isFinite(n)) return false;
  if (f.target == null) return true;          // nur erfasst, kein Soll
  return Math.abs(n - f.target) <= (f.tolerance ?? 0);
}
function fieldOk(f: CaptureField, v: Val): boolean {
  if (f.type === 'measure') return measureOk(f, v);
  if (f.type === 'bool') return v === true;
  return true; // text
}

// Schlüssel je Stichprobe (Instanz + Probe-Nr.)
const sKey = (instanceId: number, slot: number) => `${instanceId}:${slot}`;

export function InspectionPanel({ order, stepState, onOrderUpdated }: {
  order: Order;
  stepState: string;
  onOrderUpdated: (o: Order) => void;
}) {
  const insp = order.inspection;
  const fields = (insp?.fields ?? []) as CaptureField[];
  const samples = insp?.samples ?? [];
  const required = insp?.required_count ?? 0;
  const pct = insp?.sample_percent ?? 100;
  const result = insp?.result ?? 'pending';
  const done = result === 'passed' || result === 'failed';
  const qty = order.quantity || 0;
  const isBatch = order.article_serialization === 'batch';
  const escalated = insp?.escalated ?? false;

  // Werte je Stichprobe: { "instanceId:slot": { fieldKey: value } }
  const [values, setValues] = useState<Record<string, Record<string, Val>>>(() => {
    const init: Record<string, Record<string, Val>> = {};
    samples.forEach((s) => { init[sKey(s.instance_id, s.slot)] = { ...(s.values as Record<string, Val>) }; });
    return init;
  });
  const [note, setNote] = useState(insp?.note ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setVal(key: string, fieldKey: string, v: Val) {
    setValues((p) => ({ ...p, [key]: { ...(p[key] ?? {}), [fieldKey]: v } }));
  }

  function sampleOk(key: string): boolean {
    return fields.every((f) => fieldOk(f, values[key]?.[f.key]));
  }
  const allOk = samples.every((s) => sampleOk(sKey(s.instance_id, s.slot)));

  function sampleLabel(instanceId: number, slot: number): string {
    return isBatch ? `Charge ${fmtObjId(instanceId)} · Probe ${slot}` : `Unit ${fmtObjId(instanceId)}`;
  }

  async function submit() {
    setSaving(true); setError(null);
    try {
      const payload: InspectionSampleInput[] = samples.map((s) => {
        const key = sKey(s.instance_id, s.slot);
        const out: Record<string, unknown> = {};
        fields.forEach((f) => {
          const v = values[key]?.[f.key];
          if (f.type === 'measure') out[f.key] = v === '' || v == null ? null : Number(v);
          else if (f.type === 'bool') out[f.key] = v === true;
          else out[f.key] = v ?? '';
        });
        return { instance_id: s.instance_id, slot: s.slot, values: out };
      });
      onOrderUpdated(await api.updateOrderInspection(order.object_id as number, {
        samples: payload, note: note.trim() || null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
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

  return (
    <div style={cardStyle}>
      <Header />

      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#374151' }}>
        Prüfumfang: <b>{required}</b> von {qty} Stück <span style={{ color: '#94a3b8' }}>({escalated ? '100 % – hochgestuft' : `${pct}% Stichprobe`})</span>
        {isBatch && required > 1 && <span style={{ color: '#94a3b8' }}> · {required} Proben aus der Charge</span>}
      </div>

      {escalated && !done && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', fontSize: 12 }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Eine Stichprobe war ungenügend – die Prüfung wurde auf <b>100 %</b> hochgestuft. Bitte alle aufgeführten Instanzen erfassen.</span>
        </div>
      )}

      {/* Ergebnis-Banner */}
      {done && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8,
          background: result === 'passed' ? '#f0fdf4' : '#fef2f2', color: result === 'passed' ? '#16a34a' : '#dc2626' }}>
          {result === 'passed' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          <span style={{ fontSize: 13, fontWeight: 700 }}>{result === 'passed' ? 'Bestanden' : 'Durchgefallen'}</span>
          {insp?.checked_count != null && <span style={{ fontSize: 12, color: '#64748b' }}>· {insp.checked_count} geprüft</span>}
          {insp?.inspector_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{insp.inspector_name}</span>}
        </div>
      )}

      {samples.length === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Info size={14} /> Noch keine Instanzen vorhanden.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 380, overflowY: 'auto' }}>
          {samples.map((s) => {
            const key = sKey(s.instance_id, s.slot);
            const ok = sampleOk(key);
            return (
              <div key={key} style={{ border: `1px solid ${done ? (ok ? '#bbf7d0' : '#fecaca') : '#e2e8f0'}`, borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569', flex: 1 }}>{sampleLabel(s.instance_id, s.slot)}</span>
                  {!done && (ok ? <CheckCircle2 size={15} style={{ color: '#16a34a' }} /> : <XCircle size={15} style={{ color: '#cbd5e1' }} />)}
                </div>
                {fields.map((f) => (
                  <CaptureRow key={f.key} field={f} value={values[key]?.[f.key]} ok={fieldOk(f, values[key]?.[f.key])}
                    readOnly={done} onChange={(v) => setVal(key, f.key, v)} />
                ))}
              </div>
            );
          })}
        </div>
      )}

      {/* Notiz */}
      {!done && samples.length > 0 && (
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz (optional)"
          className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
      )}
      {done && insp?.note && <div style={{ fontSize: 12, color: '#64748b' }}>Notiz: {insp.note}</div>}

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {/* Aktion */}
      {!done && samples.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
          <span style={{ flex: 1, fontSize: 12, color: allOk ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
            Vorschau: {allOk ? 'Bestanden' : 'Durchgefallen'}
          </span>
          <button onClick={submit} disabled={saving}
            style={{ padding: '7px 16px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
            {saving ? '…' : 'Erfassung abschliessen'}
          </button>
        </div>
      )}
    </div>
  );
}

function CaptureRow({ field, value, onChange, ok, readOnly }: {
  field: CaptureField; value: Val; onChange: (v: Val) => void; ok: boolean; readOnly?: boolean;
}) {
  const filled = value != null && value !== '';
  if (field.type === 'bool') {
    return (
      <div>
        <Label>{field.label}</Label>
        <div style={{ display: 'flex', gap: 6 }}>
          <Toggle label="Gut" active={value === true} tone="ok" disabled={readOnly} onClick={() => onChange(true)} />
          <Toggle label="Schlecht" active={value === false} tone="bad" disabled={readOnly} onClick={() => onChange(false)} />
        </div>
      </div>
    );
  }
  if (field.type === 'text') {
    return (
      <div>
        <Label>{field.label}</Label>
        <input value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} disabled={readOnly}
          className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
      </div>
    );
  }
  // measure
  const soll = field.target != null ? `Soll ${field.target}${field.tolerance != null ? ` ± ${field.tolerance}` : ''}${field.unit ? ` ${field.unit}` : ''}` : 'Messwert erfassen';
  return (
    <div>
      <Label>{field.label}</Label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} inputMode="decimal" disabled={readOnly} placeholder={field.unit ? `Ist (${field.unit})` : 'Ist'}
          className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          style={{ borderColor: filled && field.target != null ? (ok ? '#86efac' : '#fca5a5') : '#e2e8f0', width: 120 }} />
        <span style={{ fontSize: 12, color: '#94a3b8', flex: 1 }}>{soll}</span>
        {filled && field.target != null && (
          ok ? <CheckCircle2 size={15} style={{ color: '#16a34a' }} /> : <XCircle size={15} style={{ color: '#dc2626' }} />
        )}
      </div>
    </div>
  );
}

function Toggle({ label, active, tone, onClick, disabled }: { label: string; active: boolean; tone: 'ok' | 'bad'; onClick: () => void; disabled?: boolean }) {
  const color = tone === 'ok' ? '#16a34a' : '#dc2626';
  const bg = tone === 'ok' ? '#f0fdf4' : '#fef2f2';
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      style={{ padding: '6px 14px', borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: disabled ? 'default' : 'pointer',
        border: `1px solid ${active ? color : '#e2e8f0'}`, background: active ? bg : '#fff', color: active ? color : '#64748b' }}>
      {label}
    </button>
  );
}

function Header() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <ClipboardCheck size={15} style={{ color: '#2563eb' }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Datenerfassung</span>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
