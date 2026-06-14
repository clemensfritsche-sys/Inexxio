'use client';

import { useState, useEffect } from 'react';
import {
  Search, Plus, ArrowLeft, Package, Boxes, Workflow, FileText, X, AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import type {
  Article, ArticleInput, ArticleStatus, ArticleUnit, ArticleSerialization, ArticleUpdateInput,
} from '@/types';
import {
  ARTICLE_UNITS, SERIALIZATION_OPTIONS, ARTICLE_STATUS_ORDER, statusConfig,
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import { ErpTabs } from '@/components/erp/erp-tabs';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtObjId(id: number | null | undefined): string {
  if (!id) return '—';
  return String(id).padStart(9, '0');
}

function localDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('de-CH');
}

function StatusBadge({ status, size = 10 }: { status: string; size?: number }) {
  const sc = statusConfig(status);
  return (
    <span style={{
      fontSize: size, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
      background: sc.bg, color: sc.color, whiteSpace: 'nowrap',
    }}>
      {sc.label}
    </span>
  );
}

// ─── Reusable form fields ────────────────────────────────────────────────────

const inputCls = 'w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors';

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 4 }}>
      {children}{required && <span style={{ color: '#dc2626' }}> *</span>}
    </div>
  );
}

function ErrorText({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: '#dc2626' }}>
      <AlertCircle size={11} /> {msg}
    </div>
  );
}

function TextField({ label, value, onChange, error, placeholder, required, hint }: {
  label: string; value: string; onChange: (v: string) => void;
  error?: string | null; placeholder?: string; required?: boolean; hint?: string;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={inputCls}
        style={{ borderColor: error ? '#fca5a5' : '#e2e8f0' }}
      />
      {error ? <ErrorText msg={error} /> : hint ? (
        <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>{hint}</div>
      ) : null}
    </div>
  );
}

