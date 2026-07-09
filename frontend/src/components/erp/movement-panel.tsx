'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeftRight, Lock, CheckCircle2, MapPin, Info, ScanLine, Truck, AlertTriangle, FileDown, Loader2, Zap } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, LocationType, Order, StorageLocation, UserProfile, OrderInstance, ShipmentEmbed, TransportMode } from '@/types';
import type { ScanCandidate, ScanKind, ScanStep } from '@/lib/scan';
import { LOCATION_META, locationTypeLabel, instanceLabel } from '@/lib/process';
import { userDisplayName } from '@/lib/utils';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { PrimaryButton, PanelHeader } from '@/components/erp/fields';
import { useScan } from '@/components/scan/scan-provider';

// Standort-Typ → gültiger ScanKind (Symbol/Icon im Scanner). «company» hat keinen
// scannbaren Kind → undefined (generischer Prompt, manuelle Eingabe/Suche).
const SRC_SCAN_KIND: Record<string, ScanKind | undefined> = {
  lagerplatz: 'lagerplatz', user: 'user', instance: 'instance',
};


export function MovementPanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  onOrderUpdated: (o: Order) => void;
}) {
  // Step-spezifisches Embed bevorzugen (mehrere Bewegungs-Schritte je Auftrag möglich);
  // Fallback auf das Kurzform-``order.movement`` (erster Schritt).
  const mv = (stepId != null ? order.steps?.find((s) => s.id === stepId)?.movement : null) ?? order.movement;
  const done = !!mv?.done;
  // Normal nur aktive Instanzen bewegen (verschrottet/verbaut sind endgültig «raus»). **Verkaufte**
  // Instanzen bleiben aber bewegbar, wenn die Bewegung sie physisch bewegt: der **Pflicht-Versand
  // zum Kunden** (Ziel = Person/Kunde – die eben verkaufte Ware geht raus) und die **Retoure**
  // (reason='return' – die verkaufte Ware kommt zurück ins Lager).
  // Verkaufte Instanzen sind NUR beim Pflicht-Versand zum Kunden (mode='customer') oder bei einer
  // Retoure bewegbar – exakt wie im Backend (movement.record_movement). Früher wurde das über
  // `target_location_type === 'user'` erraten; das galt aber für JEDE Bewegung zu einer Person und
  // bot verkaufte Instanzen fälschlich an → Backend wies sie als «gehört nicht zu diesem Auftrag» ab.
  const shipsSold = order.reason === 'return' || mv?.mode === 'customer';
  const instances = useMemo(
    () => (order.instances ?? []).filter((i) => shipsSold
      ? !['scrapped', 'consumed'].includes(i.disposition ?? '')
      : !['scrapped', 'sold', 'consumed'].includes(i.disposition ?? '')),
    [order.instances, shipsSold],
  );
  const scan = useScan();

  const [storageLocs, setStorageLocs] = useState<StorageLocation[]>([]);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [targets, setTargets] = useState<Record<number, string>>({});   // instanceObjId → "type:id"
  const [listsReady, setListsReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fixedType = mv?.target_location_type as LocationType | null | undefined;
  const fixedId = mv?.target_location_id ?? null;
  const hasFixedTarget = !!fixedType && !!fixedId;

  // Auswahllisten NUR für die **freie** Zielwahl laden. Bei festem Ziel (z. B. Pflicht-Versand
  // zum Kunden) werden sie nicht gebraucht – das spart das Laden aller Instanzen/Lagerplätze/
  // Personen (spürbar schneller, gerade nach dem Verkauf mit fixem Kunden-Ziel).
  useEffect(() => {
    if (stepState === 'locked' || done || hasFixedTarget) return;
    Promise.allSettled([api.getStorageLocations(), api.getUsers(), api.getInstances()])
      .then(([sl, us, inst]) => {
        if (sl.status === 'fulfilled') setStorageLocs(sl.value);
        if (us.status === 'fulfilled') setUsers(us.value);
        if (inst.status === 'fulfilled') setAllInstances(inst.value);
        setListsReady(true);
      });
  }, [stepState, done, hasFixedTarget]);
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
    // Quell-Standort verifizieren – für JEDEN Standort mit Nummer, IMMER mit **beiden** Wegen:
    // Kamera-Scan UND manuelle Eingabe/Suche (der Dialog zeigt stets beides – der Nutzer wählt,
    // was er nutzt). ``kind`` nur für scannbare Typen setzen (company hat keinen ScanKind →
    // generisch); der Dialog ist gegen unbekannte kinds gehärtet und die Kamera läuft überall.
    if (inst.location_id != null) {
      const srcKind = SRC_SCAN_KIND[inst.location_type ?? ''];
      steps.push({
        label: 'Aktueller Standort',
        hint: `Standort von ${fmtObjId(iid)} scannen oder Nummer eingeben`,
        expected: inst.location_id,
        kind: srcKind,
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
        {mv?.shipment && <ShipmentBox order={order} stepId={stepId} shipment={mv.shipment} readOnly onOrderUpdated={onOrderUpdated} />}
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

      {/* Versand (ADR 005): abgeleitet aus Ziel/Geofence – Tarifvergleich + Label VOR dem Vollzug */}
      {mv?.shipment && <ShipmentBox order={order} stepId={stepId} shipment={mv.shipment} onOrderUpdated={onOrderUpdated} />}

      {/* Pro Instanz: Status (gescannt/offen) + Einzel-Scan */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {instances.map((i) => {
          const t = i.object_id != null ? targets[i.object_id as number] : undefined;
          const tgtId = t ? Number(t.slice(t.indexOf(':') + 1)) : null;
          return (
            <div key={i.id} style={{ border: `1px solid ${t ? '#bbf7d0' : '#f1f5f9'}`, borderRadius: 8, padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>
                {instanceLabel(i.kind)}
                {i.move_quantity != null && (
                  <span style={{ marginLeft: 6, fontWeight: 700, color: '#0f172a' }}>· bewegt {i.move_quantity} Stk</span>
                )}
              </span>
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

// ─── Versand-Box (ADR 005: «Versand wird abgeleitet, nicht bestellt») ────────────
// Zeigt die abgeleitete Transportklasse; bei externem Transport: Tarifvergleich
// (günstigster vorgewählt, Schnellster als Hinweis), Label-Kauf, Tracking. Ohne
// Aggregator (manual): Carrier/Tracking von Hand. Modus je Auftrag übersteuerbar.
const MODE_LABEL: Record<TransportMode, string> = {
  auto: 'Automatisch', carrier: 'Immer Versand', self: 'Selbsttransport', none: 'Kein Versand',
};

function ShipmentBox({ order, stepId, shipment: sp, readOnly = false, onOrderUpdated }: {
  order: Order; stepId?: number | null; shipment: ShipmentEmbed; readOnly?: boolean;
  onOrderUpdated: (o: Order) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rateId, setRateId] = useState<string | null>(null);
  const [carrier, setCarrier] = useState(sp.carrier ?? '');
  const [tracking, setTracking] = useState(sp.tracking_number ?? '');

  const mode = (sp.transport_mode ?? 'auto') as TransportMode;
  const external = sp.transport_class === 'outside';
  const wantsCarrier = (mode === 'auto' && external) || mode === 'carrier';
  const purchased = sp.status === 'purchased' || sp.status === 'done';
  const inbound = sp.direction === 'inbound';
  const chosen = rateId ?? sp.rates.find((r) => r.cheapest)?.rate_id ?? sp.rates[0]?.rate_id ?? null;
  const chosenRate = sp.rates.find((r) => r.rate_id === chosen) ?? null;
  const fastest = sp.rates.find((r) => r.fastest && !r.cheapest) ?? null;
  const parcel = sp.parcels[0] as { weight_kg?: number; length_cm?: number; width_cm?: number; height_cm?: number } | undefined;

  async function run(kind: string, fn: () => Promise<Order>) {
    setBusy(kind); setErr(null);
    try { onOrderUpdated(await fn()); }
    catch (e) { setErr(e instanceof Error ? e.message : 'Aktion fehlgeschlagen'); }
    finally { setBusy(null); }
  }
  const oid = order.object_id as number;
  const setMode = (m: TransportMode) => run('mode', () => api.updateOrderShipment(oid, { step_id: stepId ?? null, transport_mode: m }));

  const classChip = external
    ? { label: inbound ? 'Extern · Abholung' : 'Extern · Versand', bg: '#FEF3C7', fg: '#B45309' }
    : sp.transport_class === 'inside'
      ? { label: 'Intern', bg: '#F1F5F9', fg: '#475569' }
      : { label: 'Ziel offen', bg: '#F1F5F9', fg: '#94a3b8' };

  return (
    <div style={{ border: '1px solid #E2E8F0', borderRadius: 10, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8, background: '#FAFAF9' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Truck size={15} style={{ color: '#475569', flexShrink: 0 }} />
        <span style={{ fontSize: 12.5, fontWeight: 700, color: '#0f172a' }}>Versand</span>
        <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 999, background: classChip.bg, color: classChip.fg }}>{classChip.label}</span>
        {sp.hazmat && (
          <span title="Mindestens ein Artikel ist als Gefahrgut markiert – Spezialversand erforderlich."
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 999, background: '#FEE2E2', color: '#B91C1C' }}>
            <AlertTriangle size={11} /> Gefahrgut
          </span>
        )}
        {!readOnly && (
          <select value={mode} disabled={busy !== null}
            onChange={(e) => setMode(e.target.value as TransportMode)}
            title="Transport-Modus dieses Auftrags (Ausnahmen: selbst bringen/abholen, nie versenden)"
            style={{ marginLeft: 'auto', fontSize: 11.5, padding: '4px 6px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', color: '#475569' }}>
            {(Object.keys(MODE_LABEL) as TransportMode[]).map((m) => <option key={m} value={m}>{MODE_LABEL[m]}</option>)}
          </select>
        )}
      </div>

      {(sp.from_label || sp.to_label) && wantsCarrier && !purchased && (
        <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.5 }}>
          {sp.from_label && <div><strong style={{ color: '#475569' }}>Von</strong> {sp.from_label}</div>}
          {sp.to_label && <div><strong style={{ color: '#475569' }}>An</strong> {sp.to_label}</div>}
          {parcel && (
            <div><strong style={{ color: '#475569' }}>Paket</strong> ~{parcel.weight_kg} kg · {parcel.length_cm}×{parcel.width_cm}×{parcel.height_cm} cm <span style={{ color: '#94a3b8' }}>(aus Artikel-Daten geschätzt)</span></div>
          )}
        </div>
      )}

      {mode === 'self' && (
        <div style={{ fontSize: 12, color: '#64748b' }}>Selbsttransport – kein Carrier. Die Übergabe wird wie gewohnt per Scan quittiert.</div>
      )}
      {mode === 'none' && (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>Für diese Bewegung wird kein Versand organisiert.</div>
      )}

      {purchased && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 8, background: '#f0fdf4', flexWrap: 'wrap' }}>
          <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
          <span style={{ fontSize: 12.5, fontWeight: 700, color: '#15803D' }}>
            {sp.carrier ?? 'Versand'}{sp.service ? ` · ${sp.service}` : ''}
          </span>
          {sp.tracking_number && (
            sp.tracking_url
              ? <a href={sp.tracking_url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: '#2563eb', textDecoration: 'none' }}>{sp.tracking_number}</a>
              : <span style={{ fontSize: 12, color: '#475569' }}>{sp.tracking_number}</span>
          )}
          {sp.cost_amount != null && <span style={{ fontSize: 12, color: '#64748b' }}>{Number(sp.cost_amount).toFixed(2)} {sp.cost_currency ?? 'CHF'}</span>}
          {sp.label_url && (
            <a href={sp.label_url} target="_blank" rel="noreferrer"
              style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: '#2563eb', textDecoration: 'none' }}>
              <FileDown size={13} /> Label (PDF)
            </a>
          )}
        </div>
      )}

      {!readOnly && wantsCarrier && !purchased && (
        sp.provider_ready ? (
          <>
            {sp.rates.length === 0 ? (
              <button onClick={() => run('quote', () => api.quoteOrderShipment(oid, stepId ?? null))} disabled={busy !== null}
                style={shipBtn('#0f172a')}>
                {busy === 'quote' ? <Loader2 size={13} className="animate-spin" /> : <Truck size={13} />}
                {inbound ? 'Abholung organisieren – Tarife laden' : 'Tarife vergleichen'}
              </button>
            ) : (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
                  {sp.rates.map((r) => (
                    <label key={r.rate_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 9px', borderRadius: 8, border: `1px solid ${chosen === r.rate_id ? '#93c5fd' : '#f1f5f9'}`, background: '#fff', cursor: 'pointer' }}>
                      <input type="radio" name={`rate-${stepId ?? 0}`} checked={chosen === r.rate_id} onChange={() => setRateId(r.rate_id)} />
                      <span style={{ fontSize: 12.5, fontWeight: 600, color: '#0f172a', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.carrier}{r.service ? ` · ${r.service}` : ''}
                      </span>
                      {r.cheapest && <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 999, background: '#DCFCE7', color: '#15803D' }}>Günstigster</span>}
                      {r.fastest && <span title="Schnellste Laufzeit" style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 999, background: '#DBEAFE', color: '#1D4ED8' }}><Zap size={9} /> Schnellster</span>}
                      {r.days != null && <span style={{ fontSize: 11, color: '#94a3b8' }}>~{r.days} Tg</span>}
                      <span className="ix-tnum" style={{ fontSize: 12.5, fontWeight: 700, color: '#0f172a' }}>{r.amount.toFixed(2)} {r.currency}</span>
                    </label>
                  ))}
                </div>
                {fastest && chosenRate?.cheapest && (
                  <div style={{ fontSize: 11, color: '#64748b' }}>
                    Schnellste Alternative: {fastest.carrier} für {fastest.amount.toFixed(2)} {fastest.currency}{fastest.days != null ? ` (~${fastest.days} Tg)` : ''}.
                  </div>
                )}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button onClick={() => chosen && run('buy', () => api.buyOrderShipment(oid, chosen, stepId ?? null))}
                    disabled={busy !== null || !chosen} style={shipBtn('#16a34a')}>
                    {busy === 'buy' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                    Label kaufen{chosenRate ? ` (${chosenRate.amount.toFixed(2)} ${chosenRate.currency})` : ''}
                  </button>
                  <button onClick={() => run('quote', () => api.quoteOrderShipment(oid, stepId ?? null))} disabled={busy !== null} style={shipBtn('#64748b', true)}>
                    Tarife neu laden
                  </button>
                </div>
              </>
            )}
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
              Kein Versand-Anbieter konfiguriert (EASYPOST_API_KEY) – Carrier & Tracking manuell erfassen:
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <input value={carrier} onChange={(e) => setCarrier(e.target.value)} placeholder="Carrier (z. B. Post CH)"
                style={{ flex: '1 1 130px', fontSize: 12.5, padding: '7px 9px', borderRadius: 7, border: '1px solid #E2E8F0' }} />
              <input value={tracking} onChange={(e) => setTracking(e.target.value)} placeholder="Tracking-Nummer"
                style={{ flex: '1 1 150px', fontSize: 12.5, padding: '7px 9px', borderRadius: 7, border: '1px solid #E2E8F0' }} />
              <button onClick={() => run('manual', () => api.updateOrderShipment(oid, { step_id: stepId ?? null, carrier: carrier.trim() || null, tracking_number: tracking.trim() || null }))}
                disabled={busy !== null || (!carrier.trim() && !tracking.trim())} style={shipBtn('#0f172a')}>
                {busy === 'manual' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />} Erfassen
              </button>
            </div>
          </div>
        )
      )}

      {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
    </div>
  );
}

function shipBtn(color: string, outline = false): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 8,
    border: outline ? '1px solid #E2E8F0' : 'none', background: outline ? '#fff' : color,
    color: outline ? color : '#fff', fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
  };
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
