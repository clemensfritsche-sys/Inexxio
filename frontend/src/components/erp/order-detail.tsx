'use client';

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { ClipboardList, ArrowLeft, Workflow, MapPin, CheckCircle2, Loader2, Repeat, ChevronDown, Boxes, Factory, Warehouse, Target, AlertTriangle, PauseCircle, PackagePlus, PackageMinus, Plus, Trash2, Undo2, FolderOpen } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderDeviationInfo, OrderLineInfo, OrderPurchase, OrderStep, OrderUpdateInput, UserProfile } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { unitLabel } from '@/lib/article';
import { toStepperState, STEP_META } from '@/lib/process';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import type { StatusAction } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { SearchSelect, StatusBadge, StatusFlow, Label, SectionTitle, PrimaryButton, SaveIndicator } from '@/components/erp/fields';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { ProcessStepper } from '@/components/erp/process-stepper';
import { PurchaseStepPanel } from '@/components/erp/purchase-step-panel';
import { OrderInstances } from '@/components/erp/order-instances';
import { InspectionPanel } from '@/components/erp/inspection-panel';
import { MovementPanel } from '@/components/erp/movement-panel';
import { ResourcePanel } from '@/components/erp/resource-panel';
import { ScrapPanel } from '@/components/erp/scrap-panel';
import { SalePanel } from '@/components/erp/sale-panel';
import { DocumentPanel } from '@/components/erp/document-panel';
import { ProcessSteps } from '@/components/erp/process-steps';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { localDate } from '@/lib/utils';

type OrderTab = 'auftrag' | 'docs';

type ViewerRole = 'staff' | 'supplier';

// Ziel der Auftragsanlage (Ziel-Karten): herstellen | aus Lager (FIFO) | bestimmte Stücke.
// «Instanz wählen» (specific) erlaubt AUCH verkaufte Ware – die Auswahl verkaufter Instanzen
// macht den Auftrag automatisch zur Retoure/Erstattung (kein eigenes Ziel mehr).
type OrderGoal = 'produce' | 'stock' | 'specific';

// Anker ist IMMER der Artikel + Menge. Was damit geschieht, ergibt sich aus dem Ablauf,
// der danach im Entwurf definiert wird (Erzeugung vs. Operation am Bestand). Optional
// lassen sich für eine Bestands-Operation bestimmte Instanzen fixieren (sonst FIFO).
type Form = { article_id: string; quantity: string; desired_delivery_date: string };

// Eine Position der Ziel-Karten («Instanz wählen»/FIFO): entweder der Auftrags-Anker
// (lineId=null, Einzel-Artikel-Auftrag) oder eine Position eines Mehrpositionen-Auftrags.
// Dieselbe Struktur bedient beide Fälle, damit die Ziel-Karten nicht zweimal gebaut werden.
type PinLine = {
  key: string; lineId: number | null; articleId: number; unit: string; reqQty: number;
  pinnedIds: number[]; pinnedQty: number; pool: Instance[]; availableQty: number;
};

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


