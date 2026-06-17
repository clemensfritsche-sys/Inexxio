'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeftRight, Lock, CheckCircle2, MapPin, Info } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, LocationType, Order, StorageLocation, UserProfile } from '@/types';
import { LOCATION_META, locationTypeLabel, instanceKindLabel } from '@/lib/process';
import { userDisplayName } from '@/lib/utils';
import { fmtObjId } from '@/components/erp/user-detail';
import { Label } from '@/components/erp/fields';

type Opt = { value: string; label: string; group: string };

function encode(type: LocationType, id: number): string { return `${type}:${id}`; }
function decode(v: string): { type: LocationType; id: number } | null {
  const idx = v.indexOf(':');
  if (idx < 0) return null;
  const type = v.slice(0, idx) as LocationType;
  const id = Number(v.slice(idx + 1));
  return Number.isFinite(id) ? { type, id } : null;
}

export function MovementPanel({ order, stepState, onOrderUpdated }: {
  order: Order;
  stepState: string;
  onOrderUpdated: (o: Order) => void;
}) {
  const mv = order.movement;
  const done = !!mv?.done;
  const instances = useMemo(() => order.instances ?? [], [order.instances]);

  const [storageLocs, setStorageLocs] = useState<StorageLocation[]>([]);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [targets, setTargets] = useState<Record<number, string>>({});
  const [note, setNote] = useState(mv?.note ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auswahllisten erst laden, wenn die Bewegung aktiv ist (nicht im gesperrten Zustand)
  useEffect(() => {
    if (stepState === 'locked' || done) return;
    Promise.allSettled([api.getStorageLocations(), api.getUsers(), api.getInstances()])
      .then(([sl, us, inst]) => {
        if (sl.status === 'fulfilled') setStorageLocs(sl.value);
        if (us.status === 'fulfilled') setUsers(us.value);
        if (inst.status === 'fulfilled') setAllInstances(inst.value);
      });
  }, [stepState, done]);

  // Vorbelegung mit dem Vorgabe-Ziel aus der Prozessdefinition (falls fest gesetzt);
  // sonst leer – der Lagerist wählt bewusst. Der aktuelle Standort wird separat angezeigt.
  useEffect(() => {
    const fixed = mv?.target_location_type && mv?.target_location_id
      ? encode(mv.target_location_type as LocationType, mv.target_location_id) : '';
    const seed: Record<number, string> = {};
    instances.forEach((i) => { if (i.object_id != null) seed[i.object_id] = fixed; });
    setTargets(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.object_id, done]);

  const ownObjIds = useMemo(() => new Set(instances.map((i) => i.object_id)), [instances]);
  const fixedType = mv?.target_location_type as LocationType | null | undefined;

  // Zieloptionen, gruppiert. Bei fest vorgegebenem Typ nur diesen anbieten.
  const options = useMemo<Opt[]>(() => {
    const out: Opt[] = [];
    if (!fixedType || fixedType === 'lagerplatz') {
      storageLocs.filter((l) => l.status === 'released' && l.object_id != null).forEach((l) =>
        out.push({ value: encode('lagerplatz', l.object_id as number), label: fmtObjId(l.object_id), group: 'Lagerplätze' }));
    }
    if (!fixedType || fixedType === 'user') {
      users.filter((u) => u.object_id != null).forEach((u) =>
        out.push({ value: encode('user', u.object_id as number), label: userDisplayName(u), group: 'Personen' }));
    }
    if (!fixedType || fixedType === 'instance') {
      allInstances.filter((i) => i.object_id != null && !ownObjIds.has(i.object_id)).forEach((i) =>
        out.push({ value: encode('instance', i.object_id as number), label: `${instanceKindLabel(i.kind)} · ${fmtObjId(i.object_id)}`, group: 'Instanzen' }));
    }
    return out;
  }, [storageLocs, users, allInstances, ownObjIds, fixedType]);

  const groups = useMemo(() => {
    const g: Record<string, Opt[]> = {};
    options.forEach((o) => { (g[o.group] ??= []).push(o); });
    return g;
  }, [options]);

  function setAll(v: string) {
    if (!v) return;
    const next: Record<number, string> = {};
    instances.forEach((i) => { if (i.object_id != null) next[i.object_id] = v; });
    setTargets(next);
  }

  async function submit() {
    const list = instances
      .map((i) => {
        const dec = i.object_id != null ? decode(targets[i.object_id] ?? '') : null;
        return dec && i.object_id != null
          ? { instance_id: i.object_id, location_type: dec.type, location_id: dec.id }
          : null;
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);

    if (list.length < instances.length) { setError('Bitte für jede Instanz einen Zielstandort wählen'); return; }
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderMovement(order.object_id as number, { targets: list, note: note.trim() || null }));
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

  if (instances.length === 0) {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Info size={14} /> Noch keine Instanzen vorhanden – zuerst serialisieren.
        </div>
      </div>
    );
  }

  // Abgeschlossen → Standorte read-only anzeigen
  if (done) {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#f0fdf4', color: '#16a34a' }}>
          <CheckCircle2 size={16} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>Eingelagert</span>
          {mv?.moved_by_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{mv.moved_by_name}</span>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {instances.map((i) => <InstanceRow key={i.id} instance={i} />)}
        </div>
        {mv?.note && <div style={{ fontSize: 12, color: '#64748b' }}>Notiz: {mv.note}</div>}
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <Header />

      {fixedType && (
        <div style={infoStyle}><Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Vorgabe: Ziel ist ein <b>{locationTypeLabel(fixedType)}</b>{mv?.target_location_label ? ` (${mv.target_location_label})` : ''}.</span></div>
      )}

      {/* Schnellauswahl für alle Instanzen */}
      {instances.length > 1 && (
        <div>
          <Label>Ziel für alle Instanzen</Label>
          <GroupedSelect value="" placeholder="— alle gemeinsam setzen —" groups={groups} onChange={setAll} />
        </div>
      )}

      {/* Pro Instanz ein Zielstandort */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {instances.map((i) => (
          <div key={i.id} style={{ border: '1px solid #f1f5f9', borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(i.object_id ?? null)}</span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceKindLabel(i.kind)}</span>
              <CurrentLocation instance={i} />
            </div>
            <GroupedSelect
              value={i.object_id != null ? (targets[i.object_id] ?? '') : ''}
              placeholder="— Zielstandort wählen —"
              groups={groups}
              onChange={(v) => { if (i.object_id != null) setTargets((p) => ({ ...p, [i.object_id as number]: v })); }}
            />
          </div>
        ))}
      </div>

      <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz (optional)" rows={2}
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={submit} disabled={saving}
          style={{ padding: '7px 16px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
          {saving ? 'Speichert…' : 'Einlagerung bestätigen'}
        </button>
      </div>
    </div>
  );
}

function GroupedSelect({ value, placeholder, groups, onChange }: {
  value: string; placeholder: string; groups: Record<string, Opt[]>; onChange: (v: string) => void;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      style={{ borderColor: '#e2e8f0' }}>
      <option value="">{placeholder}</option>
      {Object.entries(groups).map(([g, opts]) => (
        <optgroup key={g} label={g}>
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function CurrentLocation({ instance }: { instance: NonNullable<Order['instances']>[number] }) {
  if (!instance.location_label) return <span style={{ fontSize: 11, color: '#cbd5e1' }}>kein Standort</span>;
  const Icon = LOCATION_META[(instance.location_type as LocationType)]?.icon ?? MapPin;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}>
      <Icon size={11} /> {instance.location_label}
    </span>
  );
}

function InstanceRow({ instance }: { instance: NonNullable<Order['instances']>[number] }) {
  const Icon = LOCATION_META[(instance.location_type as LocationType)]?.icon ?? MapPin;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
      <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(instance.object_id ?? null)}</span>
      <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceKindLabel(instance.kind)}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: '#0f172a' }}>
        <Icon size={13} style={{ color: '#2563eb' }} /> {instance.location_label ?? '—'}
      </span>
    </div>
  );
}

function Header() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <ArrowLeftRight size={15} style={{ color: '#2563eb' }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Bewegung</span>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
const infoStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px',
  background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 12, color: '#1e40af',
};
