'use client';

import { useEffect, useState } from 'react';
import { ShoppingCart, Plus, Trash2, Link2, User as UserIcon, Info, Eye, Check } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleProcessStep, ProcessStepMode, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { PROCESS_MODE_LABEL } from '@/lib/purchase-order';
import { SUPPLIER_FIELD_CATALOG, MANDATORY_FIELD_KEYS, normalizeSharedFields, fieldLabel } from '@/lib/article-fields';
import { ErrorText, Label, Segmented, SelectField, TextField } from '@/components/erp/fields';

export function ProcessSteps({ articleObjectId, suppliers }: {
  articleObjectId: number | null;
  suppliers: UserProfile[];
}) {
  const [steps, setSteps] = useState<ArticleProcessStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [mode, setMode] = useState<ProcessStepMode>('supplier');
  const [supplierId, setSupplierId] = useState('');
  const [url, setUrl] = useState('');
  const [shared, setShared] = useState<string[]>(MANDATORY_FIELD_KEYS);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editShared, setEditShared] = useState<string[]>(MANDATORY_FIELD_KEYS);

  useEffect(() => {
    if (articleObjectId == null) return;
    setLoading(true);
    api.getArticleProcessSteps(articleObjectId)
      .then(setSteps)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [articleObjectId]);

  if (articleObjectId == null) {
    return (
      <div style={noticeStyle}>
        <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Artikel zuerst speichern – danach lassen sich Prozessschritte hinterlegen.</span>
      </div>
    );
  }

  function resetForm() {
    setAdding(false); setMode('supplier'); setSupplierId(''); setUrl('');
    setShared(MANDATORY_FIELD_KEYS); setError(null);
  }

  async function addStep() {
    setError(null);
    if (mode === 'supplier' && !supplierId) { setError('Bitte einen Lieferanten wählen'); return; }
    if (mode === 'webshop' && !url.trim()) { setError('Bitte einen Webshop-Link angeben'); return; }
    setSaving(true);
    try {
      const created = await api.createArticleProcessStep(articleObjectId as number, {
        mode,
        supplier_id: mode === 'supplier' ? Number(supplierId) : null,
        webshop_url: mode === 'webshop' ? url.trim() : null,
        shared_fields: shared,
      });
      setSteps((p) => [...p, created]);
      resetForm();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  async function removeStep(stepId: number) {
    try {
      await api.deleteArticleProcessStep(articleObjectId as number, stepId);
      setSteps((p) => p.filter((s) => s.id !== stepId));
    } catch { /* ignore */ }
  }

  async function saveShared(stepId: number) {
    try {
      const updated = await api.updateArticleProcessStep(articleObjectId as number, stepId, { shared_fields: editShared });
      setSteps((p) => p.map((s) => (s.id === stepId ? updated : s)));
      setEditId(null);
    } catch { /* ignore */ }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={infoStyle}>
        <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Diese Schritte definieren, wie der Artikel beschafft wird. Wird ein Auftrag mit
          diesem Artikel freigegeben, startet der Prozess automatisch.</span>
      </div>

      {loading && <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>}

      {steps.map((s, i) => (
        <div key={s.id} style={{ ...cardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ShoppingCart size={17} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>{i + 1}. Bestellung (Purchase Order)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3, fontSize: 12, color: '#64748b' }}>
                {s.mode === 'supplier'
                  ? <><UserIcon size={12} /> {PROCESS_MODE_LABEL.supplier}: {s.supplier_name ?? `#${s.supplier_id}`}</>
                  : <><Link2 size={12} /> {PROCESS_MODE_LABEL.webshop}</>}
              </div>
              {s.mode === 'webshop' && s.webshop_url && (
                <a href={s.webshop_url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: '#2563eb', wordBreak: 'break-all' }}>{s.webshop_url}</a>
              )}
            </div>
            <button onClick={() => removeStep(s.id)} title="Entfernen"
              style={{ flexShrink: 0, border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}>
              <Trash2 size={15} />
            </button>
          </div>

          {/* Sichtbare Stammdaten */}
          <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#94a3b8' }}>
                <Eye size={12} /> Für Lieferant sichtbar
              </span>
              {editId === s.id ? (
                <button onClick={() => saveShared(s.id)} style={miniPrimary}><Check size={12} /> Speichern</button>
              ) : (
                <button onClick={() => { setEditId(s.id); setEditShared(normalizeSharedFields(s.shared_fields)); }} style={miniGhost}>Ändern</button>
              )}
            </div>
            {editId === s.id ? (
              <FieldChips value={editShared} onChange={setEditShared} />
            ) : (
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {normalizeSharedFields(s.shared_fields).map((k) => <Chip key={k} label={fieldLabel(k)} on />)}
              </div>
            )}
          </div>
        </div>
      ))}

      {!adding ? (
        <button onClick={() => setAdding(true)} style={addBtnStyle}>
          <Plus size={15} /> Prozessschritt «Bestellung» hinzufügen
        </button>
      ) : (
        <div style={{ ...cardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 14 }}>
          <Segmented label="Bezugsquelle" value={mode} onChange={(v) => setMode(v as ProcessStepMode)}
            options={[{ value: 'supplier', label: 'Lieferant' }, { value: 'webshop', label: 'Webshop-Link' }]} required />
          {mode === 'supplier' ? (
            suppliers.length > 0 ? (
              <SelectField label="Lieferant" value={supplierId} onChange={setSupplierId} required
                options={[{ value: '', label: '— wählen —' }, ...suppliers.map((u) => ({ value: String(u.id), label: userDisplayName(u) }))]} />
            ) : (
              <div style={noticeStyle}>
                <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>Keine Benutzer mit Rolle «Lieferant» vorhanden. Bitte zuerst einen Lieferanten anlegen oder Webshop-Link nutzen.</span>
              </div>
            )
          ) : (
            <TextField label="Webshop-Link" value={url} onChange={setUrl} required placeholder="https://shop.example.com/artikel" />
          )}
          <div>
            <Label>Für den Lieferanten sichtbare Stammdaten</Label>
            <FieldChips value={shared} onChange={setShared} />
          </div>
          {error && <ErrorText msg={error} />}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={resetForm} style={secondaryBtn}>Abbrechen</button>
            <button onClick={addStep} disabled={saving} style={primaryBtn}>{saving ? 'Speichern…' : 'Hinzufügen'}</button>
          </div>
        </div>
      )}
    </div>
  );
}

// Tag-Auswahl der Stammdaten; Pflichtfelder sind gesperrt (immer sichtbar).
function FieldChips({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const optional = SUPPLIER_FIELD_CATALOG.filter((f) => !f.mandatory);
  function toggle(key: string) {
    const set = new Set(value);
    if (set.has(key)) set.delete(key); else set.add(key);
    onChange(normalizeSharedFields([...set]));
  }
  return (
    <div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {SUPPLIER_FIELD_CATALOG.map((f) => (
          <Chip key={f.key} label={f.mandatory ? `${f.label} · Pflicht` : f.label}
            on={f.mandatory || value.includes(f.key)} locked={f.mandatory}
            onClick={f.mandatory ? undefined : () => toggle(f.key)} />
        ))}
      </div>
      <div style={{ marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
        Pflicht-Stammdaten sind für den Lieferanten immer sichtbar.
        {optional.length === 0 && ' Weitere (optionale) Felder können künftig hier freigegeben werden.'}
      </div>
    </div>
  );
}

function Chip({ label, on, locked, onClick }: { label: string; on?: boolean; locked?: boolean; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      style={{
        padding: '3px 9px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        border: `1px solid ${on ? '#bfdbfe' : '#e2e8f0'}`,
        background: on ? '#eff6ff' : '#fff', color: on ? '#2563eb' : '#94a3b8',
        cursor: onClick ? 'pointer' : 'default', opacity: locked ? 0.85 : 1,
      }}>
      {label}
    </button>
  );
}

const cardStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, background: '#fff',
  border: '1px solid #E2E8F0', borderRadius: 10, padding: '12px 14px',
};
const infoStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px',
  background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 12, color: '#1e40af',
};
const noticeStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '12px 14px',
  background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, fontSize: 13, color: '#92400e',
};
const addBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px',
  borderRadius: 10, border: '1px dashed #cbd5e1', background: '#fff', color: '#2563eb',
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const primaryBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: 'none', background: '#2563eb',
  color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const secondaryBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff',
  color: '#374151', fontSize: 13, cursor: 'pointer',
};
const miniPrimary: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4, padding: '3px 9px', borderRadius: 6,
  border: 'none', background: '#2563eb', color: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer',
};
const miniGhost: React.CSSProperties = {
  padding: '3px 9px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff',
  color: '#475569', fontSize: 11, fontWeight: 600, cursor: 'pointer',
};
