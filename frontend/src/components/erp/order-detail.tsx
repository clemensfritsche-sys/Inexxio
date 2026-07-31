'use client';

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { Ban, X, History as HistoryIcon, ClipboardList, ArrowLeft, Workflow, MapPin, CheckCircle2, Loader2, Repeat, ChevronDown, Factory, Warehouse, Target, AlertTriangle, PauseCircle, PackagePlus, Plus, Trash2, Undo2, FolderOpen, CalendarClock, Search, Building2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderDeviationInfo, OrderPurchase, OrderStep, OrderUpdateInput, UserProfile } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { unitLabel } from '@/lib/article';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import type { StatusAction } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { printObjectLabel } from '@/components/scan/object-label';
import { QrCode } from 'lucide-react';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { ChoiceButton, DH, DetailHeader, HeaderAction, HeaderSep, Label, PrimaryButton, ReadField, Row, SPEC, SaveIndicator, SearchSelect, SectionTitle, StatusBadge, StatusFlow, numericOnly, numericInputProps } from '@/components/erp/fields';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { OrderFlow } from '@/components/erp/order-flow';
import { PurchaseStepPanel } from '@/components/erp/purchase-step-panel';
import { OrderPositions } from '@/components/erp/order-positions';
import { orderName } from '@/lib/record-name';
import { InspectionPanel } from '@/components/erp/inspection-panel';
import { MovementPanel } from '@/components/erp/movement-panel';
import { ResourcePanel } from '@/components/erp/resource-panel';
import { ScrapPanel } from '@/components/erp/scrap-panel';
import { SalePanel } from '@/components/erp/sale-panel';
import { DocumentPanel } from '@/components/erp/document-panel';
import { ProcessSteps } from '@/components/erp/process-steps';
import { ShortfallDialog, type ShortfallAnswer } from '@/components/erp/shortfall-dialog';
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
  /** Menge über den GANZEN wählbaren Pool (frei + gebunden) – Grundlage für «Auswählen». */
  poolQty: number;
  // Frei verfügbar? Eine **gebundene** Instanz ist wählbar – daraus wird ein Abweichungsauftrag.
  free: (i: Instance) => boolean;
  /** Sorte je Instanz: frei · gebunden (→ Abweichung) · verkauft (→ Retoure). */
  kind: (i: Instance) => PinKind;
  /** Beanspruchte Menge je gewählter Instanz-Objektnummer (Teilmenge einer Charge, #361). */
  wanted: Record<number, number>;
};

/** Die drei Sorten, die eine Instanz-Auswahl haben kann – sie bestimmen die Art des Auftrags. */
type PinKind = 'free' | 'bound' | 'sold';

