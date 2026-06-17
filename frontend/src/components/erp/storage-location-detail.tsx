'use client';

import { useState } from 'react';
import { Warehouse, ArrowLeft, FileText, MapPin, Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { StorageLocation, StorageLocationStatus, StorageLocationInput } from '@/types';
import { storageStatusConfig } from '@/lib/storage-location';
import { lifecycleActions } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, StatusBadge, StatusFlow, ErrorText } from '@/components/erp/fields';
import { MapPicker, type ParsedAddress } from '@/components/erp/map-picker';

type Form = {
  max_load_kg: string; dimensions: string; note: string;
  latitude: string; longitude: string;
  address_street: string; address_zip: string; address_city: string; address_country: string;
};

function s(v: unknown): string {
  return v == null ? '' : String(v);
}

function joinDims(record: StorageLocation): string {
  return [record.width_mm, record.depth_mm, record.height_mm].filter((v) => v != null).join('x');
}

function seedFrom(record: StorageLocation | null): Form {
  if (!record) {
    return {
      max_load_kg: '', dimensions: '', note: '',
      latitude: '', longitude: '', address_street: '', address_zip: '', address_city: '', address_country: '',
    };
  }
  return {
    max_load_kg: s(record.max_load_kg), dimensions: joinDims(record), note: s(record.note),
    latitude: s(record.latitude), longitude: s(record.longitude),
    address_street: s(record.address_street), address_zip: s(record.address_zip),
    address_city: s(record.address_city), address_country: s(record.address_country),
  };
}

function num(v: string): number | null {
  const t = v.trim().replace(',', '.');
  if (t === '') return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}
function strOrNull(v: string): string | null {
  return v.trim() || null;
}

function parseDims(v: string): { w: number; d: number; h: number } | null {
  const parts = v.trim().toLowerCase().replace(/×/g, 'x').replace(/\s+/g, '').split('x');
  if (parts.length !== 3) return null;
  const n = parts.map(Number);
  if (n.some((x) => !Number.isFinite(x) || x <= 0)) return null;
  return { w: Math.round(n[0]), d: Math.round(n[1]), h: Math.round(n[2]) };
}

function validateWeight(v: string): string | null {
  const t = v.trim().replace(',', '.');
  if (t === '') return 'Traglast ist ein Pflichtfeld';
  if (!/^\d+(\.\d+)?$/.test(t)) return 'Traglast muss eine Zahl sein';
  if (!(Number(t) > 0)) return 'Traglast muss grösser als 0 sein';
  return null;
}

function validateDims(v: string): string | null {
  if (!v.trim()) return 'Abmessungen sind ein Pflichtfeld';
  if (!parseDims(v)) return "Format: Breite x Länge x Höhe in mm, z. B. 800x1200x1500";
  return null;
}