function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// Abgeleitete Subjektart des Auftrags (kein Modus-Flag) – für die Anzeige.
function subjectRoleLabel(role: string | null | undefined): string {
  // Ein Unter-Auftrag, der auf vorhandene Instanzen wirkt, ist eine Bestands-Operation –
  // KEINE eigene «Abweichung»-Art (Status/Art bleiben für alle Aufträge einheitlich).
  return role === 'stock' || role === 'deviation' || role === 'return' ? 'Operation am Bestand' : 'Herstellung – erzeugt Instanzen';
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

export function OrderDetail({ record, articles, viewerRole, company, suppliers = [], onSaved, onCancel, onBack }: {
  record: Order | null;            // null ⇒ Anlage-Modus (nur Mitarbeiter)
  articles: Article[];
  viewerRole: ViewerRole;
  company: Partial<CompanySettings> | null;
  suppliers?: UserProfile[];
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
  const [tab, setTab] = useState<OrderTab>('auftrag');
  const [dialog, setDialog] = useState<'deactivate' | null>(null);
  const [deviationBusy, setDeviationBusy] = useState(false);
  const [supplyBusy, setSupplyBusy] = useState(false);
  const [recoverBusy, setRecoverBusy] = useState(false);
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
  // Eine Retoure (reason='return') ist ein Unter-Auftrag eines abgeschlossenen Verkaufs auf
  // dessen verkaufte Instanzen (Rücknahme + Gutschrift); pausiert den Eltern ebenfalls nicht.
  const isReturn = record?.reason === 'return';
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
  // Mehrpositionen-Auftrag: der Bedarf steht auf ``order_lines`` statt Artikel/Menge am
  // Auftrag selbst (Anker wird bei der ersten zusätzlichen Position dorthin überführt).
  const isMultiPosition = (record?.order_lines?.length ?? 0) > 0;
  const orderLines = record?.order_lines ?? [];

  // Anker: Artikel + Menge. Bedarf (Artikel/Menge/Termin) wird per Auto-Save persistiert.
  // Bei einem Mehrpositionen-Auftrag steht der Bedarf auf den Positionen – nur der Termin
  // bleibt hier ein Auto-Save-Feld.
  const qtyNum = form.quantity.trim() ? Number(form.quantity) : null;
  const demandValid = isMultiPosition || (!!form.article_id && qtyNum != null && qtyNum > 0);
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
  // «Herstellen» ist bei einem Mehrpositionen-Auftrag NIE möglich (mehrere Artikel – kein
  // EINER Artikel-Prozess, den er fahren könnte; Backend erzwingt dort immer `stock`).
  const canProduce = !isMultiPosition && !hasCustomSteps;

  // Verfügbarer Lagerbestand je Position (für die Ziel-Karten + «Instanz wählen»). Bei
  // einem Mehrpositionen-Auftrag EINE Zeile je Position, sonst eine synthetische Zeile
  // für den Anker – dieselbe Ableitung bedient also Einzel- wie Mehrpositionen-Auftrag.
  const [pinPool, setPinPool] = useState<Instance[]>([]);
  useEffect(() => {
    // Bei einem Unter-Auftrag (Abweichung/Nachschub) stehen die Instanzen fest – kein Lagerpool nötig.
    if (!isDraftStaff || isSubOrder) { setPinPool([]); return; }
    api.getInstances(500).then(setPinPool).catch(() => {});
  }, [isDraftStaff, isSubOrder]);

  const pinnedByArticle = new Map<number, { ids: number[]; qty: number }>();
  for (const i of record?.instances ?? []) {
    if (i.object_id == null) continue;
    const cur = pinnedByArticle.get(i.article_id) ?? { ids: [], qty: 0 };
    cur.ids.push(i.object_id);
    cur.qty += i.quantity ?? 0;
    pinnedByArticle.set(i.article_id, cur);
  }
  function buildPinLine(lineId: number | null, articleId: number, unit: string, reqQty: number): PinLine {
    const pool = pinPool.filter((i) =>
      i.object_id != null && i.article_id === articleId &&
      i.quality === 'passed' && i.disposition === 'in_stock' &&
      (i.reserved_for_order_object_id == null || i.reserved_for_order_object_id === record?.object_id));
    const pinned = pinnedByArticle.get(articleId) ?? { ids: [], qty: 0 };
    return {
      key: lineId != null ? `line-${lineId}` : 'anchor', lineId, articleId, unit, reqQty,
      pinnedIds: pinned.ids, pinnedQty: pinned.qty, pool,
      availableQty: pool.reduce((s, i) => s + (i.quantity ?? 0), 0),
    };
  }
  const pinLines: PinLine[] = isMultiPosition
    ? orderLines.map((l) => buildPinLine(l.id, l.article_id, l.article_unit ? unitLabel(l.article_unit) : '', l.quantity))
    : record?.article_id != null
      ? [buildPinLine(null, record.article_id, qtyUnit, record.quantity ?? 0)]
      : [];
  const reqQty = record?.quantity ?? 0;
  const availableQty = pinLines.reduce((s, l) => s + l.availableQty, 0);
  // Genug Bestand für eine reine Bestands-Operation? (JEDE Position muss gedeckt sein)
  const enoughStock = pinLines.length > 0 && pinLines.every((l) => l.reqQty > 0 && l.availableQty >= l.reqQty);

  // Ziel der Auftragsanlage (Ziel-Karten). Pins ⇒ «Instanz wählen»; eigene Schritte ⇒
  // «Aus Lager»; sonst «Herstellen». Über die Karten wechselbar (pickGoal räumt Pins beim
  // Verlassen von «Instanz wählen» auf, damit «Aus Lager» wirklich reines FIFO ist).
  const pins = pinLines.flatMap((l) => l.pinnedIds);
  const [goalSel, setGoalSel] = useState<OrderGoal | null>(null);
  // Verkaufte Instanzen des Artikels – unter «Instanz wählen» ebenfalls wählbar; ihre Auswahl
  // macht den Auftrag automatisch zur Retoure/Erstattung (reason='return', Backend leitet ab).
  const soldPool = pinPool.filter((i) =>
    i.object_id != null && i.article_id === record?.article_id && i.disposition === 'sold');
  const [refundIds, setRefundIds] = useState<number[]>([]);
  const goal: OrderGoal = pins.length > 0
    ? 'specific'
    : !canProduce
      ? (goalSel === 'specific' ? 'specific' : 'stock')
      : (goalSel ?? 'produce');

  async function pickGoal(g: OrderGoal) {
    setGoalSel(g);
    if (g !== 'specific') {   // «Aus Lager»/«Herstellen» = ohne Pins
      for (const l of pinLines) {
        if (l.pinnedIds.length > 0) await setLinePins(l, []);
      }
    }
  }
  function togglePin(line: PinLine, oid: number) {
    const ids = line.pinnedIds.includes(oid) ? line.pinnedIds.filter((x) => x !== oid) : [...line.pinnedIds, oid];
    setLinePins(line, ids);
  }

  // Mehrpositionen-Auftrag: JEDE Position entscheidet SELBST «Aus Lager (FIFO)» oder «Instanz
  // wählen» – nicht mehr global für alle. Der Modus ist abgeleitet (hat die Position Pins →
  // specific) mit einem UI-Override, solange noch keine Instanz gewählt ist.
  const [lineModes, setLineModes] = useState<Record<string, 'fifo' | 'specific'>>({});
  function lineMode(l: PinLine): 'fifo' | 'specific' {
    if (l.pinnedIds.length > 0) return 'specific';
    return lineModes[l.key] ?? 'fifo';
  }
  async function setLineMode(l: PinLine, m: 'fifo' | 'specific') {
    setLineModes((prev) => ({ ...prev, [l.key]: m }));
    if (m === 'fifo' && l.pinnedIds.length > 0) await setLinePins(l, []);
  }

  // «Instanz wählen» verlangt, dass die gewählten Instanzen die Menge GENAU decken. Bei einem
  // Mehrpositionen-Auftrag gilt das je Position, die auf «Instanz» steht (FIFO-Positionen sind
  // immer ok – eine Fehlmenge deckt später der Nachschub).
  const specificComplete = isMultiPosition
    ? pinLines.every((l) => lineMode(l) === 'fifo' || l.pinnedQty === l.reqQty)
    : (goal !== 'specific' || (pinLines.length > 0 && pinLines.every((l) => l.pinnedQty === l.reqQty)));
  // Unter-Auftrag (Abweichung/Nachschub): Subjekt steht schon fest – Freigabe braucht nur einen
  // definierten Ablauf (mind. einen Schritt, der festlegt, was geschieht / wie nachgeschoben wird).
  const stepCount = orderStepCount ?? (record?.steps?.length ?? 0);
  const subOrderReady = stepCount > 0;
  // Freigabe: Bedarf gespeichert UND – je nach Auftragsart – Ablauf definiert (Unter-Auftrag)
  // bzw. Instanzauswahl vollständig (reguläre Bestands-Operation «Instanz wählen»).
  // Ein Unter-Auftrag (Abweichung/Nachschub) hat sein Subjekt bereits fest (Instanzen/
  // Artikel-Prozess) – braucht KEIN eigenes Artikel/Menge-Paar zur Freigabe (schliesst
  // sonst eine Abweichung eines Mehrpositionen-Auftrags dauerhaft aus der Freigabe aus).
  const hasDemand = isSubOrder || isMultiPosition || (!!record?.article_id && !!record?.quantity);
  const canRelease = !isCreate && hasDemand
    && sig === savedSig && (isSubOrder ? subOrderReady : specificComplete);
  const releaseHint = isSubOrder
    ? (subOrderReady ? undefined : (isSupply ? 'Erst einen Prozessschritt für den Nachschub hinzufügen' : isReturn ? 'Erst einen Prozessschritt für die Retoure hinzufügen' : 'Erst einen Prozessschritt für die Abweichung hinzufügen'))
    : (!specificComplete
      ? (isMultiPosition ? 'Erst für jede Position die passenden Instanzen wählen' : `Erst genau ${reqQty} Instanz(en) wählen`)
      : 'Erst Artikel und Menge speichern');

  async function setLinePins(line: PinLine, ids: number[]) {
    if (!record) return;
    try {
      const saved = line.lineId != null
        ? await api.setOrderLinePins(record.object_id as number, line.lineId, { instance_object_ids: ids })
        : await api.updateOrder(record.object_id as number, { instance_object_ids: ids, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Festlegen der Instanzen'); }
  }

  async function addPosition(articleId: number, quantity: number) {
    if (!record) return;
    const saved = await api.addOrderLine(record.object_id as number, { article_id: articleId, quantity });
    verRef.current = saved.updated_at;
    onSaved(saved);
  }

  // «Verkaufte Ware zurücknehmen»: die gewählten VERKAUFTEN Instanzen als Subjekt fixieren – über
  // denselben Pin-Pfad wie Lager-Instanzen (`instance_object_ids`). Das Backend erkennt verkaufte
  // Instanzen und macht den Auftrag zur Retoure (reason='return' + parent = Original-Verkauf);
  // danach zeigt sich der Ablauf-Editor (Bewegung + Gutschrift) wie bei jedem Unter-Auftrag.
  async function bindRefund(ids: number[]) {
    if (!record) return;
    try {
      const saved = await api.updateOrder(record.object_id as number, { instance_object_ids: ids, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) { setError(e instanceof Error ? e.message : 'Retoure konnte nicht angelegt werden'); }
  }

  async function removePosition(lineId: number) {
    if (!record) return;
    try {
      const saved = await api.removeOrderLine(record.object_id as number, lineId);
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Entfernen der Position'); }
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
        // Bei einem Mehrpositionen-Auftrag sind Artikel/Menge am Auftrag nicht mehr das
        // Feld für den Bedarf (der steht auf den Positionen) – nur der Termin wird hier
        // noch per Auto-Save persistiert (das Backend weist article_id/quantity sonst ab).
        const payload: OrderUpdateInput = { desired_delivery_date: effectiveDate, expected_updated_at: verRef.current };
        if (!isMultiPosition) {
          payload.article_id = form.article_id ? Number(form.article_id) : null;
          payload.quantity = qtyNum;
        }
        const saved = await api.updateOrder(record.object_id as number, payload);
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

  // «Aus Lager decken» (FIFO, ohne ids) / «Andere Instanz wählen» (gezielt): deckt die
  // Subjekt-Fehlmenge eines blockierten Schritts aus vorhandenem Lagerbestand.
  async function coverFromStock(instanceObjectIds?: number[]) {
    if (!record) return;
    setRecoverBusy(true);
    setError(null);
    try {
      onSaved(await api.coverStock(record.object_id as number, instanceObjectIds));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Aus Lager decken fehlgeschlagen');
    } finally {
      setRecoverBusy(false);
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
        {/* Reiter (nur Personal, nur bei bestehendem Auftrag): Dokumente-Reiter dazu. */}
        {isStaff && !isCreate && (
          <DetailTabs<OrderTab> style={{ marginTop: 10 }} active={tab} onChange={setTab} tabs={[
            { key: 'auftrag', label: 'Auftrag', icon: ClipboardList },
            { key: 'docs', label: 'Dokumente', icon: FolderOpen },
          ]} />
        )}
      </div>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'docs' && !isCreate ? (
          <ObjectDocuments objectId={record?.object_id ?? null} contextLabel="diesem Auftrag" />
        ) : (<>
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
        {/* Retouren sichtbar machen – Unteraufträge auf die verkauften Instanzen dieses Verkaufs
            (Rücknahme + Gutschrift). Wie ein Nachschub pausieren sie den Eltern NICHT. */}
        {!isCreate && isStaff && (record.returns?.length ?? 0) > 0 && (
          <div style={{ marginBottom: 12, border: '1px solid #e2e8f0', borderRadius: 10, background: '#fff', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', fontSize: 13, fontWeight: 700, color: '#0f172a', borderBottom: '1px solid #f1f5f9' }}>
              <Undo2 size={16} style={{ color: '#0891b2' }} />
              Retouren
              <span style={{ marginLeft: 'auto', fontWeight: 700, color: '#0e7490' }}>{record.returns!.length}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {record.returns!.map((d) => (
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
          </div>
        )}
        {isCompleted && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '12px 14px', background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 10, fontSize: 13, color: '#0f766e', fontWeight: 600 }}>
            <CheckCircle2 size={16} /> Auftrag abgeschlossen – alle Prozessschritte erledigt.
          </div>
        )}

        {/* Bedarf – Einzel-Artikel (wie gewohnt: Artikel + Menge) ODER, sobald mindestens
            eine weitere Position hinzugefügt wurde, die Liste der Positionen. Weitere
            Positionen lassen sich JEDERZEIT ergänzen (auch nach dem ersten Speichern). */}
        <SectionTitle>Bedarf</SectionTitle>
        <div style={cardStyle}>
          {demandEditable ? (
            <>
              {isMultiPosition ? (
                <PositionsList lines={orderLines} onRemove={removePosition} />
              ) : (
                <>
                  <SearchSelect label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />
                  {isCreate && releasedArticles.length === 0 && (
                    <div style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 10px' }}>
                      Kein freigegebener Artikel vorhanden. Nur freigegebene Artikel sind referenzierbar.
                    </div>
                  )}
                </>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: isMultiPosition ? '1fr' : '1fr 1fr', gap: 14 }}>
                {!isMultiPosition && (
                  <TextFieldUnit label="Menge" value={form.quantity} onChange={(v) => set('quantity', v)} unit={qtyUnit} required placeholder="z. B. 5" />
                )}
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
              {/* Weitere Position: erst möglich, sobald der Auftrag existiert (die erste
                  Position entsteht wie gewohnt über Artikel/Menge oben + Auto-Save). */}
              {!isCreate && record?.status === 'draft' && (
                <AddPositionRow articles={releasedArticles}
                  excludeArticleIds={isMultiPosition ? orderLines.map((l) => l.article_id) : (record?.article_id != null ? [record.article_id] : [])}
                  onAdd={addPosition} />
              )}
            </>
          ) : (
            <>
              {isMultiPosition ? (
                <PositionsList lines={orderLines} />
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
                    <span style={{ color: '#94a3b8', flexShrink: 0 }}>Artikel</span>
                    <span style={{ textAlign: 'right' }}>
                      {record?.article_object_id != null ? <ObjId value={record.article_object_id} /> : '—'}
                    </span>
                  </div>
                  <Row k="Menge" v={record?.quantity != null ? `${record.quantity} ${record.article_unit ? unitLabel(record.article_unit) : ''}`.trim() : '—'} />
                </>
              )}
              <Row k="Wunsch-Liefertermin" v={record?.desired_delivery_date ? localDate(record.desired_delivery_date) : 'Schnellstmöglich'} />
              <Row k="Art" v={subjectRoleLabel(record?.subject_role)} />
            </>
          )}
        </div>

        {/* Wiederkehrend – nur im Entwurf einstellbar (ein freigegebener Auftrag
            ist „scharf" und lässt sich nicht mehr auf wiederkehrend umstellen). Bei einem
            Unter-Auftrag (Abweichung/Nachschub) nicht sinnvoll. */}
        {isStaff && record?.status === 'draft' && !isSubOrder && <RecurrenceCard order={record} onSaved={onSaved} version={verRef} />}

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
              : isReturn
                ? 'Lege fest, was mit der zurückkommenden Ware geschieht (Rücknahme ins Lager, Gutschrift, optional Prüfung/Verschrottung). Mit der Freigabe wird die Retoure scharf.'
                : 'Lege fest, was mit den oben genannten Instanzen geschieht (bewegen, verschrotten, prüfen, beschaffen …). Mit der Freigabe wird die Abweichung scharf.'}>
              {isSupply ? 'Ablauf des Nachschubs' : isReturn ? 'Ablauf der Retoure' : 'Ablauf der Abweichung'}
            </SectionTitle>
            <div style={cardStyle}>
              {/* FIX: suppliers war hier (und an den zwei weiteren Stellen) als [] hartkodiert –
                  ein Beschaffungs-Schritt am Auftrag konnte NIE einen Lieferanten wählen
                  («Keine Lieferanten vorhanden»), obwohl welche existieren. */}
              <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={suppliers}
                selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
            </div>
          </>
        )}

        {/* Ziel der Auftragsanlage – «Was möchten Sie tun?» (DAU-sicher: Symbol + Farbe +
            Klartext, Live-Verfügbarkeit, unmögliche Optionen deaktiviert mit Begründung).
            Bei mehreren Positionen scheidet «Herstellen» aus (kein EINER Artikel-Prozess,
            den ein Mehrpositionen-Auftrag fahren könnte) – nur FIFO oder Instanz wählen. */}
        {isStaff && record?.status === 'draft' && !isSubOrder && !isMultiPosition && (
          <>
            <SectionTitle icon={Workflow}>Was möchten Sie tun?</SectionTitle>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10, marginBottom: 12 }}>
              <GoalCard icon={Factory} tone="#0f766e" active={goal === 'produce'}
                disabled={!canProduce}
                disabledHint={'Erst die Auftrags-Schritte entfernen'}
                title="Herstellen / Beschaffen"
                desc={`Bei Freigabe entstehen ${reqQty || ''} ${qtyUnit} neu – der Prozess des Artikels wird gefahren.`}
                footer="Neuer Bestand"
                onClick={() => pickGoal('produce')} />
              <GoalCard icon={Warehouse} tone="#2563eb" active={goal === 'stock'}
                disabled={!enoughStock}
                disabledHint={availableQty < 1 ? 'Kein Bestand vorhanden' : `Nur ${availableQty} ${qtyUnit} am Lager (${reqQty} benötigt)`}
                title="Aus dem Lager"
                desc={'Vorhandene Stück verarbeiten – das System wählt automatisch die ältesten (FIFO).'}
                footer={`Lager: ${availableQty} ${qtyUnit} verfügbar`}
                onClick={() => pickGoal('stock')} />
              <GoalCard icon={Target} tone="#7c3aed" active={goal === 'specific'}
                disabled={!enoughStock && soldPool.length === 0}
                disabledHint={availableQty < 1 && soldPool.length === 0 ? 'Kein Bestand vorhanden' : `Nur ${availableQty} ${qtyUnit} am Lager (${reqQty} benötigt)`}
                title="Instanz wählen"
                desc={'Genau wählen, welche Instanzen verarbeitet werden – auch VERKAUFTE Ware (→ Retoure/Erstattung).'}
                footer={soldPool.length > 0 ? `Lager: ${availableQty} · verkauft: ${soldPool.length}` : `Lager: ${availableQty} ${qtyUnit} verfügbar`}
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
                {goal === 'specific' && (
                  <>
                    <SectionTitle icon={Boxes}>Instanzen wählen</SectionTitle>
                    {availableQty > 0 && pinLines.map((line) => <PinPicker key={line.key} line={line} onToggle={togglePin} />)}
                    {/* Verkaufte Ware ebenfalls hier wählbar – die Auswahl macht den Auftrag zur
                        Retoure/Erstattung (reason='return', danach Ablauf-Editor). */}
                    {soldPool.length > 0 && (
                      <RefundSubjectPicker sold={soldPool} value={refundIds} onChange={setRefundIds}
                        onConfirm={() => bindRefund(refundIds)} error={error} />
                    )}
                  </>
                )}
                <SectionTitle icon={Workflow} info={goal === 'specific'
                  ? 'Schritte definieren, was mit den gewählten Instanzen geschieht (bewegen, verkaufen, prüfen …).'
                  : `Schritte definieren, was mit ${reqQty || ''} ${qtyUnit} ab Lager geschieht – die ältesten zuerst (FIFO).`}>Ablauf</SectionTitle>
                <div style={cardStyle}>
                  <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={suppliers}
                    selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
                </div>
              </>
            )}
          </>
        )}

        {/* Mehrpositionen-Auftrag: JE POSITION entscheiden – aus dem Lager (FIFO) oder
            bestimmte Instanzen wählen. «Herstellen» scheidet aus (kein EINER Artikel-Prozess).
            Flexibler als der frühere globale Modus, gleiche Optik wie die Einzel-Auswahl. */}
        {isStaff && record?.status === 'draft' && !isSubOrder && isMultiPosition && (
          <>
            <SectionTitle icon={Workflow}>Was möchten Sie tun?</SectionTitle>
            <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5, marginBottom: 8 }}>
              Mehrere Positionen – <strong style={{ color: '#0f172a' }}>je Position</strong> wählen:
              aus dem Lager (FIFO) oder bestimmte Instanzen. «Herstellen» ist hier nicht möglich
              (dafür je Artikel einen eigenen Auftrag anlegen).
            </div>
            {pinLines.map((line) => {
              const lineInfo = orderLines.find((l) => l.id === line.lineId);
              const mode = lineMode(line);
              return (
                <div key={line.key} style={{ ...cardStyle, gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: '#0F172A' }}>
                    {lineInfo?.article_object_id != null && <ObjId value={lineInfo.article_object_id} />}
                    <span style={{ flex: 1 }}>{lineInfo?.article_name ?? `Artikel #${line.articleId}`}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>{line.reqQty} {line.unit}</span>
                  </div>
                  {/* Segmentierter Umschalter FIFO / Instanz wählen */}
                  <div style={{ display: 'flex', gap: 6 }}>
                    <SegBtn active={mode === 'fifo'} icon={Warehouse} tone="#2563eb"
                      label="Aus dem Lager (FIFO)" onClick={() => setLineMode(line, 'fifo')} />
                    <SegBtn active={mode === 'specific'} icon={Target} tone="#7c3aed"
                      label="Instanz wählen" onClick={() => setLineMode(line, 'specific')} />
                  </div>
                  {mode === 'fifo' ? (
                    <div style={{ fontSize: 12, color: '#64748b' }}>
                      Die ältesten {line.reqQty} {line.unit} werden automatisch verarbeitet (FIFO).
                      {line.availableQty < line.reqQty && (
                        <span style={{ color: '#d97706' }}> · nur {line.availableQty} am Lager – Fehlmenge deckt der Nachschub.</span>
                      )}
                    </div>
                  ) : (
                    <PinPicker line={line} onToggle={togglePin} bare />
                  )}
                </div>
              );
            })}
            <SectionTitle icon={Workflow}
              info="Schritte definieren, was mit den Positionen geschieht (bewegen, verkaufen, prüfen …).">Ablauf</SectionTitle>
            <div style={cardStyle}>
              <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={suppliers}
                selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
            </div>
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
            {record.paused ? (
              // Angehalten wegen offener Abweichung: der GANZE Auftrag ruht (das Backend lehnt
              // jede Schritt-Ausführung ab). KEIN interaktives Panel – nur die On-Hold-Notiz,
              // die auf die zu klärende Abweichung verweist (dieselbe Sprache wie die Unterdeckung).
              <ProcessHoldNotice reason="deviation" step={currentStepObj} isStaff={isStaff}
                canSupply={false} busy={false} recoverBusy={false} error={error}
                onSupply={requestSupply} onCoverStock={coverFromStock}
                deviations={record.deviations ?? []} onOpen={(oid) => nav?.(oid)} />
            ) : currentStepObj?.state === 'blocked' ? (
              <ProcessHoldNotice reason="shortfall" step={currentStepObj} isStaff={isStaff} canSupply={record.status === 'released'}
                busy={supplyBusy} recoverBusy={recoverBusy} error={error} onSupply={requestSupply}
                onCoverStock={coverFromStock} />
            ) : (
              <StepPanel key={currentStepId ?? 'none'} step={currentStepObj} order={record as Order} viewerRole={viewerRole} company={company} onSaved={afterStep} />
            )}
          </>
        ) : !isStaff && hasPurchase ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <PurchaseStepPanel order={record as Order} purchases={record?.purchase ? [record.purchase] : []}
              viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
          </>
        ) : null}

        </>)}
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


function stepHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

// Subjekt-Schritte wirken auf die Fertigware des Auftrags (nicht auf Komponenten). Nur bei
// ihnen ist «Aus Lager decken» (inkl. gezielter Instanz-Auswahl) sinnvoll – ein Komponenten-
// Bedarf (Ressource) wird ausschliesslich über Nachschub gedeckt.
const SUBJECT_STEP_TYPES = ['movement', 'inspection', 'scrap', 'sale'];

// EIN einheitliches «Prozess angehalten» (on hold) für beide Gründe, warum ein Auftrag nicht
// weiterläuft – konsistente Sprache/Optik statt zweier Metaphern:
//   • reason='deviation' – eine offene Abweichung hält den GANZEN Auftrag an (Backend lehnt
//     jede Schritt-Ausführung ab). Auflösung: die Abweichung abschliessen/zurücknehmen.
//   • reason='shortfall' – ein Subjekt-/Komponentenbedarf ist unterdeckt; der betroffene
//     Schritt ruht. Zwei Wege: Nachschub (produzieren/beschaffen) ODER aus Lager decken
//     (FIFO, mit Unterkategorie «bestimmte Instanz wählen»). Löst sich von selbst, sobald
//     der Bedarf gedeckt ist. GLEICH für alle Auftragsarten (Bestand wie Erzeugung).
function ProcessHoldNotice({ reason, step, isStaff, canSupply, busy, recoverBusy, error, onSupply, onCoverStock, deviations, onOpen }: {
  reason: 'deviation' | 'shortfall';
  step: OrderStep | null;
  isStaff: boolean;
  canSupply: boolean;
  busy: boolean;
  recoverBusy: boolean;
  error: string | null;
  onSupply: () => void;
  onCoverStock: (instanceObjectIds?: number[]) => void;
  deviations?: OrderDeviationInfo[];
  onOpen?: (objectId: number) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [picked, setPicked] = useState<number[]>([]);

  // ── Angehalten wegen offener Abweichung (ganzer Auftrag ruht) ──────────────────
  if (reason === 'deviation') {
    const open = (deviations ?? []).filter((d) => d.status === 'draft' || d.status === 'released');
    return (
      <HoldFrame title="Prozess angehalten – Abweichung offen">
        <div style={{ fontSize: 12, color: '#92400e', lineHeight: 1.5 }}>
          Solange eine Abweichung offen ist, ruht der gesamte Auftrag – es lässt sich kein Schritt
          ausführen (auch die betroffene Instanz nicht). Bitte zuerst die Abweichung abschliessen
          oder zurücknehmen; danach läuft der Prozess automatisch weiter.
        </div>
        {open.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {open.map((d) => (
              <button key={d.object_id} type="button" onClick={() => onOpen?.(d.object_id)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#0f172a', background: '#fff', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 12px', cursor: 'pointer', textAlign: 'left' }}>
                <AlertTriangle size={14} style={{ color: '#b45309', flexShrink: 0 }} />
                <span>Abweichung <ObjId value={d.object_id} /> {d.status === 'draft' ? 'bearbeiten' : 'abschliessen'}
                  {d.instance_count > 0 && <span style={{ color: '#64748b' }}> · {d.instance_count === 1 ? '1 Instanz' : `${d.instance_count} Instanzen`}</span>}</span>
              </button>
            ))}
          </div>
        )}
        {error && <span style={{ fontSize: 12, color: '#dc2626' }}>{error}</span>}
      </HoldFrame>
    );
  }

  // ── Angehalten wegen Unterdeckung (nur der betroffene Schritt) ─────────────────
  const running = step?.supply_order_object_ids ?? [];
  const hasRunning = running.length > 0;
  const shortfall = step?.shortfall ?? [];
  const isSubjectStep = step ? SUBJECT_STEP_TYPES.includes(step.step_type) : false;
  const availableInstances = shortfall.flatMap((sf) => sf.available_instances ?? []);
  const stockAvailable = shortfall.reduce((s, sf) => s + (sf.available_quantity ?? 0), 0);
  const canRecover = isStaff && canSupply && !hasRunning;
  const busyAny = busy || recoverBusy;

  function togglePick(oid: number) {
    setPicked((p) => (p.includes(oid) ? p.filter((x) => x !== oid) : [...p, oid]));
  }

  return (
    <HoldFrame title="Prozess angehalten – Unterdeckung">
      <div style={{ fontSize: 12, color: '#92400e', lineHeight: 1.5 }}>
        Dieser Schritt ruht – das benötigte Material ist nicht (mehr) am Lager
        {isSubjectStep && <> (z. B. weil ein Stück per Abweichung ausgesteuert wurde)</>}.
        {canRecover && isSubjectStep
          ? ' Wählen Sie, wie es weitergeht:'
          : ' Sobald der Nachschub geliefert hat, läuft der Schritt automatisch weiter.'}
      </div>
      {shortfall.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {shortfall.map((sf, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#0f172a' }}>
              <PackageMinus size={14} style={{ color: '#b45309', flexShrink: 0 }} />
              <span>
                <strong>{sf.quantity}</strong> × {sf.article_name ?? 'Artikel'}
                {sf.article_object_id != null && <> (<ObjId value={sf.article_object_id} />)</>} fehlt
                {(sf.available_quantity ?? 0) > 0 && <span style={{ color: '#64748b' }}> · {sf.available_quantity} am Lager frei</span>}
              </span>
            </div>
          ))}
        </div>
      )}
      {hasRunning && (
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, fontSize: 13, color: '#92400e', fontWeight: 600 }}>
          <PackagePlus size={15} style={{ color: '#b45309', flexShrink: 0 }} />
          Nachschub läuft:
          {running.map((oid) => <ObjId key={oid} value={oid} />)}
        </div>
      )}
      {canRecover && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Zwei Wege, EINHEITLICH für alle Auftragsarten: liegt der Artikel bereits am Lager,
              ist «Aus Lager decken» (FIFO) der schnellste Weg – mit Unterkategorie «bestimmte
              Instanz wählen». Sonst «Nachschub anlegen» (produzieren/beschaffen). */}
          {isSubjectStep && stockAvailable > 0 ? (
            <>
              <PrimaryButton icon={Warehouse} onClick={() => onCoverStock()} disabled={busyAny}>
                {recoverBusy ? 'Wird gedeckt…' : 'Aus Lager decken (FIFO)'}
              </PrimaryButton>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {availableInstances.length > 0 && (
                  <SecondaryAction icon={Boxes} label="Bestimmte Instanz wählen" onClick={() => setPickerOpen((o) => !o)} disabled={busyAny} active={pickerOpen} />
                )}
                <SecondaryAction icon={PackagePlus} label="Stattdessen Nachschub produzieren" onClick={onSupply} disabled={busyAny} />
              </div>
            </>
          ) : (
            <PrimaryButton icon={PackagePlus} onClick={onSupply} disabled={busyAny}>
              {busy ? 'Nachschub wird angelegt…' : 'Nachschub anlegen'}
            </PrimaryButton>
          )}
          {pickerOpen && availableInstances.length > 0 && (
            <div style={{ border: '1px solid #fde68a', borderRadius: 8, background: '#fff', padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, color: '#64748b' }}>Ersatz-Instanz(en) am Lager wählen:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {availableInstances.map((ai) => {
                  const sel = picked.includes(ai.object_id);
                  return (
                    <button key={ai.object_id} type="button" onClick={() => togglePick(ai.object_id)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                        padding: '4px 10px', borderRadius: 999, cursor: 'pointer',
                        border: `1px solid ${sel ? '#7c3aed' : '#e2e8f0'}`,
                        background: sel ? '#f5f3ff' : '#fff', color: sel ? '#6d28d9' : '#475569',
                      }}>
                      {sel && <CheckCircle2 size={12} />}
                      {fmtObjId(ai.object_id)}{ai.quantity > 1 ? ` ·${ai.quantity}` : ''}
                    </button>
                  );
                })}
              </div>
              <PrimaryButton icon={CheckCircle2} onClick={() => { onCoverStock(picked); setPickerOpen(false); setPicked([]); }} disabled={busyAny || picked.length === 0}>
                {recoverBusy ? 'Wird übernommen…' : 'Gewählte Instanzen übernehmen'}
              </PrimaryButton>
            </div>
          )}
        </div>
      )}
      {error && <span style={{ fontSize: 12, color: '#dc2626' }}>{error}</span>}
    </HoldFrame>
  );
}

