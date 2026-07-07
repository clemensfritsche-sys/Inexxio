'use client';

import { useEffect, useRef, useState } from 'react';
import { Warehouse, ArrowLeft, FileText, MapPin, Boxes, Link2, FolderOpen } from 'lucide-react';
import { api } from '@/lib/api';
import type { StorageLocation, StorageLocationStatus, StorageLocationInput, ObjectReference } from '@/types';
import { storageStatusConfig } from '@/lib/storage-location';
import { lifecycleActions } from '@/lib/status-flow';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, StatusBadge, StatusFlow, ErrorText, SaveIndicator } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { ObjectLabel } from '@/components/scan/object-label';
import { MapPicker, type ParsedAddress } from '@/components/erp/map-picker';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { DetailTabs, type DetailTab } from '@/components/erp/detail-tabs';
import { localDate } from '@/lib/utils';

type TabKey = 'stammdaten' | 'verwendung' | 'dokumente';

type Form = {
  max_load_kg: string; dimensions: string;
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
      max_load_kg: '', dimensions: '',
      latitude: '', longitude: '', address_street: '', address_zip: '', address_city: '', address_country: '',
    };
  }
  return {
    max_load_kg: s(record.max_load_kg), dimensions: joinDims(record),
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
    latitude: num(form.latitude), longitude: num(form.longitude),
    address_street: strOrNull(form.address_street), address_zip: strOrNull(form.address_zip),
    address_city: strOrNull(form.address_city), address_country: strOrNull(form.address_country),
  };
}


