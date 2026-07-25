'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeftRight, Lock, CheckCircle2, MapPin, Info, ScanLine, Truck, AlertTriangle, FileDown, Loader2, Zap, Boxes, Warehouse, Package } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, LocationType, Order, Place, UserProfile, OrderInstance, ShipmentEmbed, TransportMode, CompanySettings } from '@/types';
import type { ScanCandidate, ScanKind, ScanStep } from '@/lib/scan';
import { LOCATION_META, locationTypeLabel, instanceLabel } from '@/lib/process';
import { userDisplayName } from '@/lib/utils';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { PrimaryButton, PanelHeader } from '@/components/erp/fields';
import { useScan } from '@/components/scan/scan-provider';
import { PlacePicker } from '@/components/erp/place-picker';

// Standort-Typ → gültiger ScanKind (Symbol/Icon im Scanner). «company» hat keinen
// scannbaren Kind → undefined (generischer Prompt, manuelle Eingabe/Suche).
// Ein **Ort** trägt keine Objektnummer → nichts zu scannen (undefined = generischer Prompt).
const SRC_SCAN_KIND: Record<string, ScanKind | undefined> = {
  user: 'user', instance: 'instance',
};

/** Ein gewähltes Ziel: entweder ein Objekt (Nummer) ODER ein Ort (Adresse). */
type Target = { type: LocationType; id?: number; place?: Place };