// Einheitlicher Rahmen für «Prozess angehalten» – gleiche Optik/Ikonografie wie die Pause-Leiste.
function HoldFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ border: '1px solid #fde68a', borderRadius: 10, background: '#fffbeb', overflow: 'hidden', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', fontSize: 14, fontWeight: 700, color: '#92400e', borderBottom: '1px solid #fde68a' }}>
        <PauseCircle size={17} /> {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px' }}>
        {children}
      </div>
    </div>
  );
}

// Kleiner Sekundär-Knopf (nicht die grosse Hauptaktion) für die weiteren Deckungs-Wege.
function SecondaryAction({ icon: Icon, label, onClick, disabled, active }: {
  icon: React.ElementType; label: string; onClick: () => void; disabled?: boolean; active?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600,
        padding: '7px 12px', borderRadius: 8, cursor: disabled ? 'default' : 'pointer',
        border: `1px solid ${active ? '#7c3aed' : '#e2e8f0'}`,
        background: active ? '#f5f3ff' : '#fff', color: active ? '#6d28d9' : '#475569',
        opacity: disabled ? 0.5 : 1,
      }}>
      <Icon size={14} /> {label}
    </button>
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
    document: step.document ?? order.document,
  };
  const stepState = step.state;
  const stepId = step.id;
  if (step.step_type === 'purchase') {
    const purchases = (step.purchases.length > 0 ? step.purchases : (order.purchase ? [order.purchase] : [])) as OrderPurchase[];
    return purchases.length > 0
      ? <PurchaseStepPanel order={stepOrder} purchases={purchases} stepId={stepId} viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
      : <StepFallback />;
  }
  if (step.step_type === 'sale') {
    const sales = step.sales.length > 0 ? step.sales : (order.sale ? [order.sale] : []);
    return <SalePanel order={stepOrder} sales={sales} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'inspection') {
    return <InspectionPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'movement') {
    return <MovementPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'resource') {
    return <ResourcePanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'scrap') {
    return <ScrapPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'document') {
    return <DocumentPanel order={stepOrder} stepState={stepState} stepId={stepId} company={company} onOrderUpdated={onSaved} />;
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
        inputMode="decimal"
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

// Auswahl der zu erstattenden VERKAUFTEN Instanzen – macht den (normalen) Auftrag zur Retoure
// (reason='return' + parent = Original-Verkauf). Danach folgt der gewohnte Ablauf-Editor.
function RefundSubjectPicker({ sold, value, onChange, onConfirm, error }: {
  sold: Instance[]; value: number[]; onChange: (ids: number[]) => void;
  onConfirm: () => void; error: string | null;
}) {
  const [busy, setBusy] = useState(false);
  function toggle(oid: number) {
    onChange(value.includes(oid) ? value.filter((x) => x !== oid) : [...value, oid]);
  }
  async function confirm() { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
        Wähle die <strong style={{ color: '#0f172a' }}>verkauften Instanzen</strong>, die erstattet
        werden. Danach definierst du wie gewohnt den Ablauf – in aller Regel <strong>Bewegung</strong>{' '}
        (Ware zurück ins Lager) + <strong>Rückerstattung</strong> (Geld zurück).
      </div>
      {sold.length === 0 ? (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>Keine verkauften Instanzen dieses Artikels.</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {sold.map((i) => {
            const sel = value.includes(i.object_id!);
            return (
              <button key={i.object_id} type="button" onClick={() => toggle(i.object_id!)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                  padding: '4px 10px', borderRadius: 999, cursor: 'pointer',
                  border: `1px solid ${sel ? '#e11d48' : '#e2e8f0'}`,
                  background: sel ? '#fff1f2' : '#fff', color: sel ? '#be123c' : '#475569',
                }}>
                {sel && <CheckCircle2 size={12} />}{fmtObjId(i.object_id)}
              </button>
            );
          })}
        </div>
      )}
      {error && <span style={{ fontSize: 12, color: '#dc2626' }}>{error}</span>}
      <PrimaryButton icon={Undo2} onClick={confirm} disabled={busy || value.length === 0}>
        {busy ? 'Wird übernommen…' : `Als Retoure übernehmen (${value.length})`}
      </PrimaryButton>
    </div>
  );
}

