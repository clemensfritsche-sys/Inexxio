'use client';

import { useEffect, useState } from 'react';
import { ShoppingCart, Plus, Trash2, Link2, User as UserIcon, Info } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleProcessStep, ProcessStepMode, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { PROCESS_MODE_LABEL } from '@/lib/purchase-order';
import { ErrorText, Segmented, SelectField, TextField } from '@/components/erp/fields';

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
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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
    setAdding(false); setMode('supplier'); setSupplierId(''); setUrl(''); setError(null);
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={infoStyle}>
        <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Diese Schritte definieren, wie der Artikel beschafft wird. Wird ein Auftrag mit
          diesem Artikel freigegeben, startet der Prozess automatisch.</span>
      </div>

      {loading && <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>}

      {steps.map((s, i) => (
        <div key={s.id} style={cardStyle}>
          <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShoppingCart size={17} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>
              {i + 1}. Bestellung (Purchase Order)
            </div>
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