/** Kurz-Anzeige eines Orts (Bezeichnung ≻ Ort ≻ Strasse) – er hat keine Objektnummer. */
function placeText(p?: Place | null): string | null {
  if (!p) return null;
  return (p.name || '').trim() || (p.city || '').trim() || (p.street1 || '').trim() || null;
}


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

  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [targets, setTargets] = useState<Record<number, Target>>({});   // instanceObjId → Ziel
  const [placeOpen, setPlaceOpen] = useState(false);
  const [listsReady, setListsReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fixedType = mv?.target_location_type as LocationType | null | undefined;
  const fixedId = mv?.target_location_id ?? null;
  const fixedPlace = (mv?.target_place ?? null) as Place | null;
  // Ein Vorgabe-**Ort** ist ebenfalls ein festes Ziel – auch ohne Objektnummer.
  const hasFixedTarget = (!!fixedType && !!fixedId) || (fixedType === 'place' && !!fixedPlace);

  // Auswahllisten NUR für die **freie** Zielwahl laden. Bei festem Ziel (z. B. Pflicht-Versand
  // zum Kunden) werden sie nicht gebraucht – das spart das Laden aller Instanzen/Lagerplätze/
  // Personen (spürbar schneller, gerade nach dem Verkauf mit fixem Kunden-Ziel).
  useEffect(() => {
    if (stepState === 'locked' || done || hasFixedTarget) return;
    Promise.allSettled([api.getPublicSettings(), api.getUsers(), api.getInstances()])
      .then(([co, us, inst]) => {
        if (co.status === 'fulfilled') setCompany(co.value);
        if (us.status === 'fulfilled') setUsers(us.value);
        if (inst.status === 'fulfilled') setAllInstances(inst.value);
        setListsReady(true);
      });
  }, [stepState, done, hasFixedTarget]);
  // Ohne festen Zielort braucht der Zielort-Scan die Auswahllisten (Lagerplätze/Personen/
  // Instanzen). Sind sie noch nicht geladen, hätte der letzte Scan-Schritt KEINE Kandidaten
  // → er zeigte nichts an. Darum den Scan erst freigeben, wenn die Listen bereit sind
  // (bei festem Zielort sofort – der kommt aus dem Schritt selbst).
  const scanReady = hasFixedTarget || listsReady;
  const ownObjIds = useMemo(() => new Set(instances.map((i) => i.object_id)), [instances]);

  // Gültige **scannbare** Zielorte (freie Zielwahl): Unternehmen, Personen, andere Instanzen.
  // Ein Ort (Adresse) ist nicht scannbar – er wird über den Orts-Wähler gesetzt.
  const targetType = useMemo(() => new Map<number, LocationType>(), []);
  const targetCandidates = useMemo<ScanCandidate[]>(() => {
    targetType.clear();
    const out: ScanCandidate[] = [];
    if ((!fixedType || fixedType === 'company') && company?.object_id != null) {
      targetType.set(company.object_id as number, 'company');
      out.push({ objectId: company.object_id as number, label: `Unternehmen ${company.company_name ?? ''}`.trim() });
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
  }, [company, users, allInstances, ownObjIds, fixedType, targetType]);

  // Eine Instanz scannen: aktueller Standort → Instanz → Zielstandort (validiert),
  // danach automatisch zur nächsten offenen Instanz; sind alle erfasst → buchen.
  function runSequence(queue: OrderInstance[], acc: Record<number, Target>) {
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
    // Ein Vorgabe-**Ort** hat keine Nummer → nichts zu scannen; er wird direkt übernommen.
    if (fixedType && fixedId) {
      steps.push({
        label: `Zielstandort ${fmtObjId(fixedId)}`,
        hint: `Zugewiesenen ${locationTypeLabel(fixedType)} ${fmtObjId(fixedId)} scannen`,
        expected: fixedId, kind: (fixedType as ScanKind) ?? undefined,
        candidates: [{ objectId: fixedId, label: mv?.target_location_label ?? locationTypeLabel(fixedType) }],
      });
    } else if (fixedType !== 'place') {
      steps.push({ label: 'Zielstandort', hint: 'Zielstandort scannen – wird zugewiesen', restrict: true, candidates: targetCandidates });
    }
    scan({
      title: `Bewegung · ${fmtObjId(iid)}`,
      steps,
      onComplete: (ids) => {
        // Vorgabe-Ort: die Adresse ist das Ziel (kein gescanntes Objekt).
        const chosen: Target = fixedType === 'place' && fixedPlace
          ? { type: 'place', place: fixedPlace }
          : (() => {
              const targetObjId = ids[ids.length - 1];
              return { type: fixedType ?? targetType.get(targetObjId) ?? 'instance', id: targetObjId };
            })();
        const nextAcc = { ...acc, [iid]: chosen };
        setTargets(nextAcc);
        runSequence(queue.slice(1), nextAcc);
      },
    });
  }

  /** Einen **Ort** als Ziel für ALLE Instanzen übernehmen. Ein Ort hält per Definition die
   *  ganze Menge – eine Teilmengen-Zuweisung gibt es dort nicht, also ist «alle» korrekt. */
  function applyPlace(place: Place) {
    const next: Record<number, Target> = { ...targets };
    instances.forEach((i) => { if (i.object_id != null) next[i.object_id as number] = { type: 'place', place }; });
    setTargets(next);
    setPlaceOpen(false);
    setError(null);
  }

  function startScan(only?: OrderInstance) {
    setError(null);
    const queue = only ? [only] : instances.filter((i) => i.object_id != null && !targets[i.object_id as number]);
    runSequence(queue.length ? queue : instances, targets);
  }

  async function submitWith(acc: Record<number, Target>) {
    const list = instances.map((i) => {
      const t = i.object_id != null ? acc[i.object_id as number] : undefined;
      if (!t || i.object_id == null) return null;
      return {
        instance_id: i.object_id, location_type: t.type,
        location_id: t.type === 'place' ? null : (t.id ?? null),
        place: t.type === 'place' ? (t.place ?? null) : null,
      };
    }).filter((x): x is NonNullable<typeof x> => x !== null);
    if (list.length < instances.length) { setError('Bitte für alle Instanzen ein Ziel erfassen'); return; }
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
    : 'Ziel je Instanz scannen (Person · Instanz · Unternehmen) – oder alle an einen Ort (Adresse) setzen.';
  return (
    <div style={cardStyle}>
      <Header info={moveInfo} />

      {/* Versand (ADR 005): abgeleitet aus Ziel/Adresse – Tarifvergleich + Label VOR dem Vollzug */}
      {mv?.shipment && <ShipmentBox order={order} stepId={stepId} shipment={mv.shipment} onOrderUpdated={onOrderUpdated} />}

      {/* **Ort** als Ziel – der einzige Halter ohne Objektnummer, darum nicht scannbar.
          Ein Ort hält immer die ganze Menge, also gilt die Wahl für alle Instanzen. */}
      {!hasFixedTarget && (placeOpen ? (
        <PlacePicker onPick={applyPlace} onCancel={() => setPlaceOpen(false)} />
      ) : (
        <button type="button" onClick={() => setPlaceOpen(true)}
          style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 6,
                   padding: '7px 12px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)',
                   background: 'var(--bg-1)', color: 'var(--fg-2)', fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }}>
          <MapPin size={14} /> Alle an einen Ort (Adresse)
        </button>
      ))}

      {/* Pro Instanz: Status (gescannt/offen) + Einzel-Scan */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {instances.map((i) => {
          const t = i.object_id != null ? targets[i.object_id as number] : undefined;
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
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: 'var(--success)' }}>
                  <CheckCircle2 size={13} /> Ziel {t.type === 'place' ? (placeText(t.place) ?? 'Ort') : fmtObjId(t.id ?? null)}
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
// EINE Transport-Achse: innerbetrieblich | Paket | Fracht. Der abgeleitete Modus ist die
// vorgewählte Empfehlung (aus Ziel & Last), IMMER frei übersteuerbar. Paket → Tarifvergleich
// (günstigster vorgewählt) + Label bzw. Carrier/Tracking von Hand. Fracht → Spediteur/Last
// manuell. Innerbetrieblich → kein Carrier, der Vollzug wird per Scan quittiert.
const MODE_META: Record<TransportMode, { label: string; icon: LucideIcon; tip: string }> = {
  internal: { label: 'Im Betrieb', icon: Warehouse, tip: 'Innerbetrieblich – kein Carrier/Versand. Die Übergabe wird per Scan quittiert.' },
  parcel: { label: 'Paket', icon: Package, tip: 'Paketversand – Tarifvergleich (Aggregator) oder Carrier/Tracking von Hand.' },
  freight: { label: 'Fracht', icon: Boxes, tip: 'Stückgut/Palette – Spediteur; Fracht-Last, Incoterm und Abholung.' },
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

  // Fracht (Modus 'freight'): Last-Felder (Paletten/Lademeter/Gewicht/Incoterm/Abholung).
  // ``kind`` spiegelt den Modus (freight ⟺ 'freight') – keine separate Sendungsart-Wahl mehr.
  const isFreight = sp.kind === 'freight';
  const load = (sp.load ?? {}) as { pallets?: number; loading_meters?: number; volume_m3?: number; gross_weight_kg?: number; pallet_type?: string; stackable?: boolean };
  const [pallets, setPallets] = useState(load.pallets != null ? String(load.pallets) : '');
  const [lm, setLm] = useState(load.loading_meters != null ? String(load.loading_meters) : '');
  const [grossKg, setGrossKg] = useState(load.gross_weight_kg != null ? String(load.gross_weight_kg) : '');
  const [incoterm, setIncoterm] = useState(sp.incoterm ?? '');
  const [pickup, setPickup] = useState(sp.pickup_date ?? '');
  const [cost, setCost] = useState(sp.cost_amount != null ? String(sp.cost_amount) : '');

  const mode = (sp.transport_mode ?? 'internal') as TransportMode;
  const recommended = (sp.recommended_mode ?? 'internal') as TransportMode;
  const isInternal = mode === 'internal';
  const external = sp.transport_class === 'outside';
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
  const saveFreight = () => run('freight', () => api.updateOrderShipment(oid, {
    step_id: stepId ?? null,
    load: {
      ...load,
      pallets: pallets ? Number(pallets) : undefined,
      loading_meters: lm ? Number(lm) : undefined,
      gross_weight_kg: grossKg ? Number(grossKg) : undefined,
    },
    incoterm: incoterm || null,
    pickup_date: pickup || null,
    carrier: carrier.trim() || null,
    tracking_number: tracking.trim() || null,
    cost_amount: cost ? Number(cost) : null,
  }));

  const ModeIcon = MODE_META[mode].icon;

  return (
    <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8, background: 'var(--bg-2)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Truck size={15} style={{ color: 'var(--fg-3)', flexShrink: 0 }} />
        <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--fg-1)' }}>Versand</span>
        {external && (
          <span title="Aus Ziel/Adresse abgeleitet – ein externer Transport ist nötig."
            style={chipStyle('var(--warning-bg)', 'var(--warning)')}>{inbound ? 'Extern · Abholung' : 'Extern · Versand'}</span>
        )}
        {sp.hazmat && (
          <span title="Mindestens ein Artikel ist als Gefahrgut markiert – Spezialversand erforderlich."
            style={{ ...chipStyle('var(--danger-bg)', 'var(--danger)'), display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <AlertTriangle size={11} /> Gefahrgut
          </span>
        )}
        {readOnly && (
          <span style={{ ...chipStyle('var(--bg-3)', 'var(--fg-2)'), marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <ModeIcon size={11} /> {MODE_META[mode].label}
          </span>
        )}
      </div>

      {/* EINE Wahl: innerbetrieblich | Paket | Fracht. Empfohlener (abgeleiteter) Modus vorgewählt. */}
      {!readOnly && (
        <div>
          <div style={{ display: 'flex', border: '1px solid var(--border-1)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
            {(['internal', 'parcel', 'freight'] as TransportMode[]).map((m, i) => {
              const on = mode === m;
              const rec = recommended === m;
              const M = MODE_META[m];
              return (
                <button key={m} type="button" disabled={busy !== null} onClick={() => !on && setMode(m)}
                  title={M.tip + (rec ? ' · Empfohlen (aus Ziel & Last abgeleitet).' : '')}
                  style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 12, fontWeight: 700, padding: '8px 6px', border: 'none', borderLeft: i === 0 ? 'none' : '1px solid var(--border-1)', cursor: busy ? 'wait' : 'pointer', background: on ? 'var(--accent)' : 'var(--bg-1)', color: on ? '#fff' : 'var(--fg-3)' }}>
                  <M.icon size={14} /> {M.label}
                  {rec && !on && <span title="Empfohlen" style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--accent)', flexShrink: 0 }} />}
                </button>
              );
            })}
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Info size={10} /> Empfohlen: {MODE_META[recommended].label} · frei wählbar.
          </div>
        </div>
      )}

      {!isInternal && !purchased && (sp.from_label || sp.to_label) && (
        <div style={{ fontSize: 11, color: 'var(--fg-3)', lineHeight: 1.5 }}>
          {sp.from_label && <div><strong style={{ color: 'var(--fg-2)' }}>Von</strong> {sp.from_label}</div>}
          {sp.to_label && <div><strong style={{ color: 'var(--fg-2)' }}>An</strong> {sp.to_label}</div>}
          {isFreight ? (
            <div><strong style={{ color: 'var(--fg-2)' }}>Last</strong> ~{load.gross_weight_kg ?? '?'} kg · {load.pallets ?? '?'} {load.pallet_type ?? 'EUR'}-Palette(n){load.loading_meters != null ? ` · ${load.loading_meters} Lademeter` : ''} <span style={{ color: 'var(--fg-4)' }}>(geschätzt)</span></div>
          ) : parcel && (
            <div><strong style={{ color: 'var(--fg-2)' }}>Paket</strong> ~{parcel.weight_kg} kg · {parcel.length_cm}×{parcel.width_cm}×{parcel.height_cm} cm <span style={{ color: 'var(--fg-4)' }}>(aus Artikel-Daten geschätzt)</span></div>
          )}
        </div>
      )}

      {isInternal && !readOnly && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)', display: 'flex', alignItems: 'center', gap: 6, lineHeight: 1.4 }}>
          <Warehouse size={13} style={{ flexShrink: 0 }} /> Innerbetriebliche Bewegung – kein Versand. Die Übergabe wird wie gewohnt per Scan quittiert.
        </div>
      )}

      {purchased && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 'var(--r-sm)', background: 'var(--success-bg)', flexWrap: 'wrap' }}>
          <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
          <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--success)' }}>
            {sp.carrier ?? 'Versand'}{sp.service ? ` · ${sp.service}` : ''}
          </span>
          {sp.tracking_number && (
            sp.tracking_url
              ? <a href={sp.tracking_url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>{sp.tracking_number}</a>
              : <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{sp.tracking_number}</span>
          )}
          {sp.cost_amount != null && <span className="ix-tnum" style={{ fontSize: 12, color: 'var(--fg-3)' }}>{Number(sp.cost_amount).toFixed(2)} {sp.cost_currency ?? 'CHF'}</span>}
          {sp.label_url && (
            <a href={sp.label_url} target="_blank" rel="noreferrer"
              style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: 'var(--accent)', textDecoration: 'none' }}>
              <FileDown size={13} /> Label (PDF)
            </a>
          )}
        </div>
      )}

      {!readOnly && !isInternal && !purchased && (
        isFreight ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 11.5, color: 'var(--fg-3)', lineHeight: 1.5 }}>
              Stückgut/Palette – <strong style={{ color: 'var(--fg-2)' }}>Spediteur anfragen</strong> (Offerte), dann Carrier/Tracking/Kosten erfassen. Frachtbrief &amp; Papiere über den Reiter «Dokumente».
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(108px, 1fr))', gap: 6 }}>
              <label style={freightLbl}>Paletten
                <input value={pallets} onChange={(e) => setPallets(e.target.value)} type="number" min={0} style={freightInp} /></label>
              <label style={freightLbl}>Lademeter
                <input value={lm} onChange={(e) => setLm(e.target.value)} type="number" min={0} step="0.1" style={freightInp} /></label>
              <label style={freightLbl}>Brutto (kg)
                <input value={grossKg} onChange={(e) => setGrossKg(e.target.value)} type="number" min={0} step="0.1" style={freightInp} /></label>
              <label style={freightLbl}>Incoterm
                <select value={incoterm} onChange={(e) => setIncoterm(e.target.value)} style={freightInp}>
                  <option value="">–</option>
                  {['EXW', 'FCA', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP', 'FOB', 'CFR', 'CIF'].map((t) => <option key={t} value={t}>{t}</option>)}
                </select></label>
              <label style={freightLbl}>Abholung
                <input value={pickup} onChange={(e) => setPickup(e.target.value)} type="date" style={freightInp} /></label>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <input value={carrier} onChange={(e) => setCarrier(e.target.value)} placeholder="Spediteur/Carrier (z. B. Planzer)"
                style={shipInp('1 1 150px')} />
              <input value={tracking} onChange={(e) => setTracking(e.target.value)} placeholder="Sendungs-/Tracking-Nr."
                style={shipInp('1 1 140px')} />
              <input value={cost} onChange={(e) => setCost(e.target.value)} type="number" min={0} step="0.05" placeholder="Kosten"
                style={shipInp('0 1 100px')} />
              <button onClick={saveFreight} disabled={busy !== null} style={shipBtn('var(--fg-1)')}>
                {busy === 'freight' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />} Fracht erfassen
              </button>
            </div>
          </div>
        ) : sp.provider_ready ? (
          <>
            {sp.rates.length === 0 ? (
              <button onClick={() => run('quote', () => api.quoteOrderShipment(oid, stepId ?? null))} disabled={busy !== null}
                style={shipBtn('var(--fg-1)')}>
                {busy === 'quote' ? <Loader2 size={13} className="animate-spin" /> : <Truck size={13} />}
                {inbound ? 'Abholung organisieren – Tarife laden' : 'Tarife vergleichen'}
              </button>
            ) : (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
                  {sp.rates.map((r) => (
                    <label key={r.rate_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 9px', borderRadius: 'var(--r-sm)', border: `1px solid ${chosen === r.rate_id ? 'var(--accent)' : 'var(--border-1)'}`, background: 'var(--bg-1)', cursor: 'pointer' }}>
                      <input type="radio" name={`rate-${stepId ?? 0}`} checked={chosen === r.rate_id} onChange={() => setRateId(r.rate_id)} />
                      <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--fg-1)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.carrier}{r.service ? ` · ${r.service}` : ''}
                      </span>
                      {r.cheapest && <span style={chipStyle('var(--success-bg)', 'var(--success)')}>Günstigster</span>}
                      {r.fastest && <span title="Schnellste Laufzeit" style={{ ...chipStyle('var(--accent-soft)', 'var(--accent-ink)'), display: 'inline-flex', alignItems: 'center', gap: 3 }}><Zap size={9} /> Schnellster</span>}
                      {r.days != null && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>~{r.days} Tg</span>}
                      <span className="ix-tnum" style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--fg-1)' }}>{r.amount.toFixed(2)} {r.currency}</span>
                    </label>
                  ))}
                </div>
                {fastest && chosenRate?.cheapest && (
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                    Schnellste Alternative: {fastest.carrier} für {fastest.amount.toFixed(2)} {fastest.currency}{fastest.days != null ? ` (~${fastest.days} Tg)` : ''}.
                  </div>
                )}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button onClick={() => chosen && run('buy', () => api.buyOrderShipment(oid, chosen, stepId ?? null))}
                    disabled={busy !== null || !chosen} style={shipBtn('var(--success)')}>
                    {busy === 'buy' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                    Label kaufen{chosenRate ? ` (${chosenRate.amount.toFixed(2)} ${chosenRate.currency})` : ''}
                  </button>
                  <button onClick={() => run('quote', () => api.quoteOrderShipment(oid, stepId ?? null))} disabled={busy !== null} style={shipBtn('var(--fg-3)', true)}>
                    Tarife neu laden
                  </button>
                </div>
              </>
            )}
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>
              Kein Versand-Anbieter konfiguriert (Sendcloud/Shippo) – Carrier &amp; Tracking manuell erfassen:
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <input value={carrier} onChange={(e) => setCarrier(e.target.value)} placeholder="Carrier (z. B. Post CH)"
                style={shipInp('1 1 130px')} />
              <input value={tracking} onChange={(e) => setTracking(e.target.value)} placeholder="Tracking-Nummer"
                style={shipInp('1 1 150px')} />
              <button onClick={() => run('manual', () => api.updateOrderShipment(oid, { step_id: stepId ?? null, carrier: carrier.trim() || null, tracking_number: tracking.trim() || null }))}
                disabled={busy !== null || (!carrier.trim() && !tracking.trim())} style={shipBtn('var(--fg-1)')}>
                {busy === 'manual' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />} Erfassen
              </button>
            </div>
          </div>
        )
      )}

      {err && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{err}</div>}
    </div>
  );
}

