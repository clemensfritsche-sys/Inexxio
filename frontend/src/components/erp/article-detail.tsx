'use client';

import { useEffect, useState } from 'react';
import { Package, ArrowLeft, FileText, Workflow, Boxes, Lock, Loader2, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleStatus, ArticleUnit, ArticleSerialization, UserProfile } from '@/types';
import {
  ARTICLE_UNITS, SERIALIZATION_OPTIONS, statusConfig,
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import type { StatusAction } from '@/lib/status-flow';
import { lifecycleActions } from '@/lib/status-flow';
import { useAutosave } from '@/lib/use-autosave';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, SelectField, Segmented, StatusBadge, StatusFlow, Label, ErrorText } from '@/components/erp/fields';
import { ProcessSteps } from '@/components/erp/process-steps';
import { InstanceList } from '@/components/erp/instance-list';

// Artikel-Lebenszyklus: Freigabe erst möglich, wenn mindestens ein Prozessschritt existiert.
function articleActions(status: string, canRelease: boolean): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
      hint: canRelease ? undefined : 'Erst einen Prozessschritt hinzufügen' }];
  return lifecycleActions(status);
}

type TabKey = 'stammdaten' | 'prozess' | 'bestand';

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'stammdaten', label: 'Stammdaten', icon: FileText },
  { key: 'prozess', label: 'Prozess', icon: Workflow },
  { key: 'bestand', label: 'Bestand', icon: Boxes },
];

type Form = { name: string; unit: string; serialization: string; size: string; weight_kg: string };

