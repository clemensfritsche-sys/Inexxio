'use client';

import { useState } from 'react';
import { ClipboardCheck, Lock, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '@/lib/api';
import type { CaptureField, Order } from '@/types';
import { TextField, Label } from '@/components/erp/fields';

type Val = string | boolean | undefined;

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

export function InspectionPanel({ order, stepState, onOrderUpdated }: {
  order: Order;
  stepState: string;
  onOrderUpdated: (o: Order) => void;
}) {
  const insp = order.inspection;
  const fields = (insp?.fields ?? []) as CaptureField[];
  const required = insp?.required_count ?? 0;
  const pct = insp?.sample_percent ?? 100;
  const result = insp?.result ?? 'pending';
  const done = result === 'passed' || result === 'failed';
  const qty = order.quantity || 0;

  const [values, setValues] = useState<Record<string, Val>>(() => ({ ...(insp?.values ?? {}) }));
  const [checked, setChecked] = useState(insp?.checked_count != null ? String(insp.checked_count) : '');
  const [note, setNote] = useState(insp?.note ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setVal(key: string, v: Val) { setValues((p) => ({ ...p, [key]: v })); }

  const allOk = fields.every((f) => fieldOk(f, values[f.key]));

  async function submitTemplated() {
    const checkedNum = checked.trim() === '' ? 0 : Math.trunc(Number(checked));
    if (allOk && checkedNum < required) { setError(`Bei Freigabe mindestens ${required} Stück prüfen`); return; }
    setSaving(true); setError(null);
    try {
      const payloadValues: Record<string, unknown> = {};
      fields.forEach((f) => {
        const v = values[f.key];
        if (f.type === 'measure') payloadValues[f.key] = v === '' || v == null ? null : Number(v);
        else if (f.type === 'bool') payloadValues[f.key] = v === true;
        else payloadValues[f.key] = v ?? '';
      });
      onOrderUpdated(await api.updateOrderInspection(order.object_id as number, {
        values: payloadValues,
        checked_count: checked.trim() === '' ? null : checkedNum,
        note: note.trim() || null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally { setSaving(false); }
  }

  async function submitSimple(res: 'passed' | 'failed') {
    const checkedNum = checked.trim() === '' ? 0 : Math.trunc(Number(checked));
    if (res === 'passed' && checkedNum < required) { setError(`Bei Freigabe mindestens ${required} Stück prüfen`); return; }
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderInspection(order.object_id as number, {
        result: res, checked_count: checked.trim() === '' ? null : checkedNum, note: note.trim() || null,
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
        Prüfumfang: <b>{required}</b> von {qty} Stück <span style={{ color: '#94a3b8' }}>({pct}% Stichprobe)</span>
      </div>

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

      {/* Erfassungsfelder (Maske) */}
      {fields.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {fields.map((f) => (
            <CaptureRow key={f.key} field={f} value={values[f.key]} onChange={(v) => setVal(f.key, v)} ok={fieldOk(f, values[f.key])} />
          ))}
        </div>
      )}

      {/* Stichprobe + Notiz */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 14 }}>
        <TextField label="Geprüft (Stück)" value={checked} onChange={setChecked} placeholder={String(required)} />
        <TextField label="Notiz (optional)" value={note} onChange={setNote} placeholder="Bemerkung" />
      </div>

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {/* Aktionen */}
      {fields.length > 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
          <span style={{ flex: 1, fontSize: 12, color: allOk ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
            Vorschau: {allOk ? 'Bestanden' : 'Durchgefallen'}
          </span>
          <button onClick={submitTemplated} disabled={saving}
            style={{ padding: '7px 16px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
            {saving ? '…' : 'Erfassung abschliessen'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={() => submitSimple('failed')} disabled={saving}
            style={{ padding: '7px 14px', borderRadius: 7, border: '1px solid #fecaca', background: '#fff', color: '#dc2626', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
            Durchgefallen
          </button>
          <button onClick={() => submitSimple('passed')} disabled={saving}
            style={{ padding: '7px 14px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#16a34a', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
            {saving ? '…' : 'Bestanden'}
          </button>
        </div>
      )}
    </div>
  );
}

function CaptureRow({ field, value, onChange, ok }: {
  field: CaptureField; value: Val; onChange: (v: Val) => void; ok: boolean;
}) {
  const filled = value != null && value !== '';
  if (field.type === 'bool') {
    return (
      <div>
        <Label>{field.label}</Label>
        <div style={{ display: 'flex', gap: 6 }}>
          <Toggle label="Gut" active={value === true} tone="ok" onClick={() => onChange(true)} />
          <Toggle label="Schlecht" active={value === false} tone="bad" onClick={() => onChange(false)} />
        </div>
      </div>
    );
  }
  if (field.type === 'text') {
    return (
      <div>
        <Label>{field.label}</Label>
        <input value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)}
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
        <input value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} inputMode="decimal" placeholder={field.unit ? `Ist (${field.unit})` : 'Ist'}
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

function Toggle({ label, active, tone, onClick }: { label: string; active: boolean; tone: 'ok' | 'bad'; onClick: () => void }) {
  const color = tone === 'ok' ? '#16a34a' : '#dc2626';
  const bg = tone === 'ok' ? '#f0fdf4' : '#fef2f2';
  return (
    <button type="button" onClick={onClick}
      style={{ padding: '6px 14px', borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: 'pointer',
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
