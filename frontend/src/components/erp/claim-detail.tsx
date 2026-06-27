'use client';

import { useState } from 'react';
import { AlertTriangle, ArrowLeft, FileText, Link2, Wrench, User as UserIcon, Loader2, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Claim, ClaimInput, ClaimUpdateInput, ClaimStatus, ClaimDirection, ClaimReason, ClaimResolution, Instance } from '@/types';
import {
  claimStatusConfig, claimActions, CLAIM_DIRECTIONS, CLAIM_REASONS, CLAIM_RESOLUTIONS,
  claimDirectionLabel, claimReasonLabel, claimResolutionLabel,
} from '@/lib/claim';
import { instanceLabel } from '@/lib/process';
import { useAutosave } from '@/lib/use-autosave';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { SearchSelect, SelectField, Segmented, TextField, StatusBadge, StatusFlow, Label } from '@/components/erp/fields';

type Form = {
  instance_object_id: string;
  direction: string;
  reason: string;
  title: string;
  description: string;
  quantity: string;
  resolution: string;
  resolution_note: string;
};

function seedFrom(record: Claim | null): Form {
  if (!record) {
    return {
      instance_object_id: '', direction: 'internal', reason: 'defect',
      title: '', description: '', quantity: '', resolution: 'none', resolution_note: '',
    };
  }
  return {
    instance_object_id: record.instance_object_id != null ? String(record.instance_object_id) : '',
    direction: record.direction, reason: record.reason,
    title: record.title ?? '', description: record.description ?? '',
    quantity: record.quantity != null ? String(record.quantity) : '',
    resolution: record.resolution, resolution_note: record.resolution_note ?? '',
  };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

function qtyValid(v: string): boolean {
  const t = v.trim();
  if (t === '') return true;            // optional
  const n = Number(t);
  return Number.isFinite(n) && n > 0;
}

export function ClaimDetail({ record, instances, onSaved, onCancel, onBack }: {
  record: Claim | null;
  instances: Instance[];
  onSaved: (c: Claim) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [savedSig, setSavedSig] = useState<string>(() => (isCreate ? '' : JSON.stringify(seedFrom(record))));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  // Abgeschlossene/abgelehnte Reklamationen sind inhaltlich gesperrt.
  const locked = !isCreate && (record.status === 'closed' || record.status === 'rejected');

  const sig = isCreate
    ? JSON.stringify({ i: form.instance_object_id, d: form.direction, r: form.reason, t: form.title.trim(), de: form.description.trim(), q: form.quantity.trim() })
    : JSON.stringify({ d: form.direction, r: form.reason, t: form.title.trim(), de: form.description.trim(), q: form.quantity.trim(), rs: form.resolution, rn: form.resolution_note.trim() });

  const valid = qtyValid(form.quantity) && (!isCreate || !!form.instance_object_id);
  const canSave = !locked && valid && sig !== savedSig && !saving;

  async function save() {
    if (!valid) return;
    const current = sig;
    setSaving(true);
    setError(null);
    try {
      const qty = form.quantity.trim() ? Number(form.quantity) : null;
      if (isCreate) {
        const payload: ClaimInput = {
          instance_object_id: Number(form.instance_object_id),
          direction: form.direction as ClaimDirection,
          reason: form.reason as ClaimReason,
          title: form.title.trim() || null,
          description: form.description.trim() || null,
          quantity: qty,
        };
        onSaved(await api.createClaim(payload));
      } else {
        const payload: ClaimUpdateInput = {
          direction: form.direction as ClaimDirection,
          reason: form.reason as ClaimReason,
          title: form.title.trim() || null,
          description: form.description.trim() || null,
          quantity: qty,
          resolution: form.resolution as ClaimResolution,
          resolution_note: form.resolution_note.trim() || null,
        };
        onSaved(await api.updateClaim(record.object_id as number, payload));
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

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      onSaved(await api.updateClaim(record.object_id as number, { status: target as ClaimStatus }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
    } finally {
      setStatusBusy(false);
    }
  }

  const instanceOptions = [
    { value: '', label: '— Instanz wählen —' },
    ...instances.map((i) => ({
      value: String(i.object_id),
      label: `${instanceLabel(i.kind)} · ${fmtObjId(i.object_id ?? null)}${i.article_name ? ` · ${i.article_name}` : ''}`,
    })),
  ];
  const directionOptions = CLAIM_DIRECTIONS.map((d) => ({ value: d.value, label: d.label }));
  const reasonOptions = CLAIM_REASONS.map((r) => ({ value: r.value, label: r.label }));
  const resolutionOptions = CLAIM_RESOLUTIONS.map((r) => ({ value: r.value, label: r.label }));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <AlertTriangle size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Reklamation</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={claimStatusConfig('open')} />
              ) : (
                <StatusFlow cfg={claimStatusConfig(record.status)} actions={claimActions(record.status)} busy={statusBusy} onAction={changeStatus} />
              )}
              <SaveIndicator saving={saving} flash={flash} />
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>RMA-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>
              {isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}
            </div>
          </div>
        </div>

        {/* Tab */}
        <div style={{ display: 'flex', gap: 2, marginTop: 12 }}>
          <button style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', fontSize: 13, fontWeight: 600, color: '#2563eb', background: 'none', border: 'none', borderBottom: '2px solid #2563eb', marginBottom: -13 }}>
            <FileText size={14} /> Stammdaten
          </button>
        </div>
      </div>

      {/* Content */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow 0.2s' }}>

        {/* Bezug (read-only, bei Anlage über die Instanz-Auswahl) */}
        <SectionTitle icon={Link2}>Bezug</SectionTitle>
        <Card>
          {isCreate ? (
            <>
              <SearchSelect label="Reklamierte Instanz" value={form.instance_object_id} onChange={(v) => set('instance_object_id', v)} options={instanceOptions} required />
              {instances.length === 0 && (
                <div style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 10px' }}>
                  Noch keine Instanzen vorhanden. Reklamationen beziehen sich auf serialisierte Bestandsobjekte.
                </div>
              )}
            </>
          ) : (
            <>
              <RowNode k="Instanz">{record.instance_object_id != null ? <ObjId value={record.instance_object_id} /> : '—'}</RowNode>
              <RowNode k="Artikel">{record.article_object_id != null ? <ObjId value={record.article_object_id} /> : (record.article_name ?? '—')}</RowNode>
              <RowNode k="Herkunftsauftrag">{record.order_object_id != null ? <ObjId value={record.order_object_id} /> : '—'}</RowNode>
            </>
          )}
        </Card>

        {/* Beanstandung */}
        <SectionTitle icon={AlertTriangle}>Beanstandung</SectionTitle>
        <Card>
          {locked ? (
            <>
              <Row k="Richtung" v={claimDirectionLabel(record.direction)} />
              <Row k="Grund" v={claimReasonLabel(record.reason)} />
              <Row k="Betreff" v={record.title || '—'} />
              <Row k="Beschreibung" v={record.description || '—'} />
              {record.quantity != null && <Row k="Betroffene Menge" v={String(record.quantity)} />}
            </>
          ) : (
            <>
              <Segmented label="Richtung" value={form.direction} onChange={(v) => set('direction', v)} options={directionOptions} required />
              <SelectField label="Grund" value={form.reason} onChange={(v) => set('reason', v)} options={reasonOptions} required />
              <TextField label="Betreff" value={form.title} onChange={(v) => set('title', v)} placeholder="Kurzbeschreibung" />
              <Textarea label="Beschreibung" value={form.description} onChange={(v) => set('description', v)} placeholder="Was ist das Problem?" />
              <TextField label="Betroffene Menge (optional)" value={form.quantity} onChange={(v) => set('quantity', v)} placeholder="z. B. 3" error={qtyValid(form.quantity) ? null : 'Menge muss eine Zahl > 0 sein'} />
            </>
          )}
        </Card>

        {/* Lösung (erst nach Anlage) */}
        {!isCreate && (
          <>
            <SectionTitle icon={Wrench}>Lösung</SectionTitle>
            <Card>
              {locked ? (
                <>
                  <Row k="Massnahme" v={claimResolutionLabel(record.resolution)} />
                  {record.resolution_note && <Row k="Notiz" v={record.resolution_note} />}
                </>
              ) : (
                <>
                  <SelectField label="Massnahme" value={form.resolution} onChange={(v) => set('resolution', v)} options={resolutionOptions} />
                  <Textarea label="Notiz zur Lösung" value={form.resolution_note} onChange={(v) => set('resolution_note', v)} placeholder="z. B. Ersatz bestellt, Gutschrift erteilt …" />
                </>
              )}
            </Card>
          </>
        )}

        {/* Herkunft */}
        {!isCreate && (
          <>
            <SectionTitle icon={UserIcon}>Herkunft</SectionTitle>
            <Card>
              <Row k="Erfasst von" v={record.reported_by_name ?? '—'} />
              <Row k="Quelle" v={record.source === 'inspection' ? 'Eingangskontrolle (automatisch)' : 'Manuell erfasst'} />
              <Row k="Erstellt" v={localDate(record.created_at)} />
            </Card>
          </>
        )}
      </div>

      {/* Footer-Status (Auto-Save, kein manueller Speichern-Knopf) */}
      {!locked && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (isCreate ? (form.instance_object_id ? 'Wird automatisch angelegt' : 'Bitte zuerst eine Instanz wählen') : 'Änderungen werden automatisch gespeichert')}
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

function Textarea({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <textarea
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
        style={{ borderColor: '#e2e8f0' }}
      />
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {children}
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px' }}>
      <Icon size={13} style={{ color: '#94a3b8' }} />
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>{children}</span>
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

function RowNode({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{k}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{children}</span>
    </div>
  );
}
