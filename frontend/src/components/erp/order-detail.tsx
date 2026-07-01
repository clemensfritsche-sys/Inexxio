'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ClipboardList, ArrowLeft, Workflow, MapPin, CheckCircle2, Loader2, Repeat, ChevronDown, Boxes, Factory, Warehouse, Target, AlertTriangle, PauseCircle, PackagePlus, PackageMinus, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderStep } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { unitLabel } from '@/lib/article';
import { toStepperState, STEP_META } from '@/lib/process';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import type { StatusAction } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { SearchSelect, StatusBadge, StatusFlow, Label, SectionTitle, PrimaryButton } from '@/components/erp/fields';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { ProcessStepper } from '@/components/erp/process-stepper';
import { PurchaseStepPanel } from '@/components/erp/purchase-step-panel';
import { OrderInstances } from '@/components/erp/order-instances';
import { InspectionPanel } from '@/components/erp/inspection-panel';
import { MovementPanel } from '@/components/erp/movement-panel';
import { ResourcePanel } from '@/components/erp/resource-panel';
import { ScrapPanel } from '@/components/erp/scrap-panel';
import { SalePanel } from '@/components/erp/sale-panel';
import { ProcessSteps } from '@/components/erp/process-steps';
import { MultiLineOrderForm } from '@/components/erp/multi-line-order-form';

type ViewerRole = 'staff' | 'supplier';

// Ziel der Auftragsanlage (Ziel-Karten): herstellen | aus Lager (FIFO) | bestimmte Stücke.
type OrderGoal = 'produce' | 'stock' | 'specific';

// Anker ist IMMER der Artikel + Menge. Was damit geschieht, ergibt sich aus dem Ablauf,
// der danach im Entwurf definiert wird (Erzeugung vs. Operation am Bestand). Optional
// lassen sich für eine Bestands-Operation bestimmte Instanzen fixieren (sonst FIFO).
type Form = { article_id: string; quantity: string; desired_delivery_date: string };

function seedFrom(record: Order | null): Form {
  if (!record) return { article_id: '', quantity: '', desired_delivery_date: '' };
  return {
    article_id: record.article_id != null ? String(record.article_id) : '',
    quantity: record.quantity != null ? String(record.quantity) : '',
    desired_delivery_date: record.desired_delivery_date ?? '',
  };
}

// Signatur des Bedarfs (Artikel/Menge/Termin) – EINE Stelle, damit «gespeichert» (savedSig)
// und «aktuell» (sig) IMMER dieselbe Form haben. (Früher verglich savedSig die Roh-Form mit
// anderem Schlüssel/Datumswert → nie gleich; bei nicht-autosave-baren Aufträgen wie einer
// Abweichung blieb die Freigabe dauerhaft gesperrt.)
function demandSig(articleId: string, quantity: string, date: string | null): string {
  return JSON.stringify({ article_id: articleId, quantity: quantity.trim(), date: date || null });
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// Abgeleitete Subjektart des Auftrags (kein Modus-Flag) – für die Anzeige.
function subjectRoleLabel(role: string | null | undefined): string {
  // Ein Unter-Auftrag, der auf vorhandene Instanzen wirkt, ist eine Bestands-Operation –
  // KEINE eigene «Abweichung»-Art (Status/Art bleiben für alle Aufträge einheitlich).
  return role === 'stock' || role === 'deviation' ? 'Operation am Bestand' : 'Herstellung – erzeugt Instanzen';
}

// Auftrag-Lebenszyklus mit Freigabe-Schutz (Artikel + Menge nötig). Ein freigegebener
// Auftrag kennt nur noch **Abbrechen** (Ersetzen entfällt – ein Abbruch erzwingt ohnehin
// den Folgeauftrag mit denselben Instanzen).
function orderActions(status: string, canRelease: boolean, releaseHint?: string): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
      hint: canRelease ? undefined : releaseHint }];
  if (status === 'released')
    return [{ label: 'Abbrechen', target: 'inactive', tone: 'danger' }];
  return [];   // inactive/completed → kein manueller Wechsel
}