export function StorageLocationDetail({ record, mapsApiKey, onSaved, onCancel, onBack }: {
  record: StorageLocation | null;
  mapsApiKey: string | null;
  onSaved: (loc: StorageLocation) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [tab, setTab] = useState<TabKey>('stammdaten');
  const [refs, setRefs] = useState<ObjectReference[] | null>(null);
  const [form, setForm] = useState<Form>(() => seedFrom(record));

  // Verwendung (lagernde Instanzen + referenzierende Artikel) bei Bedarf laden
  useEffect(() => {
    if (tab !== 'verwendung' || refs !== null || record?.object_id == null) return;
    api.getStorageLocationReferences(record.object_id).then(setRefs).catch(() => setRefs([]));
  }, [tab, refs, record?.object_id]);
  const [savedSig, setSavedSig] = useState<string>(() => (isCreate ? '' : JSON.stringify(seedFrom(record))));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<'deactivate' | 'replace' | null>(null);
  const verRef = useRef<string | null>(record?.updated_at ?? null);   // Optimistic Locking

  async function resyncVersion() {
    if (!record) return;
    try {
      const fresh = await api.getStorageLocation(record.object_id as number);
      verRef.current = fresh.updated_at;
      onSaved(fresh);
    } catch { /* ignore */ }
  }

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      const saved = await api.updateStorageLocation(record.object_id as number,
        { status: target as StorageLocationStatus, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
      if (isVersionConflict(e)) await resyncVersion();
    } finally {
      setStatusBusy(false);
    }
  }

  function onStatusAction(target: string) {
    if (target === 'inactive') { setDialog('deactivate'); return; }
    if (target === 'replace') { setDialog('replace'); return; }
    changeStatus(target);   // Freigeben / Reaktivieren
  }

  async function confirmDeactivate() {
    if (!record) return;
    const saved = await api.updateStorageLocation(record.object_id as number,
      { status: 'inactive', expected_updated_at: verRef.current });
    verRef.current = saved.updated_at;
    onSaved(saved);
    setDialog(null);
  }

  async function confirmReplace() {
    if (!record) return;
    onSaved(await api.replaceStorageLocation(record.object_id as number));   // navigiert zum neuen
    setDialog(null);
  }

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
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
  }

  const errs = {
    weight: validateWeight(form.max_load_kg),
    dimensions: validateDims(form.dimensions),
    gps: form.latitude.trim() && form.longitude.trim() ? null : 'Standort (GPS) ist ein Pflichtfeld',
  };
  const valid = !errs.weight && !errs.dimensions && !errs.gps;

  const latNum = form.latitude.trim() ? Number(form.latitude) : null;
  const lngNum = form.longitude.trim() ? Number(form.longitude) : null;

  // Nach der Freigabe ist der Lagerplatz schreibgeschützt.
  const locked = !isCreate && record !== null && record.status !== 'draft';

  const sig = JSON.stringify(form);
  const canSave = !locked && valid && sig !== savedSig && !saving;

  async function save() {
    if (!valid) return;
    const current = sig;
    setSaving(true);
    setError(null);
    try {
      const input = buildInput(form);
      if (isCreate) {
        onSaved(await api.createStorageLocation(input));
      } else {
        const saved = await api.updateStorageLocation(record.object_id as number,
          { ...input, expected_updated_at: verRef.current });
        verRef.current = saved.updated_at;
        onSaved(saved);
        setSavedSig(current);
        setFlash(true);
        setTimeout(() => setFlash(false), 700);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
      if (!isCreate && isVersionConflict(e)) await resyncVersion();
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
            <Warehouse size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Lagerplatz</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={storageStatusConfig('draft')} />
              ) : (
                <StatusFlow cfg={storageStatusConfig(record.status)} actions={lifecycleActions(record.status, { canReactivate: record.replaced_by_id == null })} busy={statusBusy} onAction={onStatusAction} />
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

        {!isCreate && (record.replaced_by_id != null || record.replaces_id != null) && (
          <ReplacedBanner replacedBy={record.replaced_by_id ?? null} replaces={record.replaces_id ?? null} />
        )}

        {/* Tabs (einheitliche Optik über alle Datensätze) */}
        <DetailTabs<TabKey> style={{ marginTop: 12 }} active={tab} onChange={setTab} tabs={([
          { key: 'stammdaten', label: 'Stammdaten', icon: FileText },
          ...(!isCreate ? [{ key: 'verwendung', label: 'Verwendung', icon: Link2 }] : []),
          ...(!isCreate ? [{ key: 'dokumente', label: 'Dokumente', icon: FolderOpen }] : []),
        ] as DetailTab<TabKey>[])} />
      </div>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'verwendung' ? (
          <UsageList refs={refs} />
        ) : tab === 'dokumente' ? (
          <ObjectDocuments objectId={record?.object_id ?? null} contextLabel="diesem Lagerplatz" />
        ) : (
        <>
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
          </>
        ) : (
          <>
            {/* Standort */}
            <SectionTitle icon={MapPin}>Standort *</SectionTitle>
            <Card>
              <MapPicker apiKey={mapsApiKey} lat={latNum} lng={lngNum} onPick={handlePick} />
              {!valid && errs.gps && <ErrorText msg={errs.gps} />}
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
              <TextField label="Max. Traglast (kg)" value={form.max_load_kg} onChange={(v) => set('max_load_kg', v)} required placeholder="z. B. 500" error={errs.weight} />
              <TextField label="Abmessungen B × L × H (mm)" value={form.dimensions} onChange={(v) => set('dimensions', v)} required placeholder="z. B. 800x1200x1500" hint="Breite × Länge × Höhe in mm, getrennt durch 'x'" error={errs.dimensions} />
            </Card>
          </>
        )}

        {!isCreate && record?.object_id != null && (
          <Card>
            <ObjectLabel objectId={record.object_id} title="Lagerplatz" />
          </Card>
        )}

        {!isCreate && (
          <div style={{ fontSize: 11, color: '#94a3b8', padding: '4px 2px' }}>
            Erstellt: {localDate(record.created_at)} · Zuletzt geändert: {localDate(record.updated_at)}
          </div>
        )}
        </>
        )}
      </div>

      {/* Footer-Status (Auto-Save, kein manueller Speichern-Knopf) */}
      {!locked && tab === 'stammdaten' && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (!valid ? 'Pflichtfelder: Traglast, Abmessungen, Standort' : isCreate ? 'Wird automatisch angelegt, sobald vollständig' : 'Änderungen werden automatisch gespeichert')}
          </span>
          {isCreate && (
            <button onClick={onCancel}
              style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}>
              Abbrechen
            </button>
          )}
        </div>
      )}

      {dialog && record && (
        <DeactivateDialog
          mode={dialog}
          title={dialog === 'replace' ? 'Lagerplatz ersetzen' : 'Lagerplatz inaktiv setzen'}
          message={dialog === 'replace'
            ? 'Ein neuer Lagerplatz (Entwurf) wird angelegt und verknüpft; dieser wird inaktiv. Nur möglich, wenn keine Instanzen lagern.'
            : 'Nur möglich, wenn keine Instanzen lagern – sonst zuerst umlagern.'}
          confirmLabel={dialog === 'replace' ? 'Ersetzen' : 'Inaktiv setzen'}
          onConfirm={async () => { if (dialog === 'replace') await confirmReplace(); else await confirmDeactivate(); }}
          onClose={() => setDialog(null)}
        />
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

// Reiter «Verwendung»: lagernde Instanzen + Artikel, die diesen Lagerplatz referenzieren
function UsageList({ refs }: { refs: ObjectReference[] | null }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 2 }}>
        Referenz / Verwendung
      </div>
      {refs === null ? (
        <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>
      ) : refs.length === 0 ? (
        <div style={{ fontSize: 13, color: '#94a3b8' }}>Keine Instanzen lagernd, kein Artikel referenziert diesen Lagerplatz.</div>
      ) : refs.map((r, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{r.kind}</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>{localDate(r.at)}</div>
          </div>
          <span style={{ fontSize: 12 }}><ObjId value={r.object_id} /></span>
        </div>
      ))}
    </div>
  );
}
