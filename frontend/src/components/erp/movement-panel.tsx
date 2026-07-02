'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeftRight, Lock, CheckCircle2, MapPin, Info, ScanLine } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, LocationType, Order, StorageLocation, UserProfile } from '@/types';
import type { ScanCandidate, ScanKind, ScanStep } from '@/lib/scan';
import { LOCATION_META, locationTypeLabel, instanceLabel } from '@/lib/process';
import { userDisplayName } from '@/lib/utils';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { PrimaryButton, PanelHeader } from '@/components/erp/fields';
import { useScan } from '@/components/scan/scan-provider';

type OrderInstance = NonNullable<Order['instances']>[number];

export function MovementPanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  onOrderUpdated: (o: Order) => void;
}) {
  const mv = order.movement;
  const done = !!mv?.done;
  // Nur noch aktive Instanzen bewegen – verschrottete/verkaufte/verbaute Teile sind «raus»
  // und blockieren den Schritt nicht mehr (sie sind oben unter «Instanzen» weiter sichtbar).
  const instances = useMemo(
    () => (order.instances ?? []).filter((i) => !['scrapped', 'sold', 'consumed'].includes(i.disposition ?? '')),
    [order.instances],
  );
  const scan = useScan();

  const [storageLocs, setStorageLocs] = useState<StorageLocation[]>([]);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [targets, setTargets] = useState<Record<number, string>>({});   // instanceObjId → "type:id"
  const [listsReady, setListsReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auswahllisten erst laden, wenn die Bewegung aktiv ist (für freie Zielwahl)
  useEffect(() => {
    if (stepState === 'locked' || done) return;
    Promise.allSettled([api.getStorageLocations(), api.getUsers(), api.getInstances()])
      .then(([sl, us, inst]) => {
        if (sl.status === 'fulfilled') setStorageLocs(sl.value);
        if (us.status === 'fulfilled') setUsers(us.value);
        if (inst.status === 'fulfilled') setAllInstances(inst.value);
        setListsReady(true);
      });
  }, [stepState, done]);

  const fixedType = mv?.target_location_type as LocationType | null | undefined;
  const fixedId = mv?.target_location_id ?? null;
  // Ohne festen Zielort braucht der Zielort-Scan die Auswahllisten (Lagerplätze/Personen/
  // Instanzen). Sind sie noch nicht geladen, hätte der letzte Scan-Schritt KEINE Kandidaten
  // → er zeigte nichts an. Darum den Scan erst freigeben, wenn die Listen bereit sind
  // (bei festem Zielort sofort – der kommt aus dem Schritt selbst).
  const scanReady = (!!fixedType && !!fixedId) || listsReady;
  const ownObjIds = useMemo(() => new Set(instances.map((i) => i.object_id)), [instances]);

  // Gültige Zielorte (für freie Zielwahl): Lagerplätze, Personen, andere Instanzen.
  const targetType = useMemo(() => new Map<number, LocationType>(), []);
  const targetCandidates = useMemo<ScanCandidate[]>(() => {
    targetType.clear();
    const out: ScanCandidate[] = [];
    if (!fixedType || fixedType === 'lagerplatz') {
      storageLocs.filter((l) => l.status === 'released' && l.object_id != null).forEach((l) => {
        targetType.set(l.object_id as number, 'lagerplatz');
        out.push({ objectId: l.object_id as number, label: `Lagerplatz` });
      });
    }
    if (!fixedType || fixedType === 'user') {
      users.filter((u) => u.object_id != null).forEach((u) => {
        targetType.set(u.object_id as number, 'user');
        out.push({ objectId: u.object_id as number, label: `Person ${userDisplayName(u)}` });
      });
    }
    if (!fixedType || fixedType === 'instance') {
      allInstances.filter((i) => i.object_id != null && !ownObjIds.has(i.object_id)).forEach((i) => {
        targetType.set(i.object_id as number, 'instance');
        out.push({ objectId: i.object_id as number, label: instanceLabel(i.kind) });
      });
    }
    return out;
  }, [storageLocs, users, allInstances, ownObjIds, fixedType, targetType]);

  // Eine Instanz scannen: aktueller Standort → Instanz → Zielstandort (validiert),
  // danach automatisch zur nächsten offenen Instanz; sind alle erfasst → buchen.
  function runSequence(queue: OrderInstance[], acc: Record<number, string>) {
    if (queue.length === 0) {
      const allDone = instances.every((x) => x.object_id != null && acc[x.object_id as number]);
      if (allDone) submitWith(acc);
      return;
    }
    const inst = queue[0];
    const iid = inst.object_id as number;
    const steps: ScanStep[] = [];
    // Quell-Scan nur bei physisch scannbarem Standort. Liegt die Instanz bei einer
    // Person/Lieferant (Wareneingang von aussen), gibt es nichts zu scannen → überspringen.
    if (inst.location_id != null && inst.location_type !== 'user') {
      steps.push({
        label: 'Aktueller Standort', hint: `Standort von ${fmtObjId(iid)} scannen`, expected: inst.location_id,
        kind: (inst.location_type as ScanKind) ?? undefined,
        candidates: inst.location_label ? [{ objectId: inst.location_id, label: inst.location_label }] : undefined,
      });
    }
    steps.push({
      label: 'Instanz', hint: 'Zu bewegende Instanz scannen', expected: iid, kind: 'instance',
      candidates: [{ objectId: iid, label: instanceLabel(inst.kind) }],
    });
    if (fixedType && fixedId) {
      steps.push({
        label: `Zielstandort ${fmtObjId(fixedId)}`,
        hint: `Zugewiesenen ${locationTypeLabel(fixedType)} ${fmtObjId(fixedId)} scannen`,
        expected: fixedId, kind: (fixedType as ScanKind) ?? undefined,
        candidates: [{ objectId: fixedId, label: mv?.target_location_label ?? locationTypeLabel(fixedType) }],
      });
    } else {
      steps.push({ label: 'Zielstandort', hint: 'Zielstandort scannen – wird zugewiesen', restrict: true, candidates: targetCandidates });
    }
    scan({
      title: `Bewegung · ${fmtObjId(iid)}`,
      steps,
      onComplete: (ids) => {
        const targetObjId = ids[ids.length - 1];
        const type = fixedType ?? targetType.get(targetObjId) ?? 'lagerplatz';
        const nextAcc = { ...acc, [iid]: `${type}:${targetObjId}` };
        setTargets(nextAcc);
        runSequence(queue.slice(1), nextAcc);
      },
    });
  }

  function startScan(only?: OrderInstance) {
    setError(null);
    const queue = only ? [only] : instances.filter((i) => i.object_id != null && !targets[i.object_id as number]);
    runSequence(queue.length ? queue : instances, targets);
  }

  async function submitWith(acc: Record<number, string>) {
    const list = instances.map((i) => {
      const raw = i.object_id != null ? acc[i.object_id as number] : undefined;
      if (!raw || i.object_id == null) return null;
      const idx = raw.indexOf(':');
      return { instance_id: i.object_id, location_type: raw.slice(0, idx) as LocationType, location_id: Number(raw.slice(idx + 1)) };
    }).filter((x): x is NonNullable<typeof x> => x !== null);
    if (list.length < instances.length) { setError('Bitte alle Instanzen scannen'); return; }
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderMovement(order.object_id as number, { targets: list, step_id: stepId ?? null }));
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
          <Info size={14} /> Noch keine Instanzen vorhanden.
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#f0fdf4', color: '#16a34a' }}>
          <CheckCircle2 size={16} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>Bewegung abgeschlossen</span>
          {mv?.moved_by_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{mv.moved_by_name}</span>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {instances.map((i) => <InstanceRow key={i.id} instance={i} />)}
        </div>
      </div>
    );
  }

  const allScanned = instances.every((i) => i.object_id != null && targets[i.object_id as number]);

  const moveInfo = fixedType
    ? `Ziel ist fest: ${locationTypeLabel(fixedType)}${mv?.target_location_label ? ` (${mv.target_location_label})` : ''}. Pro Instanz aktuellen Standort + Instanz scannen.`
    : 'Pro Instanz scannen: aktueller Standort → Instanz → Zielstandort (wird zugewiesen).';
  return (
    <div style={cardStyle}>
      <Header info={moveInfo} />

      {/* Pro Instanz: Status (gescannt/offen) + Einzel-Scan */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {instances.map((i) => {
          const t = i.object_id != null ? targets[i.object_id as number] : undefined;
          const tgtId = t ? Number(t.slice(t.indexOf(':') + 1)) : null;
          return (
            <div key={i.id} style={{ border: `1px solid ${t ? '#bbf7d0' : '#f1f5f9'}`, borderRadius: 8, padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(i.kind)}</span>
              {t ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: '#16a34a' }}>
                  <CheckCircle2 size={13} /> Ziel {fmtObjId(tgtId)}
                </span>
              ) : (
                <CurrentLocation instance={i} />
              )}
              <button onClick={() => startScan(i)} disabled={!scanReady}
                title={scanReady ? 'Diese Instanz scannen' : 'Zielorte werden geladen…'}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', color: scanReady ? '#2563eb' : '#cbd5e1', cursor: scanReady ? 'pointer' : 'not-allowed', flexShrink: 0 }}>
                <ScanLine size={15} />
              </button>
            </div>
          );
        })}
      </div>

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {allScanned ? (
        <PrimaryButton icon={CheckCircle2} tone="success" onClick={() => submitWith(targets)} disabled={saving}>
          {saving ? 'Speichert…' : 'Bewegung buchen'}
        </PrimaryButton>
      ) : (
        <PrimaryButton icon={ScanLine} onClick={() => startScan()} disabled={saving || !scanReady}>
          {scanReady ? 'Scannen & bewegen' : 'Lädt Zielorte…'}
        </PrimaryButton>
      )}
    </div>
  );
}

function CurrentLocation({ instance }: { instance: OrderInstance }) {
  if (!instance.location_label) return <span style={{ fontSize: 11, color: '#cbd5e1' }}>noch nicht festgelegt</span>;
  const Icon = LOCATION_META[(instance.location_type as LocationType)]?.icon ?? MapPin;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}>
      <Icon size={11} /> {instance.location_label}
    </span>
  );
}

function InstanceRow({ instance }: { instance: OrderInstance }) {
  const Icon = LOCATION_META[(instance.location_type as LocationType)]?.icon ?? MapPin;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
      <span style={{ fontSize: 12 }}><ObjId value={instance.object_id} /></span>
      <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(instance.kind)}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: '#0f172a' }}>
        <Icon size={13} style={{ color: '#2563eb' }} /> {instance.location_label ?? '—'}
      </span>
    </div>
  );
}

function Header({ info }: { info?: string }) {
  return <PanelHeader icon={ArrowLeftRight} title="Bewegung" info={info} />;
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