function SelectField({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} style={{ borderColor: '#e2e8f0' }}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function Segmented({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <div style={{ display: 'flex', gap: 6 }}>
        {options.map((o) => {
          const active = value === o.value;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(o.value)}
              style={{
                flex: 1, padding: '7px 10px', fontSize: 13, fontWeight: 600,
                borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${active ? '#2563eb' : '#e2e8f0'}`,
                background: active ? '#eff6ff' : '#fff',
                color: active ? '#2563eb' : '#64748b',
              }}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Create modal ────────────────────────────────────────────────────────────

const EMPTY_FORM: ArticleInput = { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '' };

function CreateModal({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: (a: Article) => void;
}) {
  const [form, setForm] = useState<ArticleInput>(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errs = {
    name: validateName(form.name),
    size: validateSize(form.size),
    weight: validateWeight(form.weight_kg),
  };
  const valid = !errs.name && !errs.size && !errs.weight;

  function upd<K extends keyof ArticleInput>(key: K, value: ArticleInput[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  async function submit() {
    setTouched(true);
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      const created = await api.createArticle({
        name: form.name.trim(),
        unit: form.unit,
        serialization: form.serialization,
        size: normalizeSize(form.size),
        weight_kg: normalizeWeight(form.weight_kg),
      });
      onCreated(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Anlegen');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15,23,42,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 440, background: '#fff', borderRadius: 14, boxShadow: '0 20px 60px rgba(0,0,0,0.25)', overflow: 'hidden' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px', borderBottom: '1px solid #E2E8F0' }}>
          <Package size={16} style={{ color: '#2563eb' }} />
          <span style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', flex: 1 }}>Neuer Artikel</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 4 }} aria-label="Schliessen">
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <TextField label="Name" value={form.name} onChange={(v) => upd('name', v)} required placeholder="z. B. Welle Antrieb" error={touched ? errs.name : null} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <SelectField label="Einheit" value={form.unit} onChange={(v) => upd('unit', v as ArticleUnit)} options={ARTICLE_UNITS} required />
            <Segmented label="Erfassung" value={form.serialization} onChange={(v) => upd('serialization', v as ArticleSerialization)} options={SERIALIZATION_OPTIONS} required />
          </div>
          <TextField label="Grösse" value={form.size} onChange={(v) => upd('size', v)} required placeholder="z. B. 3x40x600" hint="Zahlen aufsteigend, getrennt durch 'x'" error={touched ? errs.size : null} />
          <TextField label="Gewicht (kg)" value={form.weight_kg} onChange={(v) => upd('weight_kg', v)} required placeholder="z. B. 2.5" hint="Grösser als 0, max. 3 Nachkommastellen" error={touched ? errs.weight : null} />

          {error && <div style={{ fontSize: 13, color: '#dc2626' }}>{error}</div>}
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', padding: '12px 18px', borderTop: '1px solid #E2E8F0', background: '#F8FAFC' }}>
          <button onClick={onClose} style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer' }}>
            Abbrechen
          </button>
          <button
            onClick={submit}
            disabled={saving || (touched && !valid)}
            style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}
          >
            {saving ? 'Anlegen…' : 'Anlegen'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── List item ───────────────────────────────────────────────────────────────

function ArticleItem({ a, sel, onClick }: { a: Article; sel: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px', width: '100%', textAlign: 'left',
        background: sel ? '#EFF6FF' : 'transparent',
        borderLeft: `3px solid ${sel ? '#2563eb' : 'transparent'}`,
        borderBottom: '1px solid #F1F5F9', cursor: 'pointer',
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 8, flexShrink: 0,
        background: '#F1F5F9', color: '#64748b',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Package size={17} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {a.name}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
          <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: '#475569' }}>{fmtObjId(a.object_id)}</span>
          <StatusBadge status={a.status} />
        </div>
      </div>
    </button>
  );
}

// ─── Detail tabs ─────────────────────────────────────────────────────────────

type TabKey = 'stammdaten' | 'prozess' | 'bestand';

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'stammdaten', label: 'Stammdaten', icon: FileText },
  { key: 'prozess', label: 'Prozess', icon: Workflow },
  { key: 'bestand', label: 'Bestand', icon: Boxes },
];

function Placeholder({ icon: Icon, title, text }: { icon: React.ElementType; title: string; text: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: 24 }}>
      <Icon size={40} strokeWidth={1} style={{ color: '#CBD5E1' }} />
      <p style={{ marginTop: 12, fontSize: 14, fontWeight: 600, color: '#64748b' }}>{title}</p>
      <p style={{ marginTop: 4, fontSize: 13, color: '#94a3b8', maxWidth: 280 }}>{text}</p>
    </div>
  );
}

type EditableKey = 'name' | 'unit' | 'serialization' | 'size' | 'weight_kg' | 'status';

function DetailPanel({ record, onSaved, onBack }: {
  record: Article;
  onSaved: (a: Article) => void;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<TabKey>('stammdaten');
  const [form, setForm] = useState<Partial<Record<EditableKey, string>>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setForm({}); setError(null); setTab('stammdaten'); }, [record.object_id]);

  function val(key: EditableKey): string {
    if (key in form) return form[key] ?? '';
    const raw = record[key];
    return raw == null ? '' : String(raw);
  }
  function set(key: EditableKey, value: string) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  const dirty = (Object.keys(form) as EditableKey[]).some((k) => val(k) !== (record[k] == null ? '' : String(record[k])));

  const errs = {
    name: validateName(val('name')),
    size: validateSize(val('size')),
    weight: validateWeight(val('weight_kg')),
  };
  const valid = !errs.name && !errs.size && !errs.weight;

  async function save() {
    if (!record.object_id || !valid) return;
    setSaving(true);
    setError(null);
    const payload: ArticleUpdateInput = {};
    (Object.keys(form) as EditableKey[]).forEach((k) => {
      if (val(k) === (record[k] == null ? '' : String(record[k]))) return;
      if (k === 'size') payload.size = normalizeSize(val('size'));
      else if (k === 'weight_kg') payload.weight_kg = normalizeWeight(val('weight_kg'));
      else if (k === 'name') payload.name = val('name').trim();
      else if (k === 'status') payload.status = val('status') as ArticleStatus;
      else if (k === 'unit') payload.unit = val('unit') as ArticleUnit;
      else if (k === 'serialization') payload.serialization = val('serialization') as ArticleSerialization;
    });
    try {
      const updated = await api.updateArticle(record.object_id, payload);
      onSaved(updated);
      setForm({});
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
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {val('name') || record.name}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <select
                value={val('status')}
                onChange={(e) => set('status', e.target.value)}
                style={{ fontSize: 12, fontWeight: 600, padding: '2px 6px', borderRadius: 6, border: '1px solid #E2E8F0', background: '#fff', color: '#475569', cursor: 'pointer' }}
              >
                {ARTICLE_STATUS_ORDER.map((s) => <option key={s} value={s}>{statusConfig(s).label}</option>)}
              </select>
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(record.object_id)}</div>
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
                  borderBottom: `2px solid ${active ? '#2563eb' : 'transparent'}`,
                  background: 'none', border: 'none', borderBottomWidth: 2, borderBottomStyle: 'solid',
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
            <TextField label="Name" value={val('name')} onChange={(v) => set('name', v)} required error={errs.name} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <SelectField label="Einheit" value={val('unit')} onChange={(v) => set('unit', v)} options={ARTICLE_UNITS} required />
              <Segmented label="Seriennummererfassung" value={val('serialization')} onChange={(v) => set('serialization', v)} options={SERIALIZATION_OPTIONS} required />
            </div>
            <TextField label="Grösse" value={val('size')} onChange={(v) => set('size', v)} required hint="Zahlen aufsteigend, getrennt durch 'x' (z. B. 3x40x600)" error={errs.size} />
            <TextField label="Gewicht (kg)" value={val('weight_kg')} onChange={(v) => set('weight_kg', v)} required hint="Grösser als 0, max. 3 Nachkommastellen" error={errs.weight} />
          </div>
        )}
        {tab === 'prozess' && (
          <Placeholder icon={Workflow} title="Prozess" text="Arbeitsplan und Prozessschritte für diesen Artikel folgen in einer späteren Phase." />
        )}
        {tab === 'bestand' && (
          <Placeholder icon={Boxes} title="Bestand" text="Lagerbestand und Bewegungen für diesen Artikel folgen in einer späteren Phase." />
        )}
      </div>

      {/* System footer (read-only meta) */}
      <div style={{ padding: '8px 20px', borderTop: '1px solid #E2E8F0', background: '#fff', flexShrink: 0, fontSize: 11, color: '#94a3b8', display: 'flex', gap: 16 }}>
        <span>Einheit: {unitLabel(record.unit)}</span>
        <span>Erfassung: {serializationLabel(record.serialization)}</span>
        <span>Erstellt: {localDate(record.created_at)}</span>
      </div>

      {/* Save bar */}
      {(dirty || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : !valid ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (!valid ? 'Bitte Eingaben prüfen' : 'Ungespeicherte Änderungen')}
          </span>
          <button
            onClick={() => { setForm({}); setError(null); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}
          >
            Verwerfen
          </button>
          <button
            onClick={save}
            disabled={saving || !valid}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving || !valid ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}
          >
            {saving ? 'Speichern…' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ArtikelPage() {
  const [records, setRecords] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selId, setSelId] = useState<number | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [statusFilter, setStatusFilter] = useState<ArticleStatus | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    api.getArticles()
      .then((r) => { setRecords(r); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = records.filter((r) => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      r.name.toLowerCase().includes(q) ||
      r.size.toLowerCase().includes(q) ||
      String(r.object_id ?? '').includes(q)
    );
  });

  const selected = records.find((r) => r.object_id === selId) ?? null;

  function handleSelect(id: number | null) {
    setSelId(id);
    setMobileView('detail');
  }

  function handleSaved(updated: Article) {
    setRecords((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  }

  function handleCreated(created: Article) {
    setRecords((prev) => [...prev, created].sort((a, b) => (a.object_id ?? 0) - (b.object_id ?? 0)));
    setShowCreate(false);
    handleSelect(created.object_id ?? null);
  }

  const showList = mobileView === 'list';

  const statusCounts = records.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 72px)' }}>
      <ErpTabs />
      <div className="flex overflow-hidden" style={{ flex: 1, minHeight: 0 }}>

        {/* ── List panel ─────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-shrink-0 border-r border-slate-200 flex flex-col bg-white',
          'w-full md:w-[300px] lg:w-[340px]',
          showList ? 'flex' : 'hidden md:flex',
        )}>
          <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid #F1F5F9' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Artikel</span>
              <button
                onClick={() => setShowCreate(true)}
                style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
              >
                <Plus size={14} /> Neu
              </button>
            </div>
            <div style={{ position: 'relative' }}>
              <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Name, Grösse, Nummer…"
                style={{
                  width: '100%', paddingLeft: 30, paddingRight: 12, paddingTop: 7, paddingBottom: 7,
                  fontSize: 13, border: '1px solid #E2E8F0', borderRadius: 8, background: '#F8FAFC',
                  outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
              {ARTICLE_STATUS_ORDER.filter((s) => statusCounts[s]).map((s) => {
                const sc = statusConfig(s);
                const active = statusFilter === s;
                return (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(active ? null : s)}
                    style={{
                      padding: '3px 8px', borderRadius: 12,
                      border: `1px solid ${active ? sc.color : '#E2E8F0'}`,
                      background: active ? sc.bg : '#fff',
                      color: active ? sc.color : '#64748b',
                      fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    {sc.label} {statusCounts[s]}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading && <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>Laden…</div>}
            {!loading && filtered.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>
                {search || statusFilter ? 'Keine Treffer' : 'Noch keine Artikel — mit «Neu» anlegen'}
              </div>
            )}
            {filtered.map((r) => (
              <ArticleItem key={r.id} a={r} sel={r.object_id === selId} onClick={() => handleSelect(r.object_id ?? null)} />
            ))}
          </div>
        </div>

        {/* ── Detail panel ───────────────────────────────────────────────── */}
        <div className={cn(
          'flex-1 overflow-hidden flex flex-col',
          !showList ? 'flex' : 'hidden md:flex',
        )}>
          {selected
            ? <DetailPanel key={selected.object_id} record={selected} onSaved={handleSaved} onBack={() => setMobileView('list')} />
            : (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <Package size={48} strokeWidth={1} style={{ color: '#CBD5E1' }} />
                <p style={{ marginTop: 12, fontSize: 14, color: '#94a3b8' }}>Artikel auswählen oder neu anlegen</p>
              </div>
            )
          }
        </div>
      </div>

      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />}
    </div>
  );
}