function buildInput(form: Form): StorageLocationInput {
  const dims = parseDims(form.dimensions);
  return {
    max_load_kg: num(form.max_load_kg),
    width_mm: dims?.w ?? null, depth_mm: dims?.d ?? null, height_mm: dims?.h ?? null,
    note: strOrNull(form.note),
    latitude: num(form.latitude), longitude: num(form.longitude),
    address_street: strOrNull(form.address_street), address_zip: strOrNull(form.address_zip),
    address_city: strOrNull(form.address_city), address_country: strOrNull(form.address_country),
  };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function StorageLocationDetail({ record, mapsApiKey, onSaved, onCancel, onBack }: {
  record: StorageLocation | null;
  mapsApiKey: string | null;
  onSaved: (loc: StorageLocation) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [dirty, setDirty] = useState(false);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      onSaved(await api.updateStorageLocation(record.object_id as number, { status: target as StorageLocationStatus }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
    } finally {
      setStatusBusy(false);
    }
  }

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
    setDirty(true);
  }

  function handlePick(la: number, ln: number, address?: ParsedAddress) {
    setForm((p) => ({
      ...p,
      latitude: la.toFixed(6), longitude: ln.toFixed(6),
      address_street: address?.street || p.address_street,
      address_zip: address?.zip || p.address_zip,
      address_city: address?.city || p.address_city,
      address_country: address?.country || p.address_country,
    }));
    setDirty(true);
  }

  const errs = {
    weight: validateWeight(form.max_load_kg),
    dimensions: validateDims(form.dimensions),
    gps: form.latitude.trim() && form.longitude.trim() ? null : 'Standort (GPS) ist ein Pflichtfeld',
  };
  const valid = !errs.weight && !errs.dimensions && !errs.gps;
  const showErrors = !isCreate || touched;

  async function save() {
    setTouched(true);
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      const input = buildInput(form);
      if (isCreate) {
        onSaved(await api.createStorageLocation(input));
      } else {
        onSaved(await api.updateStorageLocation(record.object_id as number, input));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const latNum = form.latitude.trim() ? Number(form.latitude) : null;
  const lngNum = form.longitude.trim() ? Number(form.longitude) : null;

  // Nach der Freigabe ist der Lagerplatz schreibgeschützt.
  const locked = !isCreate && record !== null && record.status !== 'draft';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Warehouse size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>
              Lagerplatz
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={storageStatusConfig('draft')} />
              ) : (
                <StatusFlow cfg={storageStatusConfig(record.status)} actions={lifecycleActions(record.status)} busy={statusBusy} onAction={changeStatus} />
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

        {/* Tab */}
        <div style={{ display: 'flex', gap: 2, marginTop: 12 }}>
          <button style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', fontSize: 13, fontWeight: 600, color: '#2563eb', background: 'none', border: 'none', borderBottom: '2px solid #2563eb', marginBottom: -13 }}>
            <FileText size={14} /> Stammdaten
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        {locked ? (
          <>
            <SectionTitle icon={MapPin}>Standort</SectionTitle>
            <Card>
              <MapPicker apiKey={mapsApiKey} lat={latNum} lng={lngNum} onPick={() => {}} readOnly />
              <Row k="Adresse" v={record!.address_street || '—'} />
              <Row k="PLZ / Ort" v={`${record!.address_zip ?? ''} ${record!.address_city ?? ''}`.trim() || '—'} />
              <Row k="Land" v={record!.address_country || '—'} />
              <Row k="GPS" v={latNum != null && lngNum != null ? `${latNum.toFixed(5)}, ${lngNum.toFixed(5)}` : '—'} />
            </Card>
            <SectionTitle icon={Boxes}>Kapazität</SectionTitle>
            <Card>
              <Row k="Max. Traglast" v={record!.max_load_kg != null ? `${record!.max_load_kg} kg` : '—'} />
              <Row k="Abmessungen (B×L×H)" v={joinDims(record!) ? `${joinDims(record!)} mm` : '—'} />
            </Card>
            {record!.note && (
              <>
                <SectionTitle icon={FileText}>Bemerkung</SectionTitle>
                <Card><div style={{ fontSize: 13, color: '#0F172A', whiteSpace: 'pre-wrap' }}>{record!.note}</div></Card>
              </>
            )}
          </>
        ) : (
          <>
            {/* Standort */}
            <SectionTitle icon={MapPin}>Standort *</SectionTitle>
            <Card>
              <MapPicker apiKey={mapsApiKey} lat={latNum} lng={lngNum} onPick={handlePick} />
              {showErrors && errs.gps && <ErrorText msg={errs.gps} />}
              <div style={{ fontSize: 11, color: '#94a3b8' }}>Adresse (wird aus Karte/GPS ermittelt, anpassbar):</div>
              <TextField label="Strasse & Nr." value={form.address_street} onChange={(v) => set('address_street', v)} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 14 }}>
                <TextField label="PLZ" value={form.address_zip} onChange={(v) => set('address_zip', v)} />
                <TextField label="Ort" value={form.address_city} onChange={(v) => set('address_city', v)} />
              </div>
              <TextField label="Land" value={form.address_country} onChange={(v) => set('address_country', v)} />
            </Card>

            {/* Kapazität */}
            <SectionTitle icon={Boxes}>Kapazität</SectionTitle>
            <Card>
              <TextField label="Max. Traglast (kg)" value={form.max_load_kg} onChange={(v) => set('max_load_kg', v)} required placeholder="z. B. 500" error={showErrors ? errs.weight : null} />
              <TextField label="Abmessungen B × L × H (mm)" value={form.dimensions} onChange={(v) => set('dimensions', v)} required placeholder="z. B. 800x1200x1500" hint="Breite × Länge × Höhe in mm, getrennt durch 'x'" error={showErrors ? errs.dimensions : null} />
            </Card>

            {/* Bemerkung */}
            <SectionTitle icon={FileText}>Bemerkung</SectionTitle>
            <Card>
              <textarea value={form.note} onChange={(e) => set('note', e.target.value)} rows={3} placeholder="Optionale Bemerkung zum Lagerplatz"
                className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />
            </Card>
          </>
        )}

        {!isCreate && (
          <div style={{ fontSize: 11, color: '#94a3b8', padding: '4px 2px' }}>
            Erstellt: {localDate(record.created_at)} · Zuletzt geändert: {localDate(record.updated_at)}
          </div>
        )}
      </div>

      {/* Save bar */}
      {!locked && (isCreate || dirty || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : (showErrors && !valid) ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (showErrors && !valid ? 'Pflichtfelder: Traglast, Abmessungen, Standort' : isCreate ? 'Neuen Lagerplatz erfassen' : 'Ungespeicherte Änderungen')}
          </span>
          <button
            onClick={isCreate ? onCancel : () => { setForm(seedFrom(record)); setDirty(false); setError(null); setTouched(false); }}
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