// Segmentierter Umschalter (eine Option je Position: FIFO / Instanz wählen).
function SegBtn({ active, icon: Icon, tone, label, onClick }: {
  active: boolean; icon: React.ElementType; tone: string; label: string; onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick}
      style={{
        flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        fontSize: 12, fontWeight: 600, padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
        border: `1.5px solid ${active ? tone : '#E2E8F0'}`,
        background: active ? `${tone}14` : '#fff', color: active ? tone : '#475569',
      }}>
      <Icon size={14} /> {label}
    </button>
  );
}

// Instanz-Auswahl (Chips) für EINE Position – geteilt von Einzel-Artikel- und
// Mehrpositionen-Auftrag (dieselbe Optik). ``bare`` lässt den äusseren Karten-Rahmen weg
// (die Position bringt ihn schon mit).
function PinPicker({ line, onToggle, bare }: {
  line: PinLine; onToggle: (line: PinLine, oid: number) => void; bare?: boolean;
}) {
  const body = (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 12, color: '#64748b' }}>Genau {line.reqQty} {line.unit} wählen:</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: line.pinnedQty === line.reqQty ? '#16a34a' : '#d97706' }}>
          {line.pinnedQty} / {line.reqQty} gewählt
        </span>
      </div>
      {line.pool.length === 0 ? (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>Keine verfügbaren Instanzen.</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {line.pool.map((i) => {
            const sel = line.pinnedIds.includes(i.object_id!);
            const atLimit = !sel && line.pinnedQty + (i.quantity ?? 1) > line.reqQty;
            return (
              <button key={i.object_id} type="button" disabled={atLimit}
                onClick={() => onToggle(line, i.object_id!)}
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
    </>
  );
  if (bare) return <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{body}</div>;
  return <div style={cardStyle}>{body}</div>;
}

// Positionen eines Mehrpositionen-Auftrags – der Bedarf steht dann hier statt in den
// Artikel/Menge-Feldern. Ohne ``onRemove`` (read-only nach der Freigabe) kein Entfernen-Knopf.
function PositionsList({ lines, onRemove }: { lines: OrderLineInfo[]; onRemove?: (lineId: number) => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {lines.map((l) => (
        <div key={l.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
          {l.article_object_id != null && <ObjId value={l.article_object_id} />}
          <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 600, color: '#0F172A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {l.article_name ?? `Artikel #${l.article_id}`}
          </span>
          <span style={{ fontSize: 12, color: '#64748b', flexShrink: 0 }}>
            {l.quantity} {l.article_unit ? unitLabel(l.article_unit) : ''}
          </span>
          {onRemove && (
            <button type="button" onClick={() => onRemove(l.id)} title="Position entfernen"
              style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2, flexShrink: 0 }}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

// «+ Position hinzufügen» – jederzeit im Entwurf nutzbar (auch nach dem ersten Speichern),
// nicht nur bei der Anlage. Macht den Auftrag bei der ersten zusätzlichen Position zu
// einem Mehrpositionen-Auftrag (Backend wandelt den bisherigen Anker in Position 0 um).
function AddPositionRow({ articles, excludeArticleIds, onAdd }: {
  articles: Article[]; excludeArticleIds: number[]; onAdd: (articleId: number, quantity: number) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [articleId, setArticleId] = useState('');
  const [qty, setQty] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const options = articles.filter((a) => !excludeArticleIds.includes(a.id));
  const selectedArticle = options.find((a) => String(a.id) === articleId);
  const unit = selectedArticle ? unitLabel(selectedArticle.unit) : '';
  const qtyNum = qty.trim() ? Number(qty) : null;
  const valid = !!articleId && qtyNum != null && qtyNum > 0;

  async function submit() {
    if (!valid) return;
    setBusy(true); setErr(null);
    try {
      await onAdd(Number(articleId), qtyNum!);
      setArticleId(''); setQty(''); setOpen(false);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Fehler beim Hinzufügen'); }
    finally { setBusy(false); }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} style={{ ...linkBtn, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        <Plus size={13} /> Position hinzufügen
      </button>
    );
  }
  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 8 }}>
        <SearchSelect label="Artikel" value={articleId} onChange={setArticleId}
          options={[{ value: '', label: '— Artikel wählen —' }, ...options.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` }))]} />
        <TextFieldUnit label="Menge" value={qty} onChange={setQty} unit={unit} placeholder="z. B. 5" />
      </div>
      {err && <span style={{ fontSize: 12, color: '#dc2626' }}>{err}</span>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" onClick={submit} disabled={!valid || busy}
          style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: valid ? '#2563eb' : '#cbd5e1', color: '#fff', fontSize: 12, fontWeight: 700, cursor: valid ? 'pointer' : 'default' }}>
          {busy ? 'Wird hinzugefügt…' : 'Hinzufügen'}
        </button>
        <button type="button" onClick={() => { setOpen(false); setErr(null); }}
          style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #e2e8f0', background: '#fff', fontSize: 12, color: '#374151', cursor: 'pointer' }}>
          Abbrechen
        </button>
      </div>
    </div>
  );
}

const recInput = "w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";

/** «Wiederkehrend» direkt am Auftrag: bei Abschluss entsteht automatisch der nächste
 *  (Entwurf), Termin = Termin + Periode. Nur im Entwurf einstellbar. */
function RecurrenceCard({ order, onSaved, version }: {
  order: Order; onSaved: (o: Order) => void; version: MutableRefObject<string | null>;
}) {
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
      // FIX: Der Wiederkehr-Save lief am Optimistic Locking vorbei (kein expected_updated_at)
      // und liess verRef veralten – der NÄCHSTE Autosave (z. B. Liefertermin) scheiterte dann
      // mit einem unerklärlichen 409, obwohl niemand sonst den Auftrag angefasst hatte.
      const o = await api.updateOrder(order.object_id as number, {
        recurrence_active: active,
        recurrence_interval_days: active ? Math.max(1, Math.trunc(Number(interval) || 0)) : null,
        recurrence_lead_time_days: active ? Math.max(0, Math.trunc(Number(lead) || 0)) : 0,
        recurrence_anchor: active && anchor ? anchor : null,
        expected_updated_at: version.current,
      });
      version.current = o.updated_at;
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