function shipBtn(color: string, outline = false): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 'var(--r-sm)',
    border: outline ? '1px solid var(--border-1)' : 'none', background: outline ? 'var(--bg-1)' : color,
    color: outline ? color : '#fff', fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
  };
}

// Kompakte Pille (Status/Kategorie): getönter Hintergrund + semantische Tinte.
function chipStyle(bg: string, fg: string): React.CSSProperties {
  return { fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 999, background: bg, color: fg };
}

// Manuelles Versand-Eingabefeld (Carrier/Tracking/Kosten) – einheitliche Optik über die Tokens.
function shipInp(flex: string): React.CSSProperties {
  return {
    flex, fontSize: 12.5, padding: '7px 9px', borderRadius: 'var(--r-sm)',
    border: '1px solid var(--border-1)', background: 'var(--bg-1)', color: 'var(--fg-1)',
  };
}

// Fracht-Last-Feld (Phase 0): kompaktes Label über Eingabe.
const freightLbl: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 3, fontSize: 10.5, fontWeight: 600,
  color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.03em',
};
const freightInp: React.CSSProperties = {
  fontSize: 12.5, padding: '6px 8px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)',
  background: 'var(--bg-1)', color: 'var(--fg-1)', textTransform: 'none', letterSpacing: 'normal', fontWeight: 400,
};

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