export function OrderDetail({ record, articles, viewerRole, company, onSaved, onCancel, onBack }: {
  record: Order | null;            // null ⇒ Anlage-Modus (nur Mitarbeiter)
  articles: Article[];
  viewerRole: ViewerRole;
  company: Partial<CompanySettings> | null;
  onSaved: (o: Order) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const isStaff = viewerRole === 'staff';
  const nav = useErpNav();   // Navigation per Objektnummer (Unteraufträge anklickbar)
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [dateOpen, setDateOpen] = useState<boolean>(!!record?.desired_delivery_date);
  const [savedSig, setSavedSig] = useState<string>(() => {
    if (record === null) return '';
    const s = seedFrom(record);
    return demandSig(s.article_id, s.quantity, record.desired_delivery_date ?? null);
  });
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selStep, setSelStep] = useState<string | null>(null);
  const [dialog, setDialog] = useState<'deactivate' | null>(null);
  const [deviationBusy, setDeviationBusy] = useState(false);
  const [supplyBusy, setSupplyBusy] = useState(false);
  // Mehrpositionen-Anlage: nur beim frischen Anlegen wählbar (record===null) – ein
  // bereits bestehender Einzel-Artikel-Auftrag bleibt unverändert einzeln.
  const [multiLine, setMultiLine] = useState(false);
  const verRef = useRef<string | null>(record?.updated_at ?? null);   // Optimistic Locking

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  // Unter-Auftrag (Abweichung ODER Nachschub): Subjekt-Instanzen + Bedarf stehen bereits fest
  // (aus dem Eltern-Auftrag) – keine Ziel-Karten/Instanzauswahl, kein editierbarer Bedarf.
  const isSubOrder = record?.parent_order_id != null;
  // Ein Nachschub (reason='supply') ist KEINE Abweichung: er deckt nur die Fehlmenge eines
  // blockierten Schritts (pausiert den Eltern nicht). «Abweichung» = ausschliesslich deviation.
  const isSupply = record?.reason === 'supply';
  // Bedarf nur im Entwurf bearbeitbar (nach Freigabe read-only); bei einem Unter-Auftrag fix.
  const demandEditable = isStaff && (isCreate || record?.status === 'draft') && !isSubOrder;
  const isCompleted = record?.status === 'completed';
  const hasPurchase = !!record?.purchase;
  // «Abweichung melden» auf **Auftragsebene**: nur am LAUFENDEN Auftrag (ein abgeschlossener
  // Prozess ist durch) und nicht, während bereits eine Abweichung offen/ein Abbruch ausstehend
  // ist (erst die offene klären). Eine spätere Reklamation eines fertigen Teils läuft über die
  // Instanz (Instanz-Detail), nicht über den abgeschlossenen Auftrag.
  const canReportDeviation = isStaff && !isCreate && record != null
    && record.status === 'released' && record.abort_into_id == null && !record.paused;

  // Auftrag-Prozess (mehrere Schritte, Mehr-Operationen-Routing) – Schlüssel ist die
  // Schritt-id, damit mehrere gleichartige Schritte unabhängig bedienbar sind.
  const steps = (record?.steps ?? []) as OrderStep[];
  const showProcess = isStaff && !!record && record.status !== 'draft' && steps.length > 0;
  const activeStepId = steps.find((s) => s.state === 'active')?.id
    ?? steps.find((s) => s.state === 'failed')?.id
    ?? steps.find((s) => s.state === 'blocked')?.id   // wartet auf Material → surface
    ?? steps[steps.length - 1]?.id ?? null;
  const currentStepId = selStep ?? (activeStepId != null ? String(activeStepId) : null);
  const currentStepObj = steps.find((s) => String(s.id) === currentStepId) ?? null;

  // Nur freigegebene Artikel sind referenzierbar
  const releasedArticles = articles.filter((a) => a.status === 'released');
  const selectedArticle = releasedArticles.find((a) => String(a.id) === form.article_id) ?? null;
  const qtyUnit = selectedArticle ? unitLabel(selectedArticle.unit) : (record?.article_unit ? unitLabel(record.article_unit) : '');

  // Anker: Artikel + Menge. Bedarf (Artikel/Menge/Termin) wird per Auto-Save persistiert.
  const qtyNum = form.quantity.trim() ? Number(form.quantity) : null;
  const demandValid = !!form.article_id && qtyNum != null && qtyNum > 0;
  const effectiveDate = dateOpen ? (form.desired_delivery_date || null) : null;
  const sig = demandSig(form.article_id, form.quantity, effectiveDate);
  const canSave = demandEditable && demandValid && sig !== savedSig && !saving;
  // Bestands-Operation? – NICHT die blosse Schrittzahl, sondern die **deklarierte Subjekt-Rolle**
  // der Schritte (Beschaffung/Ressource bringen Bestand herein = Herstellung; Verkauf/Bewegung
  // wirken auf vorhandenen Bestand). Live über ProcessSteps (`isStockOp`, Spiegel der Backend-
  // Registry); initial aus der abgeleiteten Subjektart, bis ProcessSteps den echten Stand meldet.
  const [orderStepCount, setOrderStepCount] = useState<number | null>(null);
  const [orderIsStockOp, setOrderIsStockOp] = useState<boolean | null>(null);
  const onStepsCount = useCallback((n: number, stockOp: boolean) => {
    setOrderStepCount(n);
    setOrderIsStockOp(stockOp);
  }, []);
  const isDraftStaff = isStaff && !isCreate && record?.status === 'draft';
  const hasCustomSteps = orderIsStockOp != null ? orderIsStockOp : record?.subject_role === 'stock';

  // Fixierte (gewählte) Instanzen + verfügbarer Lagerbestand des Artikels (für die Ziel-Karten).
  const pins = (record?.instances ?? []).map((i) => i.object_id).filter((x): x is number => x != null);
  const pinnedQty = (record?.instances ?? []).reduce((s, i) => s + (i.quantity ?? 0), 0);
  const reqQty = record?.quantity ?? 0;
  const [pinPool, setPinPool] = useState<Instance[]>([]);
  useEffect(() => {
    // Bei einem Unter-Auftrag (Abweichung/Nachschub) stehen die Instanzen fest – kein Lagerpool nötig.
    if (!isDraftStaff || isSubOrder || record?.article_id == null) { setPinPool([]); return; }
    api.getInstances(500).then(setPinPool).catch(() => {});
  }, [isDraftStaff, isSubOrder, record?.article_id]);
  const articleStock = pinPool.filter((i) =>
    i.object_id != null && i.article_id === record?.article_id &&
    i.quality === 'passed' && i.disposition === 'in_stock' &&
    (i.reserved_for_order_object_id == null || i.reserved_for_order_object_id === record?.object_id));
  const availableQty = articleStock.reduce((s, i) => s + (i.quantity ?? 0), 0);
  // Genug Bestand für eine reine Bestands-Operation? (Menge darf den Lagerbestand nicht übersteigen)
  const enoughStock = reqQty > 0 && availableQty >= reqQty;

  // Ziel der Auftragsanlage (Ziel-Karten). Pins ⇒ «Instanz wählen»; eigene Schritte ⇒
  // «Aus Lager»; sonst «Herstellen». Über die Karten wechselbar (pickGoal räumt Pins beim
  // Verlassen von «Instanz wählen» auf, damit «Aus Lager» wirklich reines FIFO ist).
  const [goalSel, setGoalSel] = useState<OrderGoal | null>(null);
  const goal: OrderGoal = pins.length > 0
    ? 'specific'
    : hasCustomSteps
      ? (goalSel === 'specific' ? 'specific' : 'stock')
      : (goalSel ?? 'produce');

  function pickGoal(g: OrderGoal) {
    setGoalSel(g);
    if (g !== 'specific' && pins.length > 0) setPins([]);   // «Aus Lager»/«Herstellen» = ohne Pins
  }
  function togglePin(oid: number) {
    if (pins.includes(oid)) { setPins(pins.filter((x) => x !== oid)); return; }
    setPins([...pins, oid]);
  }

  // «Instanz wählen» verlangt, dass die gewählten Instanzen die Auftragsmenge GENAU decken.
  const specificComplete = goal !== 'specific' || pinnedQty === reqQty;
  // Unter-Auftrag (Abweichung/Nachschub): Subjekt steht schon fest – Freigabe braucht nur einen
  // definierten Ablauf (mind. einen Schritt, der festlegt, was geschieht / wie nachgeschoben wird).
  const stepCount = orderStepCount ?? (record?.steps?.length ?? 0);
  const subOrderReady = stepCount > 0;
  // Freigabe: Bedarf gespeichert UND – je nach Auftragsart – Ablauf definiert (Unter-Auftrag)
  // bzw. Instanzauswahl vollständig (reguläre Bestands-Operation «Instanz wählen»).
  const canRelease = !isCreate && !!record?.article_id && !!record?.quantity
    && sig === savedSig && (isSubOrder ? subOrderReady : specificComplete);
  const releaseHint = isSubOrder
    ? (subOrderReady ? undefined : (isSupply ? 'Erst einen Prozessschritt für den Nachschub hinzufügen' : 'Erst einen Prozessschritt für die Abweichung hinzufügen'))
    : (!specificComplete ? `Erst genau ${reqQty} Instanz(en) wählen` : 'Erst Artikel und Menge speichern');

  async function setPins(ids: number[]) {
    if (!record) return;
    try {
      const saved = await api.updateOrder(record.object_id as number,
        { instance_object_ids: ids, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Festlegen der Instanzen'); }
  }

  async function save() {
    if (!demandValid) return;
    const current = sig;
    setSaving(true);
    setError(null);
    try {
      if (isCreate) {
        onSaved(await api.createOrder({ article_id: Number(form.article_id), quantity: qtyNum, desired_delivery_date: effectiveDate }));
      } else {
        const saved = await api.updateOrder(record.object_id as number, {
          article_id: form.article_id ? Number(form.article_id) : null,
          quantity: qtyNum, desired_delivery_date: effectiveDate, expected_updated_at: verRef.current,
        });
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

  async function resyncVersion() {
    if (!record) return;
    try {
      const fresh = await api.getOrder(record.object_id as number);
      verRef.current = fresh.updated_at;
      onSaved(fresh);
    } catch { /* ignore */ }
  }

  const flush = useAutosave(sig, canSave, save);

  // Nach Abschluss eines Prozessschritts automatisch zum nächsten aktiven springen
  function afterStep(o: Order) {
    onSaved(o);
    const next = (o.steps ?? []).find((s) => s.state === 'active');
    if (next) setSelStep(String(next.id));
  }

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      const saved = await api.updateOrder(record.object_id as number,
        { status: target as Order['status'], expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
      if (isVersionConflict(e)) await resyncVersion();
    } finally {
      setStatusBusy(false);
    }
  }

  // Abbrechen läuft über einen Bestätigungsdialog (Ersetzen entfällt).
  function onStatusAction(target: string) {
    if (target === 'inactive') { setDialog('deactivate'); return; }
    changeStatus(target);
  }

  async function confirmCancel() {
    if (!record) return;
    // Abbruch erzwingt einen Folgeauftrag (Abweichung), der die im Prozess befindlichen
    // Instanzen übernimmt; bei einem Entwurf wird direkt inaktiviert. Navigiert zum Ergebnis.
    onSaved(await api.abortOrder(record.object_id as number));
    setDialog(null);
  }

  // «Abbruch zurücknehmen»: verwirft den noch im Entwurf befindlichen Folgeauftrag – das
  // Original läuft danach unverändert weiter (kein Vollzug, Reservierungen blieben erhalten).
  async function revokeAbort() {
    if (!record?.abort_into_id) return;
    onSaved(await api.revokeAbort(record.abort_into_id));
  }

  // «Abweichung melden»: eröffnet einen Unterauftrag (Abweichung) auf den Instanzen
  // dieses Auftrags und navigiert dorthin – der Nutzer definiert dort den Ablauf und gibt frei.
  async function reportDeviation() {
    if (!record) return;
    setDeviationBusy(true);
    setError(null);
    try {
      onSaved(await api.createDeviation(record.object_id as number));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Abweichung konnte nicht eröffnet werden');
    } finally {
      setDeviationBusy(false);
    }
  }

  // «Nachschub anlegen»: eröffnet einen Nachschub-Unterauftrag, der die Fehlmenge des
  // blockierten Schritts deckt. Liefert den (aktualisierten) Auftrag zurück – der blockierte
  // Schritt zeigt danach den laufenden Nachschub; sobald dieser liefert, wird er wieder aktiv.
  async function requestSupply() {
    if (!record) return;
    setSupplyBusy(true);
    setError(null);
    try {
      onSaved(await api.createSupply(record.object_id as number));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nachschub konnte nicht angelegt werden');
    } finally {
      setSupplyBusy(false);
    }
  }

  const articleOptions = [
    { value: '', label: '— Artikel wählen —' },
    ...releasedArticles.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` })),
  ];
  const companyAddr = company ? [company.street, company.street_number].filter(Boolean).join(' ') : '';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ClipboardList size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Auftrag</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={orderStatusConfig('draft')} />
              ) : (isCompleted || !isStaff) ? (
                <StatusBadge cfg={orderStatusConfig(record.status)} />
              ) : (
                <StatusFlow cfg={orderStatusConfig(record.status)} actions={orderActions(record.status, canRelease, releaseHint)} busy={statusBusy} onAction={onStatusAction} />
              )}
              {demandEditable && <SaveIndicator saving={saving} flash={flash} />}
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
      </div>

      {/* Content */}
      <div onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow 0.2s' }}>
        {/* Mehrpositionen-Anlage: «Herstellen»-Zeilen wurden als EIGENE Aufträge angelegt
            (eigene Fertigungs-Timeline) – hier verlinkt, nur direkt nach der Anlage sichtbar. */}
        {!isCreate && (record.also_created?.length ?? 0) > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12, padding: '12px 14px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 13, color: '#1d4ed8', fontWeight: 600 }}>
            <Factory size={16} style={{ flexShrink: 0 }} />
            Zusätzlich angelegt (eigene Herstellung/Beschaffung):
            {record.also_created!.map((oid) => <ObjId key={oid} value={oid} />)}
          </div>
        )}
        {!isCreate && record.abort_into_id != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '12px 14px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, fontSize: 13, color: '#92400e', fontWeight: 600 }}>
            <AlertTriangle size={16} /> Abbruch ausstehend – wird inaktiv, sobald der Folgeauftrag <ObjId value={record.abort_into_id} /> freigegeben ist.
            {isStaff && (
              <button onClick={revokeAbort} type="button"
                style={{ marginLeft: 'auto', padding: '6px 12px', borderRadius: 8, border: '1px solid #d97706', background: '#fff', color: '#92400e', fontWeight: 700, fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                Abbruch zurücknehmen
              </button>
            )}
          </div>
        )}

        {/* Unteraufträge (Abweichungen) sichtbar machen – DAU-sicher: Symbol + Farbe + Klartext,
            klickbare Objektnummern, grüne Badge bei erledigter Abweichung. Pausiert der Auftrag,
            steht das gross zuoberst. (Der Abbruch-Folgeauftrag hat oben schon seinen Banner.) */}
        {!isCreate && isStaff && (record.deviations?.length ?? 0) > 0 && record.abort_into_id == null && (
          <div style={{ marginBottom: 12, border: `1px solid ${record.paused ? '#fde68a' : '#e2e8f0'}`, borderRadius: 10, background: record.paused ? '#fffbeb' : '#fff', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', fontSize: 13, fontWeight: 700, color: record.paused ? '#92400e' : '#0f172a', borderBottom: '1px solid #f1f5f9' }}>
              {record.paused ? <PauseCircle size={16} /> : <AlertTriangle size={16} style={{ color: '#d97706' }} />}
              {record.paused ? 'Pausiert – Abweichung offen' : 'Abweichungen'}
              <span style={{ marginLeft: 'auto', fontWeight: 700, color: '#b45309' }}>{record.deviations!.length}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {record.deviations!.map((d) => (
                <button key={d.object_id} type="button" onClick={() => nav?.(d.object_id)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#fff', borderTop: '1px solid #f8fafc', border: 'none', borderTopColor: '#f8fafc', cursor: 'pointer', textAlign: 'left', width: '100%' }}>
                  <ObjId value={d.object_id} />
                  <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>
                    {d.instance_count === 1 ? '1 Instanz' : `${d.instance_count} Instanzen`}
                    {d.instance_object_ids && d.instance_object_ids.length > 0 && (
                      <> · {fmtObjId(d.instance_object_ids[0])}{d.instance_object_ids.length > 1 ? ` +${d.instance_object_ids.length - 1}` : ''}</>
                    )}
                  </span>
                  <StatusBadge cfg={orderStatusConfig(d.status)} />
                </button>
              ))}
            </div>
            {record.paused && (
              <div style={{ padding: '8px 14px', fontSize: 12, color: '#92400e', borderTop: '1px solid #fef3c7' }}>
                Der Auftrag läuft automatisch weiter, sobald die offene Abweichung abgeschlossen ist.
              </div>
            )}
          </div>
        )}

        {/* Nachschub-Unteraufträge sichtbar machen – decken die Fehlmenge blockierter Schritte.
            Anders als eine Abweichung pausiert ein Nachschub den Auftrag NICHT; sobald er liefert,
            wird der betroffene Schritt von selbst wieder aktiv. */}
        {!isCreate && isStaff && (record.supply_orders?.length ?? 0) > 0 && (
          <div style={{ marginBottom: 12, border: '1px solid #e2e8f0', borderRadius: 10, background: '#fff', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', fontSize: 13, fontWeight: 700, color: '#0f172a', borderBottom: '1px solid #f1f5f9' }}>
              <PackagePlus size={16} style={{ color: '#d97706' }} />
              Nachschub
              <span style={{ marginLeft: 'auto', fontWeight: 700, color: '#b45309' }}>{record.supply_orders!.length}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {record.supply_orders!.map((d) => (
                <button key={d.object_id} type="button" onClick={() => nav?.(d.object_id)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#fff', borderTop: '1px solid #f8fafc', border: 'none', borderTopColor: '#f8fafc', cursor: 'pointer', textAlign: 'left', width: '100%' }}>
                  <ObjId value={d.object_id} />
                  <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>
                    {d.title ?? (d.instance_count === 1 ? '1 Instanz' : `${d.instance_count} Instanzen`)}
                  </span>
                  <StatusBadge cfg={orderStatusConfig(d.status)} />
                </button>
              ))}
            </div>
          </div>
        )}
        {isCompleted && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '12px 14px', background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 10, fontSize: 13, color: '#0f766e', fontWeight: 600 }}>
            <CheckCircle2 size={16} /> Auftrag abgeschlossen – alle Prozessschritte erledigt.
          </div>
        )}

        {/* Bedarf */}
        <SectionTitle>Bedarf</SectionTitle>
        {isCreate && multiLine ? (
          <div style={cardStyle}>
            <MultiLineOrderForm articles={releasedArticles} onCreated={onSaved} onCancel={() => setMultiLine(false)} />
          </div>
        ) : (
        <div style={cardStyle}>
          {demandEditable ? (
            <>
              <SearchSelect label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />
              {isCreate && releasedArticles.length === 0 && (
                <div style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 10px' }}>
                  Kein freigegebener Artikel vorhanden. Nur freigegebene Artikel sind referenzierbar.
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <TextFieldUnit label="Menge" value={form.quantity} onChange={(v) => set('quantity', v)} unit={qtyUnit} required placeholder="z. B. 5" />
                <div>
                  <Label>Wunsch-Liefertermin</Label>
                  {dateOpen ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <input type="date" value={form.desired_delivery_date} min={todayIso()} onChange={(e) => set('desired_delivery_date', e.target.value)}
                        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
                      <button type="button" onClick={() => { setDateOpen(false); set('desired_delivery_date', ''); }}
                        style={linkBtn}>Schnellstmöglich (kein Datum)</button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>Schnellstmöglich</span>
                      <button type="button" onClick={() => setDateOpen(true)} style={linkBtn}>Termin festlegen</button>
                    </div>
                  )}
                </div>
              </div>
              {isCreate && (
                <button type="button" onClick={() => setMultiLine(true)}
                  style={{ ...linkBtn, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <Boxes size={13} /> Mehrere Positionen erfassen (z. B. mehrere Artikel verkaufen)
                </button>
              )}
            </>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
                <span style={{ color: '#94a3b8', flexShrink: 0 }}>Artikel</span>
                <span style={{ textAlign: 'right' }}>
                  {record?.article_object_id != null ? <ObjId value={record.article_object_id} /> : '—'}
                </span>
              </div>
              <Row k="Menge" v={record?.quantity != null ? `${record.quantity} ${record.article_unit ? unitLabel(record.article_unit) : ''}`.trim() : '—'} />
              <Row k="Wunsch-Liefertermin" v={record?.desired_delivery_date ? localDate(record.desired_delivery_date) : 'Schnellstmöglich'} />
              <Row k="Art" v={subjectRoleLabel(record?.subject_role)} />
            </>
          )}
        </div>
        )}

        {/* Wiederkehrend – nur im Entwurf einstellbar (ein freigegebener Auftrag
            ist „scharf" und lässt sich nicht mehr auf wiederkehrend umstellen). Bei einem
            Unter-Auftrag (Abweichung/Nachschub) nicht sinnvoll. */}
        {isStaff && record?.status === 'draft' && !isSubOrder && <RecurrenceCard order={record} onSaved={onSaved} />}

        {/* Lieferung an (für Lieferant) */}
        {!isStaff && (
          <>
            <SectionTitle icon={MapPin}>Lieferung an</SectionTitle>
            <div style={cardStyle}>
              <Row k="Besteller" v={company?.company_name ?? 'Inexxio AG'} />
              {companyAddr && <Row k="Adresse" v={`${companyAddr}, ${company?.zip ?? ''} ${company?.city ?? ''}`.trim()} />}
            </div>
          </>
        )}

        {/* Bestands-Instanzen (bei Freigabe erzeugt) */}
        {record && <OrderInstances order={record} />}

        {/* Abweichung melden – Unterauftrag auf den Instanzen dieses Auftrags (Defekt,
            Nacharbeit, Reklamation – EIN Konzept). Erst nach Freigabe der Abweichung scharf. */}
        {canReportDeviation && (
          <>
            <SectionTitle icon={AlertTriangle}>Abweichung</SectionTitle>
            <div style={cardStyle}>
              <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
                Weicht die Realität vom Prozess ab (Defekt, Nacharbeit, Reklamation)? Eröffne eine{' '}
                <strong style={{ color: '#0f172a' }}>Abweichung</strong> – einen Unterauftrag auf
                den Instanzen dieses Auftrags. Du legst dort fest, was geschieht, und gibst sie frei.
              </div>
              {error && <span style={{ fontSize: 12, color: '#dc2626' }}>{error}</span>}
              <button type="button" onClick={reportDeviation} disabled={deviationBusy}
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  alignSelf: 'flex-start', padding: '9px 16px', borderRadius: 8,
                  border: '1px solid #fbbf24', background: deviationBusy ? '#fef3c7' : '#fffbeb',
                  color: '#b45309', fontSize: 13, fontWeight: 700,
                  cursor: deviationBusy ? 'default' : 'pointer',
                }}>
                {deviationBusy ? <Loader2 size={15} className="animate-spin" /> : <AlertTriangle size={15} />}
                Abweichung melden
              </button>
            </div>
          </>
        )}

        {/* Unter-Auftrag (Entwurf): Subjekt/Bedarf stehen fest (oben gelistet) – KEINE
            Ziel-Karten/Instanzauswahl. Nur den Ablauf definieren, dann freigeben. Abweichung =
            was mit den Instanzen geschieht; Nachschub = wie die Fehlmenge entsteht/beschafft wird. */}
        {isStaff && record?.status === 'draft' && isSubOrder && (
          <>
            <SectionTitle icon={Workflow} info={isSupply
              ? 'Lege fest, wie die fehlende Menge entsteht oder beschafft wird (herstellen, beschaffen …). Mit der Freigabe läuft der Nachschub.'
              : 'Lege fest, was mit den oben genannten Instanzen geschieht (bewegen, verschrotten, prüfen, beschaffen …). Mit der Freigabe wird die Abweichung scharf.'}>
              {isSupply ? 'Ablauf des Nachschubs' : 'Ablauf der Abweichung'}
            </SectionTitle>
            <div style={cardStyle}>
              <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={[]}
                selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
            </div>
          </>
        )}

        {/* Ziel der Auftragsanlage – «Was möchten Sie tun?» (DAU-sicher: Symbol + Farbe +
            Klartext, Live-Verfügbarkeit, unmögliche Optionen deaktiviert mit Begründung). */}
        {isStaff && record?.status === 'draft' && !isSubOrder && (
          <>
            <SectionTitle icon={Workflow}>Was möchten Sie tun?</SectionTitle>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10, marginBottom: 12 }}>
              <GoalCard icon={Factory} tone="#0f766e" active={goal === 'produce'}
                disabled={hasCustomSteps}
                disabledHint="Erst die Auftrags-Schritte entfernen"
                title="Herstellen / Beschaffen"
                desc={`Bei Freigabe entstehen ${reqQty || ''} ${qtyUnit} neu – der Prozess des Artikels wird gefahren.`}
                footer="Neuer Bestand"
                onClick={() => pickGoal('produce')} />
              <GoalCard icon={Warehouse} tone="#2563eb" active={goal === 'stock'}
                disabled={!enoughStock}
                disabledHint={availableQty < 1 ? 'Kein Bestand vorhanden' : `Nur ${availableQty} ${qtyUnit} am Lager (${reqQty} benötigt)`}
                title="Aus dem Lager"
                desc="Vorhandene Stück verarbeiten – das System wählt automatisch die ältesten (FIFO)."
                footer={`Lager: ${availableQty} ${qtyUnit} verfügbar`}
                onClick={() => pickGoal('stock')} />
              <GoalCard icon={Target} tone="#7c3aed" active={goal === 'specific'}
                disabled={!enoughStock}
                disabledHint={availableQty < 1 ? 'Kein Bestand vorhanden' : `Nur ${availableQty} ${qtyUnit} am Lager (${reqQty} benötigt)`}
                title="Instanz wählen"
                desc="Genau wählen, welche Instanzen verarbeitet werden (z. B. Reparatur, Abweichung)."
                footer={`Lager: ${availableQty} ${qtyUnit} verfügbar`}
                onClick={() => pickGoal('specific')} />
            </div>

            {/* Editor je nach Ziel */}
            {goal === 'produce' ? (
              <div style={{ ...cardStyle, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <Factory size={18} style={{ color: '#0f766e', flexShrink: 0 }} />
                <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
                  <strong style={{ color: '#0f172a' }}>Herstellung.</strong> Bei der Freigabe werden{' '}
                  <strong style={{ color: '#0f172a' }}>{reqQty || ''} {qtyUnit}</strong> nach dem
                  Prozess des Artikels erzeugt – keine eigenen Auftrags-Schritte nötig.
                </div>
              </div>
            ) : (
              <>
                {/* «Instanz wählen»: Instanzen direkt hier wählen – genau die Auftragsmenge. */}
                {goal === 'specific' && (
                  <>
                    <SectionTitle icon={Boxes}>Instanzen wählen</SectionTitle>
                    <div style={cardStyle}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                        <span style={{ fontSize: 12, color: '#64748b' }}>Genau {reqQty} {qtyUnit} wählen:</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: pinnedQty === reqQty ? '#16a34a' : '#d97706' }}>
                          {pinnedQty} / {reqQty} gewählt
                        </span>
                      </div>
                      {articleStock.length === 0 ? (
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>Keine verfügbaren Instanzen.</div>
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {articleStock.map((i) => {
                            const sel = pins.includes(i.object_id!);
                            const atLimit = !sel && pinnedQty + (i.quantity ?? 1) > reqQty;
                            return (
                              <button key={i.object_id} type="button" disabled={atLimit}
                                onClick={() => togglePin(i.object_id!)}
                                style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                                  padding: '4px 10px', borderRadius: 999, cursor: atLimit ? 'not-allowed' : 'pointer',
                                  border: `1px solid ${sel ? '#7c3aed' : '#e2e8f0'}`,
                                  background: sel ? '#f5f3ff' : '#fff', color: sel ? '#6d28d9' : '#475569',
                                  opacity: atLimit ? 0.4 : 1,
                                }}>
                                {sel && <CheckCircle2 size={12} />}
                                {fmtObjId(i.object_id)}{(i.quantity ?? 1) > 1 ? ` ·${i.quantity}` : ''}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )}

                <SectionTitle icon={Workflow} info={goal === 'specific'
                  ? 'Schritte definieren, was mit den gewählten Instanzen geschieht (bewegen, verkaufen, prüfen …).'
                  : `Schritte definieren, was mit ${reqQty || ''} ${qtyUnit} ab Lager geschieht – die ältesten zuerst (FIFO).`}>Ablauf</SectionTitle>
                <div style={cardStyle}>
                  <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={[]}
                    selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
                </div>
              </>
            )}
          </>
        )}

        {/* Prozess */}
        {showProcess ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <div style={{ ...cardStyle, paddingTop: 14, paddingBottom: 14 }}>
              <ProcessStepper
                nodes={steps.map((s) => ({ key: String(s.id), label: s.label, state: toStepperState(s.state), hint: stepHint(s), icon: STEP_META[s.step_type as keyof typeof STEP_META]?.icon }))}
                selectedKey={currentStepId ?? undefined}
                onSelect={setSelStep}
              />
            </div>
            {currentStepObj?.state === 'blocked' ? (
              <BlockedStepNotice step={currentStepObj} isStaff={isStaff} canSupply={record.status === 'released'}
                busy={supplyBusy} error={error} onSupply={requestSupply} />
            ) : (
              <StepPanel key={currentStepId ?? 'none'} step={currentStepObj} order={record as Order} viewerRole={viewerRole} company={company} onSaved={afterStep} />
            )}
          </>
        ) : !isStaff && hasPurchase ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <PurchaseStepPanel order={record as Order} viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
          </>
        ) : null}
      </div>

      {/* Meta footer (edit only) */}
      {!isCreate && (
        <div style={{ padding: '8px 20px', borderTop: '1px solid #E2E8F0', background: '#fff', flexShrink: 0, fontSize: 11, color: '#94a3b8', display: 'flex', gap: 16 }}>
          <span>Erstellt: {localDate(record.created_at)}</span>
          <span>Zuletzt geändert: {localDate(record.updated_at)}</span>
        </div>
      )}

      {/* Footer-Status (Auto-Save, kein manueller Speichern-Knopf) */}
      {demandEditable && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (!demandValid ? 'Pflichtfelder: Artikel und Menge' : isCreate ? 'Wird automatisch angelegt, sobald vollständig' : 'Änderungen werden automatisch gespeichert')}
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
          title="Auftrag abbrechen"
          message={record.status === 'released'
            ? 'Es wird ein Folgeauftrag (Abweichung) mit den im Prozess befindlichen Instanzen angelegt. Du legst dort fest, was mit ihnen geschieht; das Original wird erst inaktiv, wenn der Folgeauftrag freigegeben ist.'
            : 'Der Entwurf wird inaktiv gesetzt.'}
          confirmLabel={record.status === 'released' ? 'Folgeauftrag anlegen' : 'Abbrechen'}
          onConfirm={confirmCancel}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

function SaveIndicator({ saving, flash }: { saving: boolean; flash: boolean }) {
  if (saving) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}><Loader2 size={12} className="animate-spin" /> Speichert…</span>;
  if (flash) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#16a34a' }}><CheckCircle2 size={12} /> Gespeichert</span>;
  return null;
}

function stepHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

// Blockierter Schritt: wartet auf Material (Subjekt/Komponente nicht am Lager). Zeigt die
// Fehlmengen und – sofern Nachschub bereits läuft – die verlinkten Nachschub-Aufträge.
// Läuft noch kein Nachschub, kann Staff am freigegebenen Auftrag einen anlegen. «Blockiert»
// ist abgeleitet: sobald der Nachschub liefert, wird der Schritt von selbst wieder aktiv.
function BlockedStepNotice({ step, isStaff, canSupply, busy, error, onSupply }: {
  step: OrderStep;
  isStaff: boolean;
  canSupply: boolean;
  busy: boolean;
  error: string | null;
  onSupply: () => void;
}) {
  const running = step.supply_order_object_ids ?? [];
  const hasRunning = running.length > 0;
  return (
    <div style={{ border: '1px solid #fde68a', borderRadius: 10, background: '#fffbeb', overflow: 'hidden', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', fontSize: 14, fontWeight: 700, color: '#92400e', borderBottom: '1px solid #fde68a' }}>
        <Clock size={17} /> Wartet auf Material
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px' }}>
        <div style={{ fontSize: 12, color: '#92400e', lineHeight: 1.5 }}>
          Dieser Schritt ist blockiert – das benötigte Material ist nicht am Lager. Sobald der
          Nachschub geliefert hat, läuft der Schritt automatisch weiter.
        </div>
        {(step.shortfall?.length ?? 0) > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {step.shortfall!.map((sf, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#0f172a' }}>
                <PackageMinus size={14} style={{ color: '#b45309', flexShrink: 0 }} />
                <span>
                  <strong>{sf.quantity}</strong> × {sf.article_name ?? 'Artikel'}
                  {sf.article_object_id != null && <> (<ObjId value={sf.article_object_id} />)</>} fehlt
                </span>
              </div>
            ))}
          </div>
        )}
        {hasRunning ? (
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, fontSize: 13, color: '#92400e', fontWeight: 600 }}>
            <PackagePlus size={15} style={{ color: '#b45309', flexShrink: 0 }} />
            Nachschub läuft:
            {running.map((oid) => <ObjId key={oid} value={oid} />)}
          </div>
        ) : isStaff && canSupply ? (
          <PrimaryButton icon={PackagePlus} onClick={onSupply} disabled={busy}>
            {busy ? 'Nachschub wird angelegt…' : 'Nachschub anlegen'}
          </PrimaryButton>
        ) : null}
        {error && <span style={{ fontSize: 12, color: '#dc2626' }}>{error}</span>}
      </div>
    </div>
  );
}

// Rendert das Panel des gewählten Prozessschritts. Der jeweilige Ausführungs-Embed
// des konkreten Schritts wird auf die Top-Level-Felder gelegt, damit die Panels
// unverändert lesen können; die Schritt-id wird für das Routing weitergereicht.
function StepPanel({ step, order, viewerRole, company, onSaved }: {
  step: OrderStep | null;
  order: Order;
  viewerRole: ViewerRole;
  company?: Partial<import('@/types').CompanySettings> | null;
  onSaved: (o: Order) => void;
}) {
  if (!step) return null;
  const stepOrder: Order = {
    ...order,
    purchase: (step.purchase ?? order.purchase) as Order['purchase'],
    sale: step.sale ?? order.sale,
    inspection: step.inspection ?? order.inspection,
    movement: step.movement ?? order.movement,
    resource: step.resource ?? order.resource,
    disposal: step.disposal ?? order.disposal,
  };
  const stepState = step.state;
  const stepId = step.id;
  if (step.step_type === 'purchase') {
    return stepOrder.purchase
      ? <PurchaseStepPanel order={stepOrder} viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
      : <StepFallback />;
  }
  if (step.step_type === 'sale') {
    return <SalePanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'inspection') {
    return <InspectionPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'movement') {
    return <MovementPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'resource' || step.step_type === 'consume' || step.step_type === 'tool') {
    return <ResourcePanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'scrap') {
    return <ScrapPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  return <StepFallback />;
}

// Fallback, wenn ein Schritt (noch) keine Detail-Daten hat – nie ein leeres Panel zeigen.
function StepFallback() {
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px',
      fontSize: 13, color: '#64748b', display: 'flex', alignItems: 'center', gap: 8 }}>
      <Loader2 size={15} className="animate-spin" style={{ flexShrink: 0 }} />
      Details werden vorbereitet – bitte die Seite neu laden, falls nichts erscheint.
    </div>
  );
}

// Mengen-Eingabe mit Einheit-Suffix des referenzierten Artikels
export function TextFieldUnit({ label, value, onChange, unit, required, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; unit?: string; required?: boolean; placeholder?: string;
}) {
  return (
    <div>
      <Label required={required}>{unit ? `${label} (${unit})` : label}</Label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        style={{ borderColor: '#e2e8f0' }}
      />
    </div>
  );
}

export const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10,
  padding: '16px 18px', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 14,
};

export const linkBtn: React.CSSProperties = {
  alignSelf: 'flex-start', border: 'none', background: 'none', padding: 0,
  fontSize: 12, color: '#2563eb', cursor: 'pointer', fontWeight: 600,
};

// Ziel-Karte («Was möchten Sie tun?»): Symbol + Farbe + Klartext + Live-Fussnote.
// Unmögliche Optionen sind deaktiviert und nennen den Grund (DAU-sicher).
export function GoalCard({ icon: Icon, tone, active, disabled, disabledHint, title, desc, footer, onClick }: {
  icon: React.ElementType; tone: string; active: boolean; disabled?: boolean;
  disabledHint?: string; title: string; desc: string; footer: string; onClick: () => void;
}) {
  return (
    <button type="button" onClick={disabled ? undefined : onClick} disabled={disabled}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 12, textAlign: 'left', width: '100%',
        padding: '12px 14px', borderRadius: 10, cursor: disabled ? 'not-allowed' : 'pointer',
        border: `1.5px solid ${active ? tone : '#E2E8F0'}`,
        background: disabled ? '#f8fafc' : active ? `${tone}14` : '#fff',
        opacity: disabled ? 0.65 : 1, transition: 'border-color 0.15s, background 0.15s',
      }}>
      <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: active ? tone : '#F1F5F9', color: active ? '#fff' : tone, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={18} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13.5, fontWeight: 700, color: '#0f172a' }}>{title}</span>
          {active && <CheckCircle2 size={15} style={{ color: tone, flexShrink: 0 }} />}
        </div>
        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.45, marginTop: 2 }}>{desc}</div>
        <div style={{ fontSize: 11, fontWeight: 600, color: disabled ? '#dc2626' : tone, marginTop: 5 }}>
          {disabled ? (disabledHint ?? 'Nicht möglich') : footer}
        </div>
      </div>
    </button>
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

const recInput = "w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";

/** «Wiederkehrend» direkt am Auftrag: bei Abschluss entsteht automatisch der nächste
 *  (Entwurf), Termin = Termin + Periode. Nur im Entwurf einstellbar. */
function RecurrenceCard({ order, onSaved }: { order: Order; onSaved: (o: Order) => void }) {
  const [active, setActive] = useState(!!order.recurrence_active);
  const [interval, setIntervalDays] = useState(order.recurrence_interval_days ? String(order.recurrence_interval_days) : '365');
  const [anchor, setAnchor] = useState(order.recurrence_anchor ?? '');
  const [lead, setLead] = useState(order.recurrence_lead_time_days != null ? String(order.recurrence_lead_time_days) : '30');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setBusy(true); setErr(null);
    try {
      const o = await api.updateOrder(order.object_id as number, {
        recurrence_active: active,
        recurrence_interval_days: active ? Math.max(1, Math.trunc(Number(interval) || 0)) : null,
        recurrence_lead_time_days: active ? Math.max(0, Math.trunc(Number(lead) || 0)) : 0,
        recurrence_anchor: active && anchor ? anchor : null,
      });
      onSaved(o); setSaved(true); setTimeout(() => setSaved(false), 1500);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
    finally { setBusy(false); }
  }

  // Dezent: standardmässig eingeklappt (ein unscheinbarer Link), nur offen wenn aktiv.
  const [open, setOpen] = useState(!!order.recurrence_active);
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start', margin: '0 2px 12px',
        border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 12, fontWeight: 600,
      }}>
        <Repeat size={13} /> Wiederkehrend einrichten
        {order.recurrence_active && <span style={{ fontSize: 10, fontWeight: 700, color: '#2563eb', background: '#eff6ff', padding: '1px 6px', borderRadius: 999 }}>aktiv</span>}
        <ChevronDown size={13} />
      </button>
    );
  }

  return (
    <>
      <button onClick={() => setOpen(false)} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px', border: 'none', background: 'none', cursor: 'pointer' }}>
        <Repeat size={13} style={{ color: '#94a3b8' }} />
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>Wiederkehrend</span>
        <ChevronDown size={13} style={{ color: '#94a3b8', transform: 'rotate(180deg)' }} />
      </button>
      <div style={cardStyle}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span style={{ fontWeight: 600, color: '#0f172a' }}>Diesen Auftrag wiederkehrend ausführen</span>
        </label>
        {active && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <Label>Periode (Tage)</Label>
                <input value={interval} onChange={(e) => setIntervalDays(e.target.value)} inputMode="numeric"
                  className={recInput} style={{ borderColor: '#e2e8f0' }} placeholder="z. B. 365" />
              </div>
              <div>
                <Label>Vorlaufzeit (Tage)</Label>
                <input value={lead} onChange={(e) => setLead(e.target.value)} inputMode="numeric"
                  className={recInput} style={{ borderColor: '#e2e8f0' }} placeholder="z. B. 30" />
              </div>
            </div>
            <div>
              <Label>Nächster Termin / Ablauf (optional)</Label>
              <input type="date" value={anchor} onChange={(e) => setAnchor(e.target.value)}
                className={recInput} style={{ borderColor: '#e2e8f0' }} />
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              Beim Abschluss entsteht automatisch der nächste Auftrag (Entwurf) – Termin = dieser
              Termin + Periode. Die Vorlaufzeit markiert ihn rechtzeitig als «fällig».
            </div>
          </>
        )}
        {err && <span style={{ fontSize: 12, color: '#dc2626' }}>{err}</span>}
        <button onClick={save} disabled={busy} style={{
          alignSelf: 'flex-start', padding: '7px 14px', borderRadius: 8, border: 'none',
          background: saved ? '#16a34a' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
        }}>
          {busy ? 'Speichern…' : saved ? 'Gespeichert ✓' : 'Speichern'}
        </button>
      </div>
    </>
  );
}