function seedFrom(record: Article | null): Form {
  if (!record) return { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '' };
  return {
    name: record.name, unit: record.unit, serialization: record.serialization,
    size: record.size, weight_kg: record.weight_kg,
  };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function ArticleDetail({ record, suppliers = [], articleNames = [], onSaved, onCancel, onBack }: {
  record: Article | null;          // null ⇒ Anlage-Modus
  suppliers?: UserProfile[];
  articleNames?: string[];         // wählbare Artikelnamen (Systemkonfiguration)
  onSaved: (a: Article) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [tab, setTab] = useState<TabKey>('stammdaten');
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [savedSig, setSavedSig] = useState<string>(() => (isCreate ? '' : JSON.stringify(seedFrom(record))));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepCount, setStepCount] = useState<number | null>(isCreate ? 0 : null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  // Anzahl Prozessschritte für die Freigabe-Bedingung laden
  useEffect(() => {
    if (record?.object_id == null) return;
    api.getArticleProcessSteps(record.object_id).then((s) => setStepCount(s.length)).catch(() => {});
  }, [record?.object_id]);

  // Nach der Freigabe ist der Artikel schreibgeschützt (keine Versionierung).
  const locked = !isCreate && record !== null && record.status !== 'draft';

  const errs = {
    name: validateName(form.name),
    size: validateSize(form.size),
    weight: validateWeight(form.weight_kg),
  };
  const valid = !errs.name && !errs.size && !errs.weight;
  const canRelease = (stepCount ?? 0) > 0;

  const sig = JSON.stringify({
    name: form.name.trim(), unit: form.unit, serialization: form.serialization,
    size: normalizeSize(form.size), weight_kg: normalizeWeight(form.weight_kg),
  });
  const canSave = !locked && valid && sig !== savedSig && !saving;

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      onSaved(await api.updateArticle(record.object_id as number, { status: target as ArticleStatus }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
    } finally {
      setStatusBusy(false);
    }
  }

  async function save() {
    if (!valid) return;
    const current = sig;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        unit: form.unit as ArticleUnit,
        serialization: form.serialization as ArticleSerialization,
        size: normalizeSize(form.size),
        weight_kg: normalizeWeight(form.weight_kg),
      };
      if (isCreate) {
        onSaved(await api.createArticle(payload));
      } else {
        onSaved(await api.updateArticle(record.object_id as number, payload));
        setSavedSig(current);
        setFlash(true);
        setTimeout(() => setFlash(false), 700);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const flush = useAutosave(sig, canSave, save);

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
                <StatusFlow cfg={statusConfig(record.status)} actions={articleActions(record.status, canRelease)} busy={statusBusy} onAction={changeStatus} />
              )}
              <SaveIndicator saving={saving} flash={flash} />
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
      <div onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'stammdaten' && (
          <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {locked ? (
              <>
                <div style={lockedNotice}>
                  <Lock size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>Artikel ist freigegeben und schreibgeschützt. Für Änderungen einen neuen Artikel anlegen.</span>
                </div>
                <Row k="Name" v={record!.name} />
                <Row k="Einheit" v={unitLabel(record!.unit)} />
                <Row k="Seriennummererfassung" v={serializationLabel(record!.serialization)} />
                <Row k="Grösse" v={record!.size} />
                <Row k="Gewicht" v={`${record!.weight_kg} kg`} />
              </>
            ) : (
              <>
                <div>
                  <SelectField label="Name" value={form.name} onChange={(v) => set('name', v)} required
                    options={[
                      { value: '', label: '— Artikelname wählen —' },
                      ...(form.name && !articleNames.includes(form.name) ? [{ value: form.name, label: form.name }] : []),
                      ...articleNames.map((n) => ({ value: n, label: n })),
                    ]} />
                  {articleNames.length === 0 && (
                    <div style={{ marginTop: 6, fontSize: 11, color: '#92400e' }}>
                      Keine Artikelnamen hinterlegt – bitte in Admin → Einstellungen → «Artikelnamen» anlegen.
                    </div>
                  )}
                  {errs.name && form.name !== '' && <ErrorText msg={errs.name} />}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <SelectField label="Einheit" value={form.unit} onChange={(v) => set('unit', v)} options={ARTICLE_UNITS} required />
                  <Segmented label="Seriennummererfassung" value={form.serialization} onChange={(v) => set('serialization', v)} options={SERIALIZATION_OPTIONS} required />
                </div>
                <TextField label="Grösse (mm)" value={form.size} onChange={(v) => set('size', v)} required placeholder="z. B. 3x40x600" hint="Masse in Millimeter (mm), aufsteigend & mit 'x' getrennt" error={form.size ? errs.size : null} />
                <TextField label="Gewicht (kg)" value={form.weight_kg} onChange={(v) => set('weight_kg', v)} required placeholder="z. B. 2.5" hint="Grösser als 0, max. 3 Nachkommastellen" error={form.weight_kg ? errs.weight : null} />
              </>
            )}
            {!isCreate && <PriceRange record={record!} />}
          </div>
        )}
        {tab === 'prozess' && (
          <ProcessSteps articleObjectId={record?.object_id ?? null} suppliers={suppliers} readOnly={locked} onStepsCount={setStepCount} />
        )}
        {tab === 'bestand' && (
          <InstanceList articleObjectId={record?.object_id ?? null} unit={record ? unitLabel(record.unit) : undefined} />
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

      {/* Footer-Status (Auto-Save, kein manueller Speichern-Knopf) */}
      {!locked && tab === 'stammdaten' && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (!valid ? 'Pflichtfelder: Name, Grösse, Gewicht' : isCreate ? 'Wird automatisch angelegt, sobald vollständig' : 'Änderungen werden automatisch gespeichert')}
          </span>
          {isCreate && (
            <button onClick={onCancel}
              style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}>
              Abbrechen
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function SaveIndicator({ saving, flash }: { saving: boolean; flash: boolean }) {
  if (saving) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}><Loader2 size={12} className="animate-spin" /> Speichert…</span>;
  if (flash) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#16a34a' }}><CheckCircle2 size={12} /> Gespeichert</span>;
  return null;
}

const lockedNotice: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px',
  background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 8,
  fontSize: 12, color: '#475569',
};

function fmtChf(v: string | number): string {
  return Number(v).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function PriceRange({ record }: { record: Article }) {
  const low = record.unit_cost_low;
  const high = record.unit_cost_high;
  if (low == null && high == null) return null;
  const same = low == null || high == null || Number(low) === Number(high);
  return (
    <div>
      <Label>Stückpreis netto / Stück</Label>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#0f766e' }}>
        {same ? `CHF ${fmtChf((low ?? high) as string | number)}` : `CHF ${fmtChf(low as string | number)} – ${fmtChf(high as string | number)}`}
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
        {same
          ? 'Aus akzeptierten Bestellungen – ohne MWST.'
          : 'Spanne über akzeptierte Bestellungen: kleinste bis grösste Bestellmenge – ohne MWST.'}
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
