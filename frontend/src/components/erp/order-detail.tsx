'use client';

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { Ban, X, ClipboardList, ArrowLeft, Workflow, MapPin, CheckCircle2, Loader2, Repeat, ChevronDown, Boxes, Factory, Warehouse, Target, AlertTriangle, PauseCircle, PackagePlus, PackageMinus, Plus, Trash2, Undo2, FolderOpen, CalendarClock, Truck, Search } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderDeviationInfo, OrderLineInfo, OrderPurchase, OrderStep, OrderUpdateInput, UserProfile } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { unitLabel } from '@/lib/article';
import { toStepperState, STEP_META } from '@/lib/process';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import type { StatusAction } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { printObjectLabel } from '@/components/scan/object-label';
import { QrCode } from 'lucide-react';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { InfoHint, Label, PrimaryButton, Row, SaveIndicator, SearchSelect, SectionTitle, StatusBadge, StatusFlow, numericOnly, numericInputProps } from '@/components/erp/fields';
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

// Auftrag-Lebenszyklus mit Freigabe-Schutz (Artikel + Menge nötig). Ein freigegebener
// Ein laufender Auftrag hat KEINE Status-Aktion mehr: das frühere «Abbrechen» war ein zweiter
// Name und ein zweites UI für dieselbe Sache (es legte ja einen Abweichungsauftrag an). Es gibt
// jetzt nur noch den einen Knopf «Abweichungsauftrag» (Flag-Symbol im Kopf) – dort entscheidet
// man, ob der Auftrag weiterläuft oder abgebrochen ist.
// AUSNAHME Unter-Auftrag: er wird **verworfen** (nichts wird angelegt, die Bindungen zum
// Eltern werden gelöst) – das ist ein anderer Vorgang und heisst darum auch anders.
function orderActions(status: string, canRelease: boolean, isSubOrder: boolean,
                      releaseHint?: string): StatusAction[] {
  if (status === 'draft')
    return [
      { label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
        hint: canRelease ? undefined : releaseHint },
      ...(isSubOrder ? [{ label: 'Verwerfen', target: 'inactive', tone: 'danger' } as StatusAction] : []),
    ];
  if (status === 'released' && isSubOrder)
    return [{ label: 'Verwerfen', target: 'inactive', tone: 'danger' }];
  return [];
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
  const [dialog, setDialog] = useState<'deactivate' | 'deviation' | null>(null);
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
      // Lager-schlauer Default: ist der Bedarf vollständig ab Lager deckbar, NICHT versehentlich
      // «Herstellen» vorwählen (sonst wird trotz vollem Lager neu produziert). Sonst herstellen.
      : (goalSel ?? (enoughStock ? 'stock' : 'produce'));

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

  // ── EINE Quellen-Wahl je Position ────────────────────────────────────────────────
  // Einzel-Artikel und Mehrpositionen benutzen dieselbe Zeile und denselben Umschalter –
  // vorher waren das zwei völlig verschiedene Oberflächen (grosse Ziel-Karten vs. Segment-
  // Umschalter), sodass das Hinzufügen einer Position das ganze Fenster umbaute.
  function lineSource(l: PinLine): OrderGoal {
    if (isMultiPosition) return lineMode(l) === 'specific' ? 'specific' : 'stock';
    return goal;
  }
  async function setLineSource(l: PinLine, s: OrderGoal) {
    if (isMultiPosition) { await setLineMode(l, s === 'specific' ? 'specific' : 'fifo'); return; }
    await pickGoal(s);
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

  // «Abweichungsauftrag»: eröffnet einen Unterauftrag auf den Instanzen dieses Auftrags.
  // ``abortParent`` ist die EINE Entscheidung dabei – läuft der Auftrag danach weiter
  // (pausiert bis zur Klärung) oder ist er abgebrochen (sofort, endgültig)?
  async function reportDeviation(abortParent: boolean) {
    if (!record) return;
    setDialog(null);
    setDeviationBusy(true);
    setError(null);
    try {
      onSaved(await api.createDeviation(record.object_id as number, { abortParent }));
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
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
            <ClipboardList size={20} />
            {!isCreate && record.reason === 'deviation' && (
              <span title="Abweichungs-Auftrag" style={{ position: 'absolute', bottom: -3, right: -3, width: 17, height: 17, borderRadius: 999, background: '#fffbeb', border: '1px solid #fbbf24', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <AlertTriangle size={10} style={{ color: '#d97706' }} />
              </span>
            )}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', display: 'flex', alignItems: 'center', gap: 7 }}>
              Auftrag
              {!isCreate && record.reason === 'deviation' && (
                <span style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#b45309', background: '#fffbeb', border: '1px solid #fde68a', padding: '1px 7px', borderRadius: 999 }}>Abweichung</span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={orderStatusConfig('draft')} />
              ) : (isCompleted || !isStaff) ? (
                <StatusBadge cfg={orderStatusConfig(record.status, record.abort_into_id != null)} />
              ) : (
                <StatusFlow cfg={orderStatusConfig(record.status, record.abort_into_id != null)} actions={orderActions(record.status, canRelease, isSubOrder, releaseHint)} busy={statusBusy} onAction={onStatusAction} />
              )}
              {demandEditable && <SaveIndicator saving={saving} flash={flash} />}
            </div>
          </div>
          <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Kleine Kopf-Aktionen wie bei Instanz/Artikel: Etikett + «Abweichung melden»
                (Flag). Die grosse Karte im Detailfenster entfällt – EIN einheitliches UI. */}
            {!isCreate && record.object_id != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
                  onClick={() => printObjectLabel(record.object_id as number, record.article_name ?? 'Auftrag', 'Auftrag')}>
                  <QrCode size={15} />
                </button>
                {canReportDeviation && (
                  <button className="erp-idbtn erp-idbtn-flag" data-tip="Abweichungsauftrag anlegen (Defekt / Nacharbeit / Reklamation / Abbruch)" data-tip-pos="bottom"
                    aria-label="Abweichungsauftrag anlegen" disabled={deviationBusy} onClick={() => setDialog('deviation')}>
                    {deviationBusy ? <Loader2 size={15} className="animate-spin" /> : <AlertTriangle size={15} />}
                  </button>
                )}
              </div>
            )}
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
              <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>
                {isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}
              </div>
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
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 88px', background: 'var(--bg-2)', boxShadow: flash ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'docs' && !isCreate ? (
          <ObjectDocuments objectId={record?.object_id ?? null} contextLabel="diesem Auftrag" />
        ) : (<>
        {/* Abgebrochen: der Auftrag ist im Moment des Abbruchs inaktiv – nicht «ausstehend»,
            nicht rücknehmbar. Der Abweichungsauftrag führt ihn fort. */}
        {!isCreate && record.abort_into_id != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '12px 14px', background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 10, fontSize: 13, color: 'var(--danger)', fontWeight: 600 }}>
            <Ban size={16} /> Abgebrochen – fortgeführt im Abweichungsauftrag <ObjId value={record.abort_into_id} />.
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
        {/* Bereitstellungen sichtbar machen. Sie entstehen als EINZIGE Unter-Auftragsart
            **automatisch** (Material liegt am falschen Ort) – und genau darum müssen sie
            sichtbar sein: ein Auftrag, in dem plötzlich ein fremder Folgeauftrag mit aktivem
            Bewegen-Modul auftaucht, ist sonst nicht erklärbar. Sie blockieren den betroffenen
            Schritt UND den Abschluss; wer sie nicht braucht, bricht sie am Datensatz ab
            (sie wird dann nicht neu angelegt). */}
        {!isCreate && isStaff && (record.provisionings?.length ?? 0) > 0 && (
          <div style={{ marginBottom: 12, border: '1px solid #e2e8f0', borderRadius: 10, background: '#fff', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', fontSize: 13, fontWeight: 700, color: '#0f172a', borderBottom: '1px solid #f1f5f9' }}>
              <Truck size={16} style={{ color: 'var(--warning)' }} />
              Bereitstellung
              <InfoHint text="Vom System abgeleitet: das Material eines Schritts liegt nicht dort, wo der Schritt es braucht. Die Bewegung holt es – solange sie läuft, wartet der Schritt. Nicht nötig? Am Datensatz abbrechen." />
              <span style={{ marginLeft: 'auto', fontWeight: 700, color: 'var(--warning)' }}>{record.provisionings!.length}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {record.provisionings!.map((d) => (
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
        {/* ── Bedarf: Positionen + Quelle in EINEM Container ────────────────────────
            Eine Position ist EINE Zeile: Artikel · Menge · woher. Dieselbe Zeile für den
            Einzel-Artikel-Auftrag wie für den Mehrpositionen-Auftrag – eine Position
            hinzuzufügen baut das Fenster nicht mehr um, es kommt schlicht eine Zeile dazu. */}
        <SectionTitle>Bedarf</SectionTitle>
        <div style={cardStyle}>
          {demandEditable ? (
            <>
              {isMultiPosition ? (
                orderLines.map((l) => {
                  const line = pinLines.find((p) => p.lineId === l.id);
                  return (
                    <PositionRow key={l.id} line={line} unit={l.article_unit ? unitLabel(l.article_unit) : ''}
                      title={l.article_name ?? `Artikel #${l.article_id}`} articleObjectId={l.article_object_id ?? null}
                      qty={String(l.quantity)} canProduce={false}
                      onRemove={orderLines.length > 1 ? () => removePosition(l.id) : undefined}
                      source={line ? lineSource(line) : 'stock'}
                      onSource={(s) => line && setLineSource(line, s)}
                      onToggle={togglePin} />
                  );
                })
              ) : (
                <PositionRow
                  line={pinLines[0]} unit={qtyUnit} canProduce={canProduce}
                  produceHint="Der Ablauf unten wirkt auf vorhandenen Bestand – für Neuerzeugung diese Schritte entfernen"
                  articleSelect={<SearchSelect label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />}
                  qtyInput={<TextFieldUnit label="Menge" value={form.quantity} onChange={(v) => set('quantity', v)} unit={qtyUnit} required placeholder="z. B. 5" />}
                  qty={form.quantity}
                  source={goal} onSource={(s) => pickGoal(s)} onToggle={togglePin} />
              )}

              {isCreate && releasedArticles.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--warning)', background: 'var(--warning-bg)', borderRadius: 8, padding: '8px 10px' }}>
                  Kein freigegebener Artikel vorhanden – nur freigegebene sind referenzierbar.
                </div>
              )}

              {/* Verkaufte Ware wählen ⇒ der Auftrag wird zur Retoure/Erstattung. */}
              {!isMultiPosition && goal === 'specific' && soldPool.length > 0 && (
                <RefundSubjectPicker sold={soldPool} value={refundIds} onChange={setRefundIds}
                  onConfirm={() => bindRefund(refundIds)} error={error} />
              )}

              {/* Weitere Position: erst möglich, sobald der Auftrag existiert. */}
              {!isCreate && record?.status === 'draft' && (
                <AddPositionRow articles={releasedArticles}
                  excludeArticleIds={isMultiPosition ? orderLines.map((l) => l.article_id) : (record?.article_id != null ? [record.article_id] : [])}
                  onAdd={addPosition} />
              )}

              {/* Termin – eine Zeile, kein eigenes Feld-Raster. */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13, borderTop: '1px solid var(--border-1)', paddingTop: 12 }}>
                <CalendarClock size={15} style={{ color: 'var(--fg-3)', flexShrink: 0 }} />
                <span style={{ color: 'var(--fg-3)' }}>Termin</span>
                {dateOpen ? (
                  <>
                    <input type="date" value={form.desired_delivery_date} min={todayIso()} onChange={(e) => set('desired_delivery_date', e.target.value)}
                      className="px-2 py-1 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-accent focus:border-transparent" style={{ borderColor: 'var(--border-1)' }} />
                    <button type="button" onClick={() => { setDateOpen(false); set('desired_delivery_date', ''); }} style={linkBtn}>schnellstmöglich</button>
                  </>
                ) : (
                  <>
                    <span style={{ fontWeight: 600, color: 'var(--fg-1)' }}>Schnellstmöglich</span>
                    <button type="button" onClick={() => setDateOpen(true)} style={linkBtn}>Datum</button>
                  </>
                )}
              </div>
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

        {/* «Abweichung melden» sitzt jetzt als kleiner Flag-Knopf im Kopf (analog Instanz) –
            keine eigene Karte mehr im Detailfenster. */}

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
            {/* Gleiche Darstellung wie am Artikel: der Editor steht frei, ohne zweite Karte. */}
            <div style={{ marginBottom: 12 }}>
              {/* FIX: suppliers war hier (und an den zwei weiteren Stellen) als [] hartkodiert –
                  ein Beschaffungs-Schritt am Auftrag konnte NIE einen Lieferanten wählen
                  («Keine Lieferanten vorhanden»), obwohl welche existieren. */}
              <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={suppliers}
                selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
            </div>
          </>
        )}

        {/* ── Ablauf ──────────────────────────────────────────────────────────────
            Gleiche Darstellung wie der Prozess-Reiter am Artikel: `ProcessSteps` steht
            frei im Weissraum statt in einer zusätzlichen Karte – es ist derselbe Editor,
            also soll er auch gleich aussehen. */}
        {isStaff && record?.status === 'draft' && !isSubOrder && (isMultiPosition || goal !== 'produce') && (
          <>
            <SectionTitle icon={Workflow} info="Was mit den Positionen geschieht: bewegen, verkaufen, prüfen, verschrotten … Jedes Modul ist frei kombinierbar.">Ablauf</SectionTitle>
            <div style={{ marginBottom: 12 }}>
              <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={suppliers}
                selfArticleObjectId={record.article_object_id ?? null} onStepsCount={onStepsCount} />
            </div>
          </>
        )}

        {/* «Erzeugen» hat keinen eigenen Ablauf – es läuft der Prozess des Artikels. Statt
            das nur zu behaupten, wird er hier **gezeigt**: dieselbe Komponente, dieselben
            Daten, nur lesend (`owner="articles"`). Eine 1:1-Spiegelung, keine Kopie – wer
            ihn ändern will, ändert ihn am Artikel. */}
        {isStaff && record?.status === 'draft' && !isSubOrder && !isMultiPosition
          && goal === 'produce' && record.article_object_id != null && (
          <>
            <SectionTitle icon={Workflow} info="Der am Artikel hinterlegte Prozess – hier nur zur Ansicht. Geändert wird er am Artikel selbst (Reiter «Prozess»).">
              Prozess des Artikels
            </SectionTitle>
            <div style={{ marginBottom: 12 }}>
              <ProcessSteps owner="articles" ownerObjectId={record.article_object_id} suppliers={suppliers}
                selfArticleObjectId={record.article_object_id} readOnly />
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
                onCoverStock={coverFromStock} onOpen={(oid) => nav?.(oid)} />
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

      {dialog === 'deviation' && record && (
        <DeviationDialog busy={deviationBusy} onChoose={reportDeviation} onClose={() => setDialog(null)} />
      )}

      {dialog === 'deactivate' && record && (
        <DeactivateDialog
          mode={dialog}
          title="Auftrag abbrechen"
          /* Ein Unter-Auftrag bekommt NIE einen eigenen Folgeauftrag – sein Subjekt gehört
             ohnehin dem Eltern bzw. er transportiert nur. Er wird direkt inaktiv, und der
             Eltern läuft danach weiter. */
          message={isSubOrder
            ? 'Der Unter-Auftrag wird inaktiv. Die Instanzen gehen an den übergeordneten Auftrag zurück, der danach weiterläuft.'
            : record.status === 'released'
              ? 'Es wird ein Folgeauftrag (Abweichung) mit den im Prozess befindlichen Instanzen angelegt. Du legst dort fest, was mit ihnen geschieht; das Original wird erst inaktiv, wenn der Folgeauftrag freigegeben ist.'
              : 'Der Entwurf wird inaktiv gesetzt.'}
          confirmLabel={record.status === 'released' && !isSubOrder ? 'Folgeauftrag anlegen' : 'Abbrechen'}
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
// ─── Abweichungsauftrag: EIN Vorgang, EINE Entscheidung ──────────────────────────
//
// Früher gab es zwei Knöpfe mit zwei Namen und zwei Dialogen für dieselbe Sache: «Abweichung
// melden» und «Abbrechen» – letzteres legte ebenfalls einen Abweichungsauftrag an. Jetzt gibt
// es einen Knopf, ein Wort und ein Symbol; der Unterschied ist eine Eigenschaft des Vorgangs:
// läuft der Ursprungsauftrag danach weiter, oder ist er abgebrochen?
function DeviationDialog({ busy, onChoose, onClose }: {
  busy: boolean;
  onChoose: (abortParent: boolean) => void;
  onClose: () => void;
}) {
  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()}
        style={{ background: '#fff', borderRadius: 'var(--r-lg)', width: 'min(520px, 100%)', boxShadow: 'var(--shadow-md)', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', borderBottom: '1px solid var(--border-1)' }}>
          <AlertTriangle size={18} style={{ color: 'var(--warning)' }} />
          <span style={{ font: '800 15px var(--font-display)', color: 'var(--fg-1)', flex: 1 }}>Abweichungsauftrag anlegen</span>
          <button onClick={onClose} aria-label="Schliessen"
            style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--fg-4)', display: 'flex' }}>
            <X size={18} />
          </button>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-3)' }}>
            Es entsteht ein Abweichungsauftrag auf die Instanzen dieses Auftrags. Dort legst du
            fest, was mit ihnen geschieht (nacharbeiten, ersetzen, verschrotten, sperren).
          </p>
          <ChoiceButton
            disabled={busy} onClick={() => onChoose(false)}
            title="Auftrag läuft weiter"
            text="Der Auftrag pausiert, bis die Abweichung geklärt ist – danach läuft er normal weiter."
          />
          <ChoiceButton
            disabled={busy} onClick={() => onChoose(true)} danger
            title="Auftrag abbrechen"
            text="Der Auftrag ist sofort abgebrochen – endgültig, keine Reaktivierung. Nur der Abweichungsauftrag läuft weiter."
          />
        </div>
      </div>
    </div>
  );
}

function ChoiceButton({ title, text, danger, disabled, onClick }: {
  title: string; text: string; danger?: boolean; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick}
      style={{
        textAlign: 'left', padding: '12px 14px', borderRadius: 'var(--r-md)', cursor: disabled ? 'default' : 'pointer',
        border: `1px solid ${danger ? 'var(--danger)' : 'var(--border-1)'}`, background: '#fff', opacity: disabled ? .6 : 1,
      }}>
      <div style={{ font: '700 13.5px var(--font-body)', color: danger ? 'var(--danger)' : 'var(--fg-1)' }}>{title}</div>
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{text}</div>
    </button>
  );
}

// Bedarf (Ressource) wird ausschliesslich über Nachschub gedeckt.
const SUBJECT_STEP_TYPES = ['movement', 'inspection', 'scrap', 'block', 'sale'];

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

  // ── Angehalten, weil Material noch unterwegs ist (nur der betroffene Schritt) ───
  // Anderer Grund als Unterdeckung: das Material EXISTIERT, es liegt bloss noch nicht hier.
  // Es gibt nichts zu beschaffen – die Bereitstellung bringt es, dann läuft es weiter.
  const staging = step?.provisioning_order_object_ids ?? [];
  if (staging.length > 0) {
    return (
      <HoldFrame title="Prozess angehalten – Material unterwegs">
        <div style={{ fontSize: 12, color: '#92400e', lineHeight: 1.5 }}>
          Das benötigte Material ist vorhanden, liegt aber noch nicht am richtigen Ort. Es wird
          gerade bereitgestellt – sobald es da ist, läuft dieser Schritt automatisch weiter.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {staging.map((oid) => (
            <button key={oid} type="button" onClick={() => onOpen?.(oid)}
              style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#0f172a', background: '#fff', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 12px', cursor: 'pointer', textAlign: 'left' }}>
              <Truck size={14} style={{ color: '#b45309', flexShrink: 0 }} />
              <span>Bereitstellung <ObjId value={oid} /> öffnen</span>
            </button>
          ))}
        </div>
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
  if (step.step_type === 'scrap' || step.step_type === 'block') {
    // EIN Panel, zwei Wirkungen – die Auswahl ist identisch, nur das Ergebnis nicht.
    return <ScrapPanel order={stepOrder} stepState={stepState} stepId={stepId}
      mode={step.step_type === 'block' ? 'block' : 'scrap'} onOrderUpdated={onSaved} />;
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
      {/* Mengen sind Zahlen: Buchstaben kommen gar nicht erst ins Feld (numericOnly). */}
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(numericOnly(e.target.value))}
        {...numericInputProps}
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
        style={{ borderColor: 'var(--border-1)' }}
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
  fontSize: 12, color: 'var(--accent)', cursor: 'pointer', fontWeight: 600,
};

/**
 * **Eine Position = eine Zeile.** Artikel · Menge · woher – und darunter, nur wenn nötig,
 * die Instanz-Auswahl. Ersetzt die früheren drei grossen Ziel-Karten PLUS den separaten
 * Segment-Umschalter der Mehrpositionen-Ansicht: beide Fälle sehen jetzt gleich aus, eine
 * Position hinzuzufügen baut das Fenster nicht mehr um.
 *
 * Wortwahl bewusst allgemein: **Erzeugen** (statt «Herstellen/Beschaffen» – der Prozess
 * entscheidet, ob produziert oder eingekauft wird), **Ab Lager**, **Auswählen**.
 */
function PositionRow({
  line, unit, title, articleObjectId, qty, source, onSource, onToggle, onRemove,
  canProduce, produceHint, articleSelect, qtyInput,
}: {
  line?: PinLine;
  unit: string;
  title?: string;
  articleObjectId?: number | null;
  qty: string;
  source: OrderGoal;
  onSource: (s: OrderGoal) => void;
  onToggle: (line: PinLine, oid: number) => void;
  onRemove?: () => void;
  canProduce: boolean;
  produceHint?: string;
  /** Anker-Position (Einzel-Artikel): Artikel/Menge sind hier noch editierbar. */
  articleSelect?: React.ReactNode;
  qtyInput?: React.ReactNode;
}) {
  const avail = line?.availableQty ?? 0;
  const req = line?.reqQty ?? (Number(qty) || 0);
  const enough = avail >= req && req > 0;
  const pinned = line?.pinnedQty ?? 0;

  // Ergebniszeile: EIN Satz, was die Freigabe bewirkt – statt eines Info-Banners.
  const outcome = source === 'produce'
    ? { text: `${req || ''} ${unit} werden neu erzeugt`.trim(), warn: null as string | null }
    : source === 'stock'
      ? { text: `${req || ''} ${unit} ab Lager, älteste zuerst`.trim(),
          warn: req > avail ? `nur ${avail} ${unit} da – Rest per Nachschub` : null }
      : { text: `${pinned}/${req} ${unit} gewählt`,
          warn: pinned < req ? 'Auswahl unvollständig' : null };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 4 }}>
      {/* Kopfzeile: Artikel + Menge (+ entfernen) */}
      {articleSelect ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 12 }}>
          {articleSelect}
          {qtyInput}
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {articleObjectId != null && <ObjId value={articleObjectId} />}
          <span style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 600, color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>{qty} {unit}</span>
          {onRemove && (
            <button type="button" onClick={onRemove} data-tip="Position entfernen" aria-label="Position entfernen"
              style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 2, flexShrink: 0 }}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      )}

      {/* Quelle: EIN Schieber mit drei Feldern. Gesperrtes nennt im Hover den Grund. */}
      {line && (
        <>
          <SourceSwitch
            value={source} onChange={onSource}
            options={[
              { value: 'produce', icon: Factory, label: 'Erzeugen', disabled: !canProduce,
                hint: canProduce ? 'Neu herstellen oder beschaffen – der Artikel-Prozess läuft' : (produceHint ?? 'Bei mehreren Positionen nicht möglich – dafür je Artikel einen eigenen Auftrag') },
              { value: 'stock', icon: Warehouse, label: 'Ab Lager', disabled: !enough,
                hint: enough ? 'Vorhandenes verwenden – automatisch die ältesten (FIFO)' : `Nur ${avail} ${unit} am Lager (${req} nötig)` },
              { value: 'specific', icon: Target, label: 'Auswählen',
                hint: 'Genau bestimmen, welche Instanzen – auch verkaufte (→ Retoure)' },
            ]}
          />

          {source === 'specific' && <PinPicker line={line} onToggle={onToggle} bare />}

          {/* Ergebnis in einer Zeile – kein Banner, kein Absatz. */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)' }}>
            <CheckCircle2 size={13} style={{ color: outcome.warn ? 'var(--warning)' : 'var(--success)', flexShrink: 0 }} />
            <span>{outcome.text}</span>
            {outcome.warn && <span style={{ color: 'var(--warning)', fontWeight: 600 }}>· {outcome.warn}</span>}
          </div>
        </>
      )}
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
      <div style={{ fontSize: 12, color: 'var(--fg-3)', lineHeight: 1.5 }}>
        Wähle die <strong style={{ color: 'var(--fg-1)' }}>verkauften Instanzen</strong>, die erstattet
        werden. Danach definierst du wie gewohnt den Ablauf – in aller Regel <strong>Bewegung</strong>{' '}
        (Ware zurück ins Lager) + <strong>Rückerstattung</strong> (Geld zurück).
      </div>
      {sold.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine verkauften Instanzen dieses Artikels.</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {sold.map((i) => {
            const sel = value.includes(i.object_id!);
            return (
              <button key={i.object_id} type="button" onClick={() => toggle(i.object_id!)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                  padding: '4px 10px', borderRadius: 999, cursor: 'pointer',
                  border: `1px solid ${sel ? 'var(--danger)' : 'var(--border-1)'}`,
                  background: sel ? 'var(--danger-bg)' : '#fff', color: sel ? 'var(--danger)' : 'var(--fg-3)',
                }}>
                {sel && <CheckCircle2 size={12} />}{fmtObjId(i.object_id)}
              </button>
            );
          })}
        </div>
      )}
      {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      <PrimaryButton icon={Undo2} onClick={confirm} disabled={busy || value.length === 0}>
        {busy ? 'Wird übernommen…' : `Als Retoure übernehmen (${value.length})`}
      </PrimaryButton>
    </div>
  );
}

/**
 * **Schieber** für die Quelle (Erzeugen · Ab Lager · Auswählen): EIN Gleis, ein Reiter,
 * der zur gewählten Option gleitet. Drei gleich aussehende Knöpfe liessen offen, dass sie
 * einander ausschliessen – ein wandernder Reiter zeigt es ohne ein Wort Erklärung.
 *
 * Gesperrte Felder bleiben sichtbar (die Wahl existiert ja) und nennen den Grund im
 * **Hover** statt in der Fläche.
 */
function SourceSwitch({ value, onChange, options }: {
  value: OrderGoal;
  onChange: (v: OrderGoal) => void;
  options: { value: OrderGoal; icon: React.ElementType; label: string; hint: string; disabled?: boolean }[];
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  const width = 100 / options.length;
  return (
    <div style={{
      position: 'relative', display: 'flex', padding: 3, borderRadius: 999,
      background: 'var(--bg-2)', border: '1px solid var(--border-1)',
    }}>
      {/* Der gleitende Reiter – reine Anzeige, liegt unter den Beschriftungen. */}
      <span aria-hidden style={{
        position: 'absolute', top: 3, bottom: 3, left: 3, width: `calc(${width}% - 2px)`,
        transform: `translateX(${index * 100}%)`, transition: 'transform .18s cubic-bezier(.4,0,.2,1)',
        borderRadius: 999, background: '#fff', boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,.12))',
      }} />
      {options.map((o) => {
        const active = o.value === value;
        const Icon = o.icon;
        return (
          <button key={o.value} type="button" role="tab" aria-selected={active}
            onClick={o.disabled ? undefined : () => onChange(o.value)} disabled={o.disabled}
            data-tip={o.hint} title={o.hint}
            style={{
              position: 'relative', flex: 1, display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', gap: 6, padding: '7px 10px', border: 'none',
              background: 'none', borderRadius: 999, font: '600 12px var(--font-body)',
              cursor: o.disabled ? 'not-allowed' : 'pointer', opacity: o.disabled ? 0.4 : 1,
              color: active ? 'var(--accent-ink)' : 'var(--fg-3)', transition: 'color .18s',
            }}>
            <Icon size={14} /> {o.label}
          </button>
        );
      })}
    </div>
  );
}

// Instanz-Auswahl (Chips) für EINE Position – geteilt von Einzel-Artikel- und
// Mehrpositionen-Auftrag (dieselbe Optik). ``bare`` lässt den äusseren Karten-Rahmen weg
// (die Position bringt ihn schon mit).
function PinPicker({ line, onToggle, bare }: {
  line: PinLine; onToggle: (line: PinLine, oid: number) => void; bare?: boolean;
}) {
  // Suche nach Instanznummer: bei ein paar Instanzen sucht das Auge, bei ein paar hundert
  // nicht mehr. Das Feld erscheint darum erst, wenn die Liste es rechtfertigt.
  const [q, setQ] = useState('');
  const SEARCH_FROM = 8;
  const needle = q.trim().replace(/\D/g, '');
  const pool = needle
    ? line.pool.filter((i) => String(i.object_id ?? '').includes(needle))
    : line.pool;

  const body = (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {line.pool.length >= SEARCH_FROM && (
          <div style={{ position: 'relative', flex: 1, minWidth: 150 }}>
            <input value={q} onChange={(e) => setQ(numericOnly(e.target.value, { decimals: false }))}
              placeholder="Instanznummer suchen…" {...numericInputProps}
              className="w-full rounded-md border bg-white px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
              style={{ borderColor: 'var(--border-1)', paddingRight: 26 }} />
            <Search size={13} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-4)', pointerEvents: 'none' }} />
          </div>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 700, color: line.pinnedQty === line.reqQty ? 'var(--success)' : 'var(--warning)' }}>
          {line.pinnedQty} / {line.reqQty} {line.unit} gewählt
        </span>
      </div>
      {line.pool.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine verfügbaren Instanzen.</div>
      ) : pool.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine Instanz mit «{q}».</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 168, overflowY: 'auto' }}>
          {pool.map((i) => {
            const sel = line.pinnedIds.includes(i.object_id!);
            const atLimit = !sel && line.pinnedQty + (i.quantity ?? 1) > line.reqQty;
            return (
              <button key={i.object_id} type="button" disabled={atLimit}
                onClick={() => onToggle(line, i.object_id!)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                  padding: '4px 10px', borderRadius: 999, cursor: atLimit ? 'not-allowed' : 'pointer',
                  border: `1px solid ${sel ? 'var(--accent)' : 'var(--border-1)'}`,
                  background: sel ? 'var(--accent-soft)' : '#fff', color: sel ? 'var(--accent-ink)' : 'var(--fg-3)',
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 160px), 1fr))', gap: 8 }}>
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

const recInput = "w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-accent focus:border-transparent";

/**
 * **Wiederkehrend** direkt am Auftrag: bei Abschluss entsteht automatisch der nächste
 * (Entwurf), Termin = Termin + Periode.
 *
 * Kein Häkchen und kein Speichern-Knopf mehr – die Angabe IST der Schalter: steht eine
 * Periode, wiederholt sich der Auftrag; ist das Feld leer, eben nicht. Ein Häkchen neben
 * einem Periodenfeld kann nur widersprüchlich sein («angehakt, aber keine Periode» /
 * «Periode, aber nicht angehakt`) – diesen Zustand gibt es jetzt nicht mehr. Gespeichert
 * wird per Auto-Save wie überall sonst; der aktuelle Stand steht als **Satz** darunter,
 * nicht als Schalterstellung, die man interpretieren muss.
 */
function RecurrenceCard({ order, onSaved, version }: {
  order: Order; onSaved: (o: Order) => void; version: MutableRefObject<string | null>;
}) {
  // Leer = nicht wiederkehrend. Darum KEIN Default-Wert, wenn nichts eingestellt ist.
  const [interval, setIntervalDays] = useState(
    order.recurrence_active && order.recurrence_interval_days ? String(order.recurrence_interval_days) : '');
  const [lead, setLead] = useState(
    order.recurrence_active && order.recurrence_lead_time_days != null ? String(order.recurrence_lead_time_days) : '');
  const [anchor, setAnchor] = useState(order.recurrence_anchor ?? '');
  const [err, setErr] = useState<string | null>(null);
  const [flash, setFlash] = useState(false);
  const [open, setOpen] = useState(!!order.recurrence_active);

  const days = Math.trunc(Number(interval) || 0);
  const active = days > 0;

  const sig = JSON.stringify({ interval, lead, anchor });
  const [savedSig, setSavedSig] = useState(sig);

  const save = useCallback(async () => {
    setErr(null);
    try {
      // Optimistic Locking: ohne expected_updated_at lief der nächste Autosave (z. B.
      // Liefertermin) in einen unerklärlichen 409.
      const o = await api.updateOrder(order.object_id as number, {
        recurrence_active: active,
        recurrence_interval_days: active ? days : null,
        recurrence_lead_time_days: active ? Math.max(0, Math.trunc(Number(lead) || 0)) : 0,
        recurrence_anchor: active && anchor ? anchor : null,
        expected_updated_at: version.current,
      });
      version.current = o.updated_at;
      onSaved(o);
      setSavedSig(sig);
      setFlash(true); setTimeout(() => setFlash(false), 700);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
  }, [order.object_id, active, days, lead, anchor, sig, onSaved, version]);

  const flush = useAutosave(sig, sig !== savedSig, save);

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start', margin: '0 2px 12px',
        border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', fontSize: 12, fontWeight: 600,
      }}>
        <Repeat size={13} />
        {active ? `Wiederkehrend · alle ${days} Tage` : 'Wiederkehrend einrichten'}
        {active && <span aria-hidden style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--success)' }} />}
        <ChevronDown size={13} />
      </button>
    );
  }

  return (
    <>
      <button onClick={() => setOpen(false)} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px', border: 'none', background: 'none', cursor: 'pointer' }}>
        <Repeat size={13} style={{ color: 'var(--fg-4)' }} />
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--fg-3)' }}>Wiederkehrend</span>
        <ChevronDown size={13} style={{ color: 'var(--fg-4)', transform: 'rotate(180deg)' }} />
      </button>
      <div style={{ ...cardStyle, boxShadow: flash ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow .2s' }}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 14 }}>
          <div>
            <Label>Periode (Tage)</Label>
            <input value={interval} onChange={(e) => setIntervalDays(numericOnly(e.target.value, { decimals: false }))}
              {...numericInputProps} className={recInput} style={{ borderColor: 'var(--border-1)' }} placeholder="leer = einmalig" />
          </div>
          <div>
            <Label>Vorlaufzeit (Tage)</Label>
            <input value={lead} onChange={(e) => setLead(numericOnly(e.target.value, { decimals: false }))}
              disabled={!active} {...numericInputProps} className={recInput}
              style={{ borderColor: 'var(--border-1)', opacity: active ? 1 : 0.5 }} placeholder="z. B. 30" />
          </div>
          <div>
            <Label>Nächster Termin</Label>
            <input type="date" value={anchor} onChange={(e) => setAnchor(e.target.value)} disabled={!active}
              className={recInput} style={{ borderColor: 'var(--border-1)', opacity: active ? 1 : 0.5 }} />
          </div>
        </div>
        {/* Dezent statt erklärend: EIN Punkt plus zwei Wörter. Ist nichts eingestellt,
            sagt das leere Feld bereits alles – dann steht hier gar nichts. */}
        {active && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--fg-3)' }}>
            <span aria-hidden style={{ width: 7, height: 7, borderRadius: 999, flexShrink: 0, background: 'var(--success)' }} />
            Aktiv · alle {days} Tage
          </div>
        )}
        {err && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{err}</span>}
      </div>
    </>
  );
}
