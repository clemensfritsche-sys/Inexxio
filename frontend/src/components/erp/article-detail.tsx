'use client';

import { useState } from 'react';
import { Package, ArrowLeft, FileText, Workflow, Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleStatus, ArticleUnit, ArticleSerialization, ArticleUpdateInput, UserProfile } from '@/types';
import {
  ARTICLE_UNITS, SERIALIZATION_OPTIONS, ARTICLE_STATUS_ORDER, statusConfig,
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, SelectField, Segmented, StatusBadge, Placeholder, Label } from '@/components/erp/fields';
import { ProcessSteps } from '@/components/erp/process-steps';

type TabKey = 'stammdaten' | 'prozess' | 'bestand';

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'stammdaten', label: 'Stammdaten', icon: FileText },
  { key: 'prozess', label: 'Prozess', icon: Workflow },
  { key: 'bestand', label: 'Bestand', icon: Boxes },
];

type Form = { name: string; unit: string; serialization: string; size: string; weight_kg: string; status: string };

function seedFrom(record: Article | null): Form {
  if (!record) return { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '', status: 'draft' };
  return {
    name: record.name, unit: record.unit, serialization: record.serialization,
    size: record.size, weight_kg: record.weight_kg, status: record.status,
  };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function ArticleDetail({ record, suppliers = [], onSaved, onCancel, onBack }: {
  record: Article | null;          // null ⇒ Anlage-Modus
  suppliers?: UserProfile[];
  onSaved: (a: Article) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [tab, setTab] = useState<TabKey>('stammdaten');
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  const errs = {
    name: validateName(form.name),
    size: validateSize(form.size),
    weight: validateWeight(form.weight_kg),
  };
  const valid = !errs.name && !errs.size && !errs.weight;
  const showErrors = !isCreate || touched;

  const dirty = isCreate || (record !== null && (
    form.name !== record.name ||
    form.unit !== record.unit ||
    form.serialization !== record.serialization ||
    normalizeSize(form.size) !== record.size ||
    normalizeWeight(form.weight_kg) !== record.weight_kg ||
    form.status !== record.status
  ));

  async function save() {
    setTouched(true);
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      if (isCreate) {
        const created = await api.createArticle({
          name: form.name.trim(),
          unit: form.unit as ArticleUnit,
          serialization: form.serialization as ArticleSerialization,
          size: normalizeSize(form.size),
          weight_kg: normalizeWeight(form.weight_kg),
        });
        onSaved(created);
      } else {
        const payload: ArticleUpdateInput = {};
        if (form.name !== record.name) payload.name = form.name.trim();
        if (form.unit !== record.unit) payload.unit = form.unit as ArticleUnit;
        if (form.serialization !== record.serialization) payload.serialization = form.serialization as ArticleSerialization;
        if (normalizeSize(form.size) !== record.size) payload.size = normalizeSize(form.size);
        if (normalizeWeight(form.weight_kg) !== record.weight_kg) payload.weight_kg = normalizeWeight(form.weight_kg);
        if (form.status !== record.status) payload.status = form.status as ArticleStatus;
        const updated = await api.updateArticle(record.object_id as number, payload);
        onSaved(updated);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Package size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: form.name ? '#0F172A' : '#94a3b8', fontStyle: form.name ? 'normal' : 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {form.name || 'Neuer Artikel'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={statusConfig('draft')} />
              ) : (
                <select
                  value={form.status}
                  onChange={(e) => set('status', e.target.value)}
                  style={{ fontSize: 12, fontWeight: 600, padding: '2px 6px', borderRadius: 6, border: '1px solid #E2E8F0', background: '#fff', color: '#475569', cursor: 'pointer' }}
                >
                  {ARTICLE_STATUS_ORDER.map((s) => <option key={s} value={s}>{statusConfig(s).label}</option>)}
                </select>
              )}
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>
              {isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, marginTop: 12 }}>
          {TABS.map((t) => {
            const active = tab === t.key;
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  color: active ? '#2563eb' : '#64748b',
                  background: 'none', border: 'none',
                  borderBottom: `2px solid ${active ? '#2563eb' : 'transparent'}`,
                  marginBottom: -13,
                }}
              >
                <Icon size={14} /> {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        {tab === 'stammdaten' && (
          <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            <TextField label="Name" value={form.name} onChange={(v) => set('name', v)} required placeholder="z. B. Welle Antrieb" error={showErrors ? errs.name : null} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <SelectField label="Einheit" value={form.unit} onChange={(v) => set('unit', v)} options={ARTICLE_UNITS} required />
              <Segmented label="Seriennummererfassung" value={form.serialization} onChange={(v) => set('serialization', v)} options={SERIALIZATION_OPTIONS} required />
            </div>
            <TextField label="Grösse (mm)" value={form.size} onChange={(v) => set('size', v)} required placeholder="z. B. 3x40x600" hint="Masse in Millimeter (mm), aufsteigend & mit 'x' getrennt" error={showErrors ? errs.size : null} />
            <TextField label="Gewicht (kg)" value={form.weight_kg} onChange={(v) => set('weight_kg', v)} required placeholder="z. B. 2.5" hint="Grösser als 0, max. 3 Nachkommastellen" error={showErrors ? errs.weight : null} />
            {!isCreate && record?.landed_unit_cost != null && (
              <div>
                <Label>Einstandspreis netto / Stück (CHF)</Label>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0f766e' }}>
                  {Number(record.landed_unit_cost).toLocaleString('de-CH', { minimumFractionDigits: 2 })}
                </div>
                <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
                  Automatisch aus der zuletzt freigegebenen Bestellung – nur Lesen.
                </div>
              </div>
            )}
          </div>
        )}
        {tab === 'prozess' && (
          <ProcessSteps articleObjectId={record?.object_id ?? null} suppliers={suppliers} />
        )}
        {tab === 'bestand' && (
          <Placeholder icon={Boxes} title="Bestand" text="Lagerbestand und Bewegungen für diesen Artikel folgen in einer späteren Phase." />
        )}
      </div>

      {/* Meta footer (edit only) */}
      {!isCreate && (
        <div style={{ padding: '8px 20px', borderTop: '1px solid #E2E8F0', background: '#fff', flexShrink: 0, fontSize: 11, color: '#94a3b8', display: 'flex', gap: 16 }}>
          <span>Einheit: {unitLabel(record.unit)}</span>
          <span>Erfassung: {serializationLabel(record.serialization)}</span>
          <span>Erstellt: {localDate(record.created_at)}</span>
        </div>
      )}

      {/* Save bar */}
      {(isCreate || dirty || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : (showErrors && !valid) ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (isCreate ? 'Neuen Artikel erfassen' : (showErrors && !valid) ? 'Bitte Eingaben prüfen' : 'Ungespeicherte Änderungen')}
          </span>
          <button
            onClick={isCreate ? onCancel : () => { setForm(seedFrom(record)); setError(null); setTouched(false); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}
          >
            {isCreate ? 'Abbrechen' : 'Verwerfen'}
          </button>
          <button
            onClick={save}
            disabled={saving || (showErrors && !valid)}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving || (showErrors && !valid) ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}
          >
            {saving ? 'Speichern…' : isCreate ? 'Anlegen' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}