// Farbe + Erklärung je Sorte: EINE Tabelle statt verstreuter Bedingungen im Chip.
const PIN_KIND: Record<PinKind, { tone: string; bg: string; hint: string; mix: string }> = {
  free: { tone: 'var(--success)', bg: 'var(--success-bg)',
    hint: 'Frei am Lager', mix: 'Es ist bereits eine freie Instanz gewählt' },
  bound: { tone: 'var(--warning)', bg: 'var(--warning-bg)',
    hint: 'In Arbeit, reserviert oder gesperrt – daraus wird ein Abweichungsauftrag',
    mix: 'Es ist bereits eine gebundene Instanz gewählt (Abweichung)' },
  sold: { tone: 'var(--accent)', bg: 'var(--accent-soft)',
    hint: 'Verkauft – daraus wird eine Retoure/Erstattung',
    mix: 'Es sind bereits verkaufte Instanzen gewählt (Retoure)' },
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
// Ein Auftrag hat nur noch EINE Status-Aktion: freigeben. Das frühere «Abbrechen» war ein
// zweiter Name und ein zweites UI für dieselbe Sache (es legte ja einen Abweichungsauftrag an)
// – dafür gibt es den Flag-Knopf «Abweichungsauftrag» im Kopf, wo man entscheidet, ob der
// Auftrag weiterläuft oder abgebrochen ist.
//
// Und es gibt **kein «Verwerfen»**: ein Unter-Auftrag ist eine bewusste Entscheidung (bzw. eine
// physische Notwendigkeit) und wird durchgezogen, nicht weggeworfen. Die einzige Ausnahme ist
// die **Bereitstellung** – sie legt das System selbst an, also braucht sie einen Ausstieg; der
// heisst «Bereitstellung übergehen» und sagt damit, was man entscheidet.
function orderActions(status: string, canRelease: boolean, releaseHint?: string): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
      hint: canRelease ? undefined : releaseHint }];
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
  const [dialog, setDialog] = useState<'skip-provisioning' | null>(null);
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
  // **Der Bedarf eines ENTWURFS ist bearbeitbar – bei jedem Auftrag** (Notiz #355). Ein
  // Unter-Auftrag ist kein Sonderfall: der Abkürzungs-Knopf an der Instanz nimmt einem nur
  // die erste Auswahl ab, er soll sie nicht festnageln. Wer eine zweite betroffene Instanz
  // oder eine weitere Position braucht, ergänzt sie hier wie überall. Nach der Freigabe ist
  // der Bedarf read-only, ebenfalls wie überall.
  const demandEditable = isStaff && (isCreate || record?.status === 'draft');
  const isCompleted = record?.status === 'completed';
  const hasPurchase = !!record?.purchase;
  // **Kein «Abbrechen»-Knopf mehr im Kopf** (Notiz #366): einen Auftrag abzubrechen heisst,
  // seine Teile in einen anderen zu überführen – und genau das tut man, indem man einen
  // Auftrag anlegt und dessen Instanzen auswählt. Der Eltern meldet dann eine Unterdeckung,
  // und bleibt ihm nichts übrig, IST «Auftragsmenge reduzieren» sein Abbruch. Ein Vorgang,
  // eine Frage, kein zweiter Weg. Ein Fehler an EINEM Stück wird ohnehin an der Instanz
  // gemeldet (dort steht die Abkürzung).
  // Nur die **Bereitstellung** ist übergehbar: sie ist die einzige Unter-Auftragsart, die das
  // System selbst anlegt. Alles andere ist eine bewusste Entscheidung und wird durchgezogen.
  const canSkipProvisioning = isStaff && !isCreate && record != null
    && record.reason === 'provisioning' && (record.status === 'draft' || record.status === 'released');

  // Auftrag-Prozess (mehrere Schritte, Mehr-Operationen-Routing) – Schlüssel ist die
  // Schritt-id, damit mehrere gleichartige Schritte unabhängig bedienbar sind.
  const steps = (record?.steps ?? []) as OrderStep[];
  const showProcess = isStaff && !!record && record.status !== 'draft' && steps.length > 0;
  const activeStepId = steps.find((s) => s.state === 'active')?.id
    ?? steps.find((s) => s.state === 'failed')?.id
    ?? steps.find((s) => s.state === 'blocked')?.id   // wartet auf Material → surface
    ?? steps[steps.length - 1]?.id ?? null;
  const currentStepId = selStep ?? (activeStepId != null ? String(activeStepId) : null);
  const currentStep = steps.find((s) => String(s.id) === currentStepId) ?? null;
  // ── Was dem Auftrag fehlt ────────────────────────────────────────────────────────
  // Die Fehlmenge gehört dem **Auftrag**, nicht einem Schritt – darum steht sie einmal.
  // «Wartet» ist ein Zustand: bindet ein Unter-Auftrag die Menge bereits (Abweichung/
  // Nachschub/Bereitstellung), ist die Entscheidung getroffen – dann steht die Angabe bei
  // diesem Unter-Auftrag im Fluss (Notiz #354), und es wird nicht erneut gefragt.
  const shortfall = record?.shortfall ?? [];
  const waitingFor = record?.waiting_for ?? [];
  const missingText = shortfall
    .map((sf) => `${sf.quantity}× ${sf.article_name ?? 'Artikel'}`).join(' · ') || undefined;
  const needsDecision = shortfall.length > 0 && waitingFor.length === 0;
  // «Auftragsmenge reduzieren» gibt es nur für die **Fertigware**: einen fehlenden
  // Komponenten-Bedarf kann man nicht wegbestätigen – ohne Material wird nichts gebaut.
  const hasSubjectShortfall = shortfall.some((sf) => (sf.kind ?? 'subject') === 'subject');
  const shortfallCandidates = shortfall.flatMap((sf) => sf.available_instances ?? []);

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
    // Auch ein Unter-Auftrag im Entwurf braucht den Pool – seine Auswahl ist erweiterbar (#355).
    if (!isDraftStaff) { setPinPool([]); return; }
    api.getInstances(500).then(setPinPool).catch(() => {});
  }, [isDraftStaff]);

  // Frei verfügbar = freigegeben, am Lager und nicht für einen FREMDEN Auftrag reserviert.
  // Alles andere ist «gebunden» – wählbar, aber nur als Abweichung (siehe ``buildPinLine``).
  const isFree = (i: Instance) =>
    i.quality === 'passed' && i.disposition === 'in_stock' &&
    (i.reserved_for_order_object_id == null || i.reserved_for_order_object_id === record?.object_id);
  // **Drei Sorten, eine Auswahl** (Notiz #360) – und die Sorte bestimmt die Art des
  // Auftrags (`classify_pick`): frei → gewöhnlicher Bedarf · gebunden → Abweichung ·
  // verkauft → Retoure. Gemischt wird nie: das Backend weist es ab, die Oberfläche sperrt
  // die jeweils andere Sorte, sobald die erste gewählt ist.
  const kindOf = (i: Instance): PinKind =>
    i.disposition === 'sold' ? 'sold' : isFree(i) ? 'free' : 'bound';

  // Was der Auftrag beansprucht – je Artikel die Instanzen UND die **beanspruchte Menge**.
  // Bei einer Teilmenge einer Charge liefert der Server sie als ``move_quantity`` (die für
  // diesen Auftrag reservierte Menge); sonst ist es die ganze Instanz (#361).
  const pinnedByArticle = new Map<number, { ids: number[]; qty: number; wanted: Record<number, number> }>();
  for (const i of record?.instances ?? []) {
    if (i.object_id == null) continue;
    const cur = pinnedByArticle.get(i.article_id) ?? { ids: [], qty: 0, wanted: {} };
    const share = i.move_quantity ?? i.quantity ?? 0;
    cur.ids.push(i.object_id);
    cur.qty += share;
    cur.wanted[i.object_id] = share;
    pinnedByArticle.set(i.article_id, cur);
  }
  function buildPinLine(lineId: number | null, articleId: number, unit: string, reqQty: number): PinLine {
    // **Jede noch existierende Instanz ist wählbar** – frei ODER gebunden (in Arbeit,
    // reserviert, gesperrt). Wer eine gebundene wählt, legt damit einen **Abweichungs-
    // auftrag** an: das Tag ist die Folge der Auswahl, kein zweiter Schalter (das Backend
    // leitet es über ``subject.classify_pick`` ab).
    // **Verschrottet ist raus, alles andere ist drin** (Notiz #360): frei (grün), gebunden
    // (gelb: in Arbeit / reserviert / gesperrt) UND **verkauft**. Für eine Rücksendung muss
    // man ebenso genau sagen, WELCHES Stück zurückkommt – FIFO ergäbe dort keinen Sinn. Die
    // Art des Auftrags folgt daraus (``classify_pick``): verkauft → Retoure · gebunden →
    // Abweichung · frei → gewöhnlicher Bedarf. Verschrottet ist die eine rote Ausnahme:
    // daran ist nichts mehr zu tun.
    const pool = pinPool.filter((i) =>
      i.object_id != null && i.article_id === articleId && i.disposition !== 'scrapped');
    const pinned = pinnedByArticle.get(articleId) ?? { ids: [], qty: 0, wanted: {} };
    return {
      key: lineId != null ? `line-${lineId}` : 'anchor', lineId, articleId, unit, reqQty,
      pinnedIds: pinned.ids, pinnedQty: pinned.qty, pool, kind: kindOf, wanted: pinned.wanted,
      // «Genug Bestand?» meint das FREI Verfügbare – gebundene Stück zählen dafür nicht.
      availableQty: pool.filter(isFree).reduce((s, i) => s + (i.quantity ?? 0), 0), free: isFree,
      // Was sich überhaupt auswählen liesse – frei UND gebunden. Reicht das nicht für die
      // Menge, ist «Auswählen» eine Sackgasse: die Auswahl liesse sich nie vervollständigen
      // und die Freigabe bliebe gesperrt (Notiz #356).
      poolQty: pool.reduce((s, i) => s + (i.quantity ?? 0), 0),
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
  function togglePin(line: PinLine, oid: number, qty: number, qtyOnly?: boolean) {
    const has = line.pinnedIds.includes(oid);
    const ids = qtyOnly ? line.pinnedIds : has ? line.pinnedIds.filter((x) => x !== oid) : [...line.pinnedIds, oid];
    // Die beanspruchten Mengen wandern mit: was abgewählt wird, verliert seine Menge.
    const wanted: Record<string, number> = {};
    for (const id of ids) wanted[String(id)] = id === oid ? qty : (line.wanted[id] ?? 0);
    setLinePins(line, ids, undefined, wanted);
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

  // Greift die Auswahl auf Instanzen zu, die ein LAUFENDER Auftrag in der Hand hat, will
  // dessen Unterdeckung beantwortet sein, bevor die Abweichung steht. Das Backend fragt
  // danach (409); hier steht die Frage, bis sie beantwortet ist.
  const [pendingPick, setPendingPick] = useState<
    { line: PinLine; ids: number[]; text: string; quantities?: Record<string, number> } | null>(null);

  async function setLinePins(line: PinLine, ids: number[], answer?: ShortfallAnswer,
                             quantities?: Record<string, number>) {
    if (!record) return;
    try {
      const saved = line.lineId != null
        ? await api.setOrderLinePins(record.object_id as number, line.lineId,
            { instance_object_ids: ids, instance_quantities: quantities })
        : await api.updateOrder(record.object_id as number, {
            instance_object_ids: ids, instance_quantities: quantities,
            shortfall_response: answer, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      setPendingPick(null);
      onSaved(saved);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Fehler beim Festlegen der Instanzen';
      // Der Server nennt die betroffenen Aufträge – die Frage stellen statt sie wegzuwerfen.
      if (msg.includes('in Arbeit') && msg.includes('warten')) setPendingPick({ line, ids, text: msg, quantities });
      else setError(msg);
    }
  }

  async function addPosition(articleId: number, quantity: number) {
    if (!record) return;
    const saved = await api.addOrderLine(record.object_id as number, { article_id: articleId, quantity });
    verRef.current = saved.updated_at;
    onSaved(saved);
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

  function onStatusAction(target: string) {
    changeStatus(target);
  }

  // «Bereitstellung übergehen»: die einzige Unter-Auftragsart, die das System selbst anlegt,
  // braucht einen Ausstieg. Danach wird sie für diesen Schritt NICHT neu angelegt – die
  // Entscheidung hält (und steht im Audit-Log).
  async function confirmSkipProvisioning() {
    if (!record) return;
    onSaved(await api.abortOrder(record.object_id as number));
    setDialog(null);
  }



  // **Unterdeckung am laufenden Auftrag: EINE Frage, drei Antworten** – dieselben, die auch
  // beim Auswählen gebundener Instanzen gestellt werden (``ShortfallDialog``).
  //
  //   pausieren  – nichts tun: der Prozess ruht, bis die Menge wieder da ist
  //   ersetzen   – freier Lagerbestand (FIFO oder gezielt), Rest per Nachschub
  //   reduzieren – der Auftrag wird mit dem fertig, was gesichert ist
  async function answerShortfall(answer: ShortfallAnswer, instanceObjectIds?: number[]) {
    if (!record || answer === 'wait') return;   // «pausieren» = nichts tun, das IST die Pause
    const replace = answer === 'replace';
    (replace ? setRecoverBusy : setSupplyBusy)(true);
    setError(null);
    try {
      onSaved(replace
        ? await api.coverShortfall(record.object_id as number, instanceObjectIds)
        : await api.confirmQuantity(record.object_id as number));
    } catch (e) {
      setError(e instanceof Error ? e.message : (replace ? 'Ersetzen fehlgeschlagen' : 'Menge konnte nicht angepasst werden'));
    } finally {
      (replace ? setRecoverBusy : setSupplyBusy)(false);
    }
  }


  const articleOptions = [
    { value: '', label: '— Artikel wählen —' },
    ...releasedArticles.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` })),
  ];
  const statusActions = isCreate || !record ? [] : orderActions(record.status, canRelease, releaseHint);
  const companyAddr = company ? [company.street, company.street_number].filter(Boolean).join(' ') : '';

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242). */}
      <DetailHeader
        icon={ClipboardList} iconBg="#EAF0F4" iconFg="#4A6572"
        eyebrow={!isCreate && record.reason === 'deviation' ? 'Abweichungsauftrag' : 'Auftrag'}
        title={isCreate ? null : orderName(record)} placeholder={isCreate ? 'Neuer Auftrag' : 'Auftrag'}
        objectId={isCreate ? null : record.object_id}
        objectIdText={isCreate ? 'wird vergeben' : undefined}
        onBack={onBack}
        avatar={
          <div style={{ ...DH.ico, background: '#EAF0F4', color: '#4A6572', position: 'relative' }}>
            <ClipboardList size={26} />
            {!isCreate && record.reason === 'deviation' && (
              <span title="Abweichungsauftrag" style={{ position: 'absolute', bottom: -3, right: -3, width: 18, height: 18, borderRadius: 999, background: 'var(--warning-bg)', border: '1px solid var(--warning)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <AlertTriangle size={11} style={{ color: 'var(--warning)' }} />
              </span>
            )}
          </div>
        }
        status={isCreate
          ? orderStatusConfig('draft')
          : orderStatusConfig(record.status, record.abort_into_id != null)}
        right={<>
          {demandEditable && <SaveIndicator saving={saving} flash={flash} />}
          {/* Anlage abbrechen – eine Aktion, also bei den Aktionen (früher im Footer). */}
          {isCreate && (
            <button type="button" onClick={onCancel} className="erp-actbtn erp-actbtn-neutral"
              style={{ height: 32, padding: '0 13px', fontSize: 12.5 }}>
              Abbrechen
            </button>
          )}
        </>}
        actions={!isCreate && record.object_id != null ? (
          <>
            <HeaderSep />
            <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
              onClick={() => printObjectLabel(record.object_id as number, record.article_name ?? 'Auftrag', 'Auftrag')}>
              <QrCode size={15} />
            </button>
            {/* Status-Aktion («Freigeben») bei den übrigen Objekt-Aktionen statt rechts
                am Status: eine Aktion gehört zu den Aktionen, der Status zeigt nur an. */}
            {isStaff && !isCompleted && statusActions.length > 0 && (
              <>
                <HeaderSep />
                {statusActions.map((a) => (
                  <HeaderAction key={a.target} label={a.label} tone={a.tone} hint={a.hint}
                    disabled={statusBusy || a.disabled} onClick={() => onStatusAction(a.target)} />
                ))}
              </>
            )}
            {/* Bereitstellung übergehen: die EINZIGE Unter-Auftragsart, die das System
                selbst anlegt, braucht einen Ausstieg. */}
            {canSkipProvisioning && (
              <button className="erp-idbtn erp-idbtn-danger" data-tip-pos="bottom"
                data-tip="Bereitstellung übergehen – ich bringe das Material von Hand an seinen Ort"
                aria-label="Bereitstellung übergehen" disabled={statusBusy}
                onClick={() => setDialog('skip-provisioning')}>
                <Ban size={15} />
              </button>
            )}
          </>
        ) : undefined}
      >
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
      </DetailHeader>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 40px', background: 'var(--bg-2)', boxShadow: flash ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'docs' && !isCreate ? (
          <ObjectDocuments objectId={record?.object_id ?? null} contextLabel="diesem Auftrag" />
        ) : (
        // Begrenzte, zentrierte Satzbreite wie in den übrigen Detailfenstern (Notiz #327):
        // auf einem 3440er-Schirm lief die Auftragsspezifikation sonst über die ganze
        // Breite, während der Prozess-Fluss darunter zentriert bei 600 px blieb – zwei
        // Massstäbe in einem Fenster.
        <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%' }}>
        {/* Fehler stehen zuoberst im Inhalt – direkt unter der Aktion, die sie ausgelöst
            hat (Freigeben/Speichern sitzen im Kopf). Kein Fussleisten-Streifen mehr. */}
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '11px 14px', background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 10, fontSize: 13, color: 'var(--danger)', fontWeight: 600 }}>
            <AlertTriangle size={16} style={{ flexShrink: 0 }} /> {error}
          </div>
        )}

        {/* Abgebrochen: der Auftrag ist im Moment des Abbruchs inaktiv – nicht «ausstehend»,
            nicht rücknehmbar. Der Abweichungsauftrag führt ihn fort. */}
        {!isCreate && record.abort_into_id != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '12px 14px', background: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: 10, fontSize: 13, color: 'var(--danger)', fontWeight: 600 }}>
            <Ban size={16} /> Abgebrochen – fortgeführt im Abweichungsauftrag <ObjId value={record.abort_into_id} />.
          </div>
        )}

        {/* ── Auftragsspezifikation ─────────────────────────────────────────────────
            **Was** dieser Auftrag betrifft – und damit das Erste, was man sehen will: sie
            steht immer zuoberst, direkt unter dem Kopf. Eine Position ist EINE Zeile
            (Artikel · Menge · woher), dieselbe für einen wie für viele Artikel. Die bei der
            Freigabe entstandenen **Instanzen** stehen in derselben Karte statt in einer
            zweiten darunter – sie sind das Ergebnis derselben Aussage, kein neues Thema. */}
        <SectionTitle>Auftragsspezifikation</SectionTitle>
        {demandEditable ? (
          <div style={cardStyle}>
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
                      onToggle={togglePin} pending={pendingPick}
                      onAnswer={(a) => pendingPick && setLinePins(pendingPick.line, pendingPick.ids, a, pendingPick.quantities)}
                      onCancel={() => setPendingPick(null)} />
                  );
                })
              ) : (
                <PositionRow
                  line={pinLines[0]} unit={qtyUnit} canProduce={canProduce}
                  produceHint="Der Ablauf unten wirkt auf vorhandenen Bestand – für Neuerzeugung diese Schritte entfernen"
                  articleSelect={<SearchSelect label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />}
                  qtyInput={<TextFieldUnit label="Menge" value={form.quantity} onChange={(v) => set('quantity', v)} unit={qtyUnit} required placeholder="z. B. 5" />}
                  qty={form.quantity}
                  source={goal} onSource={(s) => pickGoal(s)} onToggle={togglePin}
                  pending={pendingPick}
                  onAnswer={(a) => pendingPick && setLinePins(pendingPick.line, pendingPick.ids, a, pendingPick.quantities)}
                  onCancel={() => setPendingPick(null)} />
              )}

              {isCreate && releasedArticles.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--warning)', background: 'var(--warning-bg)', borderRadius: 8, padding: '8px 10px' }}>
                  Kein freigegebener Artikel vorhanden – nur freigegebene sind referenzierbar.
                </div>
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

              {/* Der frühere Footer-Satz – jetzt eine leise Zeile in der Karte, auf die er
                  sich bezieht (und nur beim Anlegen, wo er etwas erklärt). */}
              {isCreate && (
                <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>
                  {demandValid ? 'Wird automatisch angelegt, sobald vollständig' : 'Pflichtfelder: Artikel und Menge'}
                </div>
              )}
          </div>
        ) : (
          // Lese-Ansicht als **EINE Spezifikations-Karte** – dieselbe Anatomie wie die
          // Artikel-Spezifikation (Notiz #267): ein Blatt, darin ein Werteraster aus
          // Lesefeldern. Vorher standen dieselben Angaben als lose Kacheln nebeneinander,
          // also drei Kästen für eine Aussage; die Karte fasst sie zusammen, ohne dass die
          // Auftragsspezifikation eine eigene Formensprache bräuchte.
          <div style={{ ...SPEC.card, marginBottom: 12 }}>
            <div style={SPEC.grid}>
              {/* Artikel → Menge → die dazugehörigen Instanzen: EINE Aufstellung statt
                  «Positionen oben, alle Instanzen unten». Bei mehreren Positionen war
                  sonst nicht erkennbar, welche Instanz zu welchem Artikel gehört. */}
              {record && <OrderPositions order={record} />}
              <ReadField icon={CalendarClock} label="Wunsch-Liefertermin"
                value={record?.desired_delivery_date ? localDate(record.desired_delivery_date) : 'Schnellstmöglich'} />
              {/* Fakturiert durch: die Gesellschaft, die diesen Verkauf ausstellt (Seller of
                  Record, ADR 006). Nur bei einem Verkauf/einer Retoure gesetzt und – als
                  interne Buchungs-Angabe – nur fürs Personal. Objektnummer klickbar. */}
              {isStaff && record?.seller_company_object_id != null && (
                <ReadField icon={Building2} label="Fakturiert durch"
                  value={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    {record.seller_company_name}<ObjId value={record.seller_company_object_id} />
                  </span>} />
              )}
              {/* Erstellt/Geändert: früher ein Fussleisten-Streifen am Fensterrand – jetzt
                  eine Angabe unter den übrigen, wo sie hingehört (kein Footer mehr). */}
              {record && <ReadField icon={HistoryIcon} label="Angelegt" value={localDate(record.created_at)} />}
            </div>
          </div>
        )}


        {/* Unteraufträge (Abweichungen) sichtbar machen – DAU-sicher: Symbol + Farbe + Klartext,
            klickbare Objektnummern, grüne Badge bei erledigter Abweichung. Pausiert der Auftrag,
            steht das gross zuoberst. (Der Abbruch-Folgeauftrag hat oben schon seinen Banner.) */}
        {/* Der Nachschub steht im **Ablauf** an seinem Schritt (Notizen #259/#260) –
            wie eine Abweichung. Eine zweite Liste daneben sagte dasselbe noch einmal und
            verschwieg, WO im Prozess der Bedarf entstand. */}

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

        {/* «Abweichung melden» sitzt jetzt als kleiner Flag-Knopf im Kopf (analog Instanz) –
            keine eigene Karte mehr im Detailfenster. */}

        {/* Unter-Auftrag (Entwurf): der Bedarf steht oben (und ist erweiterbar, #355) – hier
            wird der Ablauf definiert, dann freigegeben. Abweichung = was mit den Instanzen
            geschieht; Nachschub = wie die Fehlmenge entsteht/beschafft wird. */}
        {isStaff && record?.status === 'draft' && isSubOrder && (
          <>
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
            {/* Keine Überschrift (Notiz #270): der Fluss mit Start-/Endknoten sagt selbst,
                was er ist – und dass er nur zur Ansicht steht, zeigt der fehlende Editor. */}
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
            {/* Frei im Weissraum, wie der Editor am Artikel – kein zweiter Karten-Hintergrund
                um einen Fluss, der schon aus Karten besteht. */}
            <div style={{ marginBottom: 12 }}>
              <OrderFlow
                steps={steps}
                deviations={record.deviations ?? []}
                waitingFor={record.waiting_for ?? []}
                missing={missingText}
                selectedId={currentStepId}
                onSelectStep={setSelStep}
                onOpenOrder={(oid) => nav?.(oid)}
                renderPanel={(step) => (
                  // **Auch ein blockierter Schritt zeigt sein Panel** (Notiz #353): was
                  // darin schon erledigt wurde (eine eingeholte Offerte, erfasste Werte),
                  // darf nicht verschwinden, nur weil der Prozess gerade ruht. Ausführen
                  // lässt sich trotzdem nichts – das Backend nennt beim Versuch den Grund.
                  <StepPanel key={String(step.id)} step={step} order={record as Order}
                    viewerRole={viewerRole} company={company} onSaved={afterStep} />
                )}
              />
              {/* **Die Fehlmenge gehört dem Auftrag** – eine Frage, eine Stelle, drei
                  Antworten. Solange sie offen ist, ruht der Prozess. Wartet er bereits auf
                  einen Unter-Auftrag, ist die Entscheidung getroffen: dann steht die Angabe
                  bei diesem Unter-Auftrag im Fluss und hier gar nichts (Notiz #354). */}
              {needsDecision && (
                <ProcessHoldNotice missing={missingText} canAct={isStaff && record.status === 'released'}
                  busy={supplyBusy || recoverBusy} error={error}
                  onAnswer={answerShortfall} candidates={shortfallCandidates} canReduce={hasSubjectShortfall} />
              )}
            </div>
          </>
        ) : !isStaff && hasPurchase ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <PurchaseStepPanel order={record as Order} purchases={record?.purchase ? [record.purchase] : []}
              viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
          </>
        ) : null}

        </div>)}
      </div>

      {/* Kein Footer mehr (Notiz #140). Die drei Dinge, die er trug, stehen jetzt dort,
          wo sie hingehören: der **Fehler** direkt unter dem Kopf – bei der Aktion, die ihn
          ausgelöst hat («Freigeben» steht im Kopf); der **Auto-Save-Status** als grüner
          Flash im Kopf (SaveIndicator, war schon immer dort); das **Abbrechen** der Anlage
          als Aktion neben dem Status. */}


      {dialog === 'skip-provisioning' && record && (
        <DeactivateDialog
          mode="deactivate"
          title="Bereitstellung übergehen"
          message="Die Bereitstellung wird inaktiv und für diesen Schritt NICHT neu angelegt – du bringst das Material selbst an seinen Ort. Der übergeordnete Auftrag läuft danach weiter."
          confirmLabel="Übergehen"
          onConfirm={confirmSkipProvisioning}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}


// Subjekt-Schritte wirken auf die Fertigware des Auftrags (nicht auf Komponenten). Nur bei
// ihnen ist «Aus Lager decken» (inkl. gezielter Instanz-Auswahl) sinnvoll – ein Komponenten-
// (`orderTitle` ist entfallen – der Name eines Auftrags wird EINMAL im Backend abgeleitet
//  (`orders.order_display_name`) und über `lib/record-name.orderName` gelesen, damit Feed
//  und Detail nicht auseinanderlaufen können, Notiz #177.)

// (Der Kopf kommt aus `fields.DetailHeader` – die lokalen Kopf-Stile sind entfallen, #242.)



// **Unterdeckung: EINE Frage, drei Antworten – und ein Fenster dafür.**
//
// Es gibt nur EINEN Grund, warum ein Prozess ruht: dem Auftrag fehlt etwas. Eine offene
// Abweichung nimmt ihr Stück heraus, ein Ausschuss verliert eines, eine weggenommene
// Reservierung ebenso – für den Auftrag ist das derselbe Sachverhalt und darum dieselbe
// Frage: *was soll mit der Fehlmenge geschehen?*
//
// Hier steht nur der Anlass; die Antworten stehen in einer kleinen Lightbox (Notiz #352,
// ``ShortfallDialog``) – demselben Fenster, das auch beim Auswählen gebundener Instanzen
// erscheint. Eine Frage, ein Fenster, egal von wo.
//
// Ist die Menge bereits in einem Unter-Auftrag gebunden, erscheint hier gar nichts: dann ist
// die Entscheidung getroffen, und die Angabe steht bei diesem Unter-Auftrag im Fluss (#354).
function ProcessHoldNotice({ missing, canAct, busy, error, candidates, canReduce, onAnswer }: {
  missing?: string;
  canAct: boolean;
  busy: boolean;
  error: string | null;
  candidates: { object_id: number; quantity: number }[];
  canReduce: boolean;
  onAnswer: (answer: ShortfallAnswer, instanceObjectIds?: number[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const text = `Es fehlt ${missing ?? 'etwas'} – der Prozess ruht, bis entschieden ist, wie es weitergeht.`;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap', font: '700 13.5px var(--font-body)', color: 'var(--warning)' }}>
        <PauseCircle size={16} /> Es fehlt
        {missing && <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-1)' }}>{missing}</span>}
      </div>
      {canAct && (
        <PrimaryButton icon={PackagePlus} onClick={() => setOpen(true)} disabled={busy}>
          {busy ? 'Wird übernommen…' : 'Entscheiden'}
        </PrimaryButton>
      )}
      {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      {open && (
        <ShortfallDialog text={text} candidates={candidates} canReduce={canReduce} busy={busy} error={error}
          onAnswer={(a, ids) => { setOpen(false); onAnswer(a, ids); }} onClose={() => setOpen(false)} />
      )}
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
  canProduce, produceHint, articleSelect, qtyInput, pending, onAnswer, onCancel,
}: {
  line?: PinLine;
  unit: string;
  title?: string;
  articleObjectId?: number | null;
  qty: string;
  source: OrderGoal;
  onSource: (s: OrderGoal) => void;
  onToggle: (line: PinLine, oid: number, qty: number, qtyOnly?: boolean) => void;
  onRemove?: () => void;
  /** Offene Unterdeckungs-Frage zu dieser Position (Auswahl greift auf gebundene Instanzen). */
  pending?: { line: PinLine; ids: number[]; text: string; quantities?: Record<string, number> } | null;
  onAnswer?: (a: ShortfallAnswer) => void;
  onCancel?: () => void;
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
  // «Auswählen» braucht genug **wählbaren** Bestand (frei + gebunden): sonst liesse sich die
  // Auswahl nie vervollständigen und die Freigabe bliebe für immer gesperrt (Notiz #356).
  const poolQty = line?.poolQty ?? 0;
  const pickable = poolQty >= req && req > 0;

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
              { value: 'specific', icon: Target, label: 'Auswählen', disabled: !pickable,
                hint: pickable
                  ? 'Genau bestimmen, welche Instanzen – auch gebundene (→ Abweichung)'
                  : `Es gibt nur ${poolQty} ${unit} zum Auswählen (${req} nötig)` },
            ]}
          />

          {source === 'specific' && <PinPicker line={line} onToggle={onToggle} bare />}
          {pending?.line.key === line.key && (
            // **Die Frage kommt sofort** – nicht irgendwann später am Eltern-Auftrag: wer
            // ein Stück aus einem laufenden Auftrag herauszieht, entscheidet im selben Zug,
            // wie es dort weitergeht. Dasselbe Fenster wie am laufenden Auftrag (#352).
            <ShortfallDialog text={pending.text} onAnswer={(a) => onAnswer?.(a)} onClose={() => onCancel?.()} />
          )}

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
  line: PinLine;
  /** Auswahl umschalten bzw. – mit ``qtyOnly`` – nur die beanspruchte Menge ändern. */
  onToggle: (line: PinLine, oid: number, qty: number, qtyOnly?: boolean) => void;
  bare?: boolean;
}) {
  // Suche nach Instanznummer: bei ein paar Instanzen sucht das Auge, bei ein paar hundert
  // nicht mehr. Das Feld erscheint darum erst, wenn die Liste es rechtfertigt.
  const [q, setQ] = useState('');
  const SEARCH_FROM = 8;
  const needle = q.trim().replace(/\D/g, '');
  const pool = needle
    ? line.pool.filter((i) => String(i.object_id ?? '').includes(needle))
    : line.pool;
  // Welche Sorte wird gerade gewählt? Aus der Auswahl abgeleitet, kein Schalter.
  const chosen = line.pool.filter((i) => line.pinnedIds.includes(i.object_id!));
  const picking: PinKind | null = chosen.length === 0 ? null : line.kind(chosen[0]);

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
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 200, overflowY: 'auto' }}>
          {pool.map((i) => {
            const oid = i.object_id!;
            const kind = line.kind(i);
            const cfg = PIN_KIND[kind];
            const sel = line.pinnedIds.includes(oid);
            const have = i.quantity ?? 1;
            // **Wie viel von dieser Instanz?** (Notiz #361) Eine Charge ist eine MENGE, kein
            // Ding: von 500 Schrauben will man oft genau EINE. Voreingestellt ist, was noch
            // fehlt – höchstens aber, was die Instanz hergibt.
            const want = sel ? (line.wanted[oid] ?? have) : Math.min(have, Math.max(line.reqQty - line.pinnedQty, 0));
            // Sperren nur noch, wenn schon die volle Menge beisammen ist – eine zu grosse
            // Charge ist kein Hindernis mehr, man nimmt eben eine Teilmenge daraus.
            const atLimit = !sel && line.pinnedQty >= line.reqQty && line.reqQty > 0;
            // **Kein Mischmasch** (Notiz #355): sobald die erste Instanz gewählt ist, steht die
            // Art des Auftrags fest. Die anderen Sorten sind dann gesperrt (das Backend weist
            // sie ohnehin ab); der Hover sagt, warum.
            const wrongKind = !sel && picking != null && picking !== kind;
            const off = atLimit || wrongKind;
            return (
              <span key={oid} style={{
                display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12,
                fontFamily: 'var(--font-mono)', padding: '3px 4px 3px 10px', borderRadius: 999,
                border: `1px solid ${sel ? cfg.tone : 'var(--border-1)'}`,
                background: sel ? cfg.bg : '#fff', color: sel ? cfg.tone : 'var(--fg-3)',
                opacity: off ? 0.4 : 1,
              }}>
                <button type="button" disabled={off} onClick={() => onToggle(line, oid, want)}
                  title={wrongKind ? `${picking ? PIN_KIND[picking].mix : ''} – nicht mit anderen Sorten mischbar`
                    : atLimit ? 'Die Menge ist bereits beisammen' : cfg.hint}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 5, border: 'none',
                    background: 'none', font: 'inherit', color: 'inherit', padding: 0,
                    cursor: off ? 'not-allowed' : 'pointer' }}>
                  {sel ? <CheckCircle2 size={12} />
                       : <span style={{ width: 6, height: 6, borderRadius: 999, background: cfg.tone }} />}
                  {fmtObjId(oid)}
                </button>
                {/* Die Menge steht IM Chip – gewählt als Feld, sonst als blosse Angabe.
                    Bei einer Instanz mit Menge 1 gibt es nichts zu entscheiden. */}
                {sel && have > 1 ? (
                  <input value={String(line.wanted[oid] ?? have)}
                    onChange={(e) => onToggle(line, oid, Number(numericOnly(e.target.value)) || 0, true)}
                    {...numericInputProps} aria-label={`Menge von ${fmtObjId(oid)}`}
                    style={{ width: 46, textAlign: 'center', border: `1px solid ${cfg.tone}`,
                      borderRadius: 999, background: '#fff', color: cfg.tone, font: 'inherit',
                      padding: '1px 4px', outline: 'none' }} />
                ) : (
                  <span style={{ paddingRight: 6, opacity: 0.75 }}>·{have}</span>
                )}
              </span>
            );
          })}
        </div>
      )}
    </>
  );
  if (bare) return <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{body}</div>;
  return <div style={cardStyle}>{body}</div>;
}

// (``PositionsList`` ist entfallen: die Lese-Ansicht der Positionen führt jetzt
//  ``OrderPositions`` – dort trägt jede Position ihre eigenen Instanzen, Notiz #141.)

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
