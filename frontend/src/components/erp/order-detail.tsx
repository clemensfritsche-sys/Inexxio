'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Ban, X, History as HistoryIcon, ClipboardList, ArrowLeft, Workflow, MapPin, CheckCircle2, Loader2, Repeat, ChevronDown, Factory, Warehouse, Target, AlertTriangle, PauseCircle, PackagePlus, Plus, Trash2, Undo2, FolderOpen, CalendarClock, Search, Building2, Boxes, TriangleAlert } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import { draftStepStore, toStepInputs } from '@/lib/step-store';
import type { AffectedOrder, Article, ArticleProcessStep, CompanySettings, Instance, InstancePickInput, Order, OrderDeviationInfo, OrderPurchase, OrderStep, OrderUpdateInput, UserProfile } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { orderStatus } from '@/lib/record-status';
import { unitLabel } from '@/lib/article';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import type { StatusAction } from '@/lib/status-flow';

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
import { formatObjectId, localDate } from '@/lib/utils';

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
/**
 * **Ein Anteil – die Zeile, die man anklickt.** Eine Instanz ist eine MENGE, und ihre
 * Menge ist immer vollständig aufgeteilt: jeder Anteil gehört genau einem Auftrag oder ist
 * frei. Weil man die Zeile wählt, ist zugleich beantwortet, WEM man etwas wegnimmt – die
 * Frage, die bei einer Charge mit mehreren Ansprüchen sonst nicht entscheidbar wäre.
 */
type Share = {
  key: string;                    // instanz:halter – eindeutig je Zeile
  instanceObjectId: number;
  instanceQty: number;            // Gesamtmenge der Instanz (für die Anzeige)
  quantity: number;               // Menge DIESES Anteils
  /** Wie viel diese Position von hier nehmen darf: die Menge des Anteils **plus** das,
   *  was sie selbst schon hält – ihr eigener Anspruch ist im Entwurf noch nicht scharf
   *  und flösse bei einer Änderung dorthin zurück. */
  capacity: number;
  holderObjectId: number | null;  // null = frei
  holderName: string | null;
  kind: PinKind;
};

type PinLine = {
  key: string; lineId: number | null; articleId: number; unit: string; reqQty: number;
  /** Die wählbaren Anteile dieses Artikels (frei · gebunden · verkauft). */
  shares: Share[];
  /** Was gewählt ist – genau die Form, die auch zum Server geht. */
  picked: InstancePickInput[];
  pickedQty: number;
  availableQty: number;
  /** Menge über ALLE Anteile (frei + gebunden) – Grundlage für «Auswählen». */
  poolQty: number;
};

/** Die drei Sorten, die ein Anteil haben kann – sie bestimmen die Art des Auftrags. */
type PinKind = 'free' | 'bound' | 'sold';

/** Schlüssel einer Anteils-Zeile – dieselbe Bildung auf beiden Seiten der Auswahl. */
function shareKey(instanceObjectId: number, holder: number | null): string {
  return `${instanceObjectId}:${holder ?? 'free'}`;
}

/**
 * **Die Auswahl folgt den Zeilen, nicht umgekehrt** (Testnotiz #390).
 *
 * Ein Anteil ist eine Aussage über EINEN Moment: «1 Stk aus Auftrag …456». Die Zeilen
 * daneben sind der **aktuelle** Stand. Beides kann auseinandergehen – der Abkürzungs-Knopf
 * an der Instanz kannte den Halter nicht, ein Halter hat inzwischen gewechselt, oder ein
 * gespeicherter Entwurf stammt aus einer Zeit ohne Halter-Angabe. Dann gewinnt der aktuelle
 * Stand: die Auswahl wandert auf die Zeile **derselben Instanz**.
 *
 * Ohne das war eine so entstandene Auswahl unsichtbar (kein Treffer) und zählte trotzdem
 * zur Menge – bei Auftragsmenge 1 galt die Zeile damit als «schon beisammen» und liess sich
 * nicht mehr anklicken. Genau der gemeldete Fall: 1 von 4 ging nicht, 2 von 4 schon.
 *
 * Ein Anteil, den es gar nicht mehr gibt, fällt weg – man kann nichts beanspruchen, was
 * nicht da ist. **Und es wird nicht geraten** (Testnotiz #394): passt die Angabe auf keine
 * Zeile, wandert sie nur dann auf eine andere, wenn es genau EINE gibt. Bei mehreren
 * Anteilen ist die Zeile eine Entscheidung – seit der genannte Anteil bei der Freigabe
 * wirklich verliert, würde ein Zufallstreffer dem falschen Auftrag etwas wegnehmen.
 */
function reconcilePicks(picks: InstancePickInput[], shares: Share[]): InstancePickInput[] {
  const out: InstancePickInput[] = [];
  for (const p of picks) {
    const rows = shares.filter((sh) => sh.instanceObjectId === p.instance_object_id);
    if (rows.length === 0) continue;
    const hit = rows.find((sh) => sh.holderObjectId === (p.from_order_object_id ?? null))
      ?? (rows.length === 1 ? rows[0] : null);
    if (!hit) continue;
    out.push({ ...p, from_order_object_id: hit.holderObjectId,
               quantity: Math.min(p.quantity ?? hit.quantity, hit.quantity) });
  }
  return out;
}

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

/**
 * **Was ein Abkürzungs-Knopf in den neuen Auftrag hineinlegt** – eine Eingabehilfe, keine
 * Fixierung (Notizen #371/#385): Artikel bzw. Instanz sind vorgewählt, alles bleibt im
 * Entwurf frei änderbar. Der Auftrag selbst entsteht erst mit der Freigabe (#386) – ein
 * Klick auf «Auftrag anlegen» erzeugt also noch keinen Datensatz.
 */
export type OrderSeed = {
  articleId: number;
  quantity?: number;
  /** Vorgewählter **Anteil** – immer EIN Stück (von einer Charge à 500 selten alle 500),
   *  mitsamt dem Halter, aus dessen Anteil er kommt. */
  instance?: { objectId: number; quantity: number; fromOrderObjectId?: number | null };
};

/** Ein leerer Auftrag in der Form, die auch der Server liefert – der Entwurf im Browser. */
function emptyDraft(): Order {
  return {
    id: 0, object_id: null, status: 'draft', article_id: null, quantity: null,
    desired_delivery_date: null, order_lines: [], instances: [], steps: [],
    shortfall: [], affects: [], waiting_for: [], deviations: [], supply_orders: [],
    returns: [], provisionings: [], created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  } as unknown as Order;
}

/** Der Entwurf, wie ihn ein Abkürzungs-Knopf vorbelegt – sonst der leere. */
function seededDraft(seed: OrderSeed | null | undefined, articles: Article[]): Order {
  const d = emptyDraft();
  if (!seed) return d;
  const art = articles.find((a) => a.id === seed.articleId);
  return {
    ...d, article_id: seed.articleId, quantity: seed.quantity ?? 1,
    article_object_id: art?.object_id ?? null, article_name: art?.name ?? null,
    article_unit: art?.unit ?? null,
  } as Order;
}

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
/**
 * **Die Unterdeckungs-Frage kommt als Code, nicht als Satz.** Der Server antwortet auf eine
 * Freigabe, die einem laufenden Auftrag sein Stück wegnimmt, mit 409 + strukturiertem
 * `detail` (`code` + `affects`) – die Oberfläche erkennt sie daran und stellt die Frage,
 * statt den Fehler anzuzeigen. Vorher wurde im Meldungstext nach Wörtern gesucht; eine
 * umformulierte Meldung hätte die Frage still verschluckt.
 */
type ShortfallDetail = { code?: string; affects?: AffectedOrder[] };
function shortfallDetail(e: unknown): ShortfallDetail | null {
  const d = e instanceof ApiError ? (e.detail as ShortfallDetail | undefined) : undefined;
  return d?.code === 'shortfall_decision_required' ? d : null;
}
const isShortfallQuestion = (e: unknown) => shortfallDetail(e) !== null;
const shortfallAffects = (e: unknown) => shortfallDetail(e)?.affects ?? [];

function orderActions(status: string, canRelease: boolean, releaseHint?: string): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
      hint: canRelease ? undefined : releaseHint }];
  return [];
}

export function OrderDetail({ record: saved, seed, articles, viewerRole, company, suppliers = [], onSaved, onBack }: {
  record: Order | null;            // null ⇒ Anlage-Modus (nur Mitarbeiter)
  /** Vorbelegung aus einem Abkürzungs-Knopf (Artikel-/Instanz-Detail) – nur beim Anlegen. */
  seed?: OrderSeed | null;
  articles: Article[];
  viewerRole: ViewerRole;
  company: Partial<CompanySettings> | null;
  suppliers?: UserProfile[];
  onSaved: (o: Order) => void;
  /** Zurück – im Anlage-Modus zugleich das Verwerfen: der Entwurf lebt nur hier (#386). */
  onBack: () => void;
}) {
  const isCreate = saved === null;
  const isStaff = viewerRole === 'staff';
  const nav = useErpNav();   // Navigation per Objektnummer (Unteraufträge anklickbar)
  // **Der Entwurf lebt im Browser** (Testnotiz #386): ein Auftrag entsteht erst mit der
  // Freigabe – vorher gibt es ihn in der Datenbank nicht, er verbraucht keine Objektnummer,
  // und wer wegklickt, hat ihn verworfen. Damit die Oberfläche davon nichts merkt, hat der
  // Entwurf **dieselbe Form** wie ein gespeicherter Auftrag: alles Weitere liest `record`
  // und weiss gar nicht, woher es kommt. Geschrieben wird je nach Herkunft – in die API
  // oder in den State (`patchDraft`).
  const [draft, setDraft] = useState<Order>(() => seededDraft(seed, articles));
  const [draftSteps, setDraftSteps] = useState<ArticleProcessStep[]>([]);
  // Der Schritt-Editor ist derselbe – nur der **Speicher** ist ein anderer. Die Liste
  // liegt zusätzlich in einem Ref, weil der Editor nach jeder Änderung sofort neu liest
  // (`reload()`): React-State wäre dann noch der alte.
  const draftStepsRef = useRef<ArticleProcessStep[]>([]);
  const draftStore = useMemo(() => draftStepStore(
    () => draftStepsRef.current,
    (next) => { draftStepsRef.current = next; setDraftSteps(next); },
    suppliers,
  ), [suppliers]);
  // Vorgemerkte Instanzen je Position (Schlüssel wie `PinLine.key`) – im Entwurf.
  type DraftPins = Record<string, InstancePickInput[]>;
  const [draftPins, setDraftPins] = useState<DraftPins>((): DraftPins => (seed?.instance
    ? { anchor: [{ instance_object_id: seed.instance.objectId, quantity: seed.instance.quantity,
                   from_order_object_id: seed.instance.fromOrderObjectId ?? null }] }
    : {}));
  const record: Order = saved ?? draft;
  function patchDraft(patch: Partial<Order>) { setDraft((d) => ({ ...d, ...patch })); }
  const [form, setForm] = useState<Form>(() => seedFrom(saved ?? draft));
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
  // **Am laufenden Auftrag ist der Betroffene er selbst** – dieselbe Liste, dieselbe Form
  // wie bei der Freigabe eines Entwurfs (Notiz #387): worüber entscheide ich hier gerade?
  // Herkunft (`sources`) gibt es hier nicht: am laufenden Auftrag fehlt eine **Menge** –
  // sie wurde nicht gerade einer bestimmten Instanz entnommen (das ist der Freigabe-Fall).
  const selfAffected: AffectedOrder[] = record?.object_id != null
    ? shortfall.map((sf) => ({
        object_id: record.object_id as number, name: orderName(record), reason: record.reason,
        article_name: sf.article_name ?? null, unit: record.article_unit ?? null,
        quantity: sf.quantity, sources: [],
      }))
    : [];

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
  // **Im Entwurf gibt es nichts zu speichern** – das Formular IST der Auftrag (#386).
  // Darum kein Auto-Save (der ist der Weg zum Server), sondern ein Übernehmen ohne
  // Verzögerung: sonst wäre «Freigeben» nach dem letzten Tastendruck noch Sekunden lang
  // gesperrt, und die Instanz-Auswahl kennte den Artikel noch nicht.
  const canSave = !isCreate && demandEditable && demandValid && sig !== savedSig && !saving;
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
  // Der Entwurf – gespeichert oder noch im Browser (#386): beide brauchen den Instanz-Pool
  // für die Auswahl.
  const isDraftStaff = isStaff && record.status === 'draft';
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
  const isFree = (i: Instance) =>
    i.quality === 'passed' && i.disposition === 'in_stock' &&
    (i.reserved_for_order_object_id == null || i.reserved_for_order_object_id === record?.object_id);

  // **Drei Sorten, eine Auswahl** (Notiz #360) – und die Sorte bestimmt die Art des
  // Auftrags (`classify_pick`): frei → gewöhnlicher Bedarf · gebunden → Abweichung ·
  // verkauft → Retoure. Gemischt wird nie: das Backend weist es ab, die Oberfläche sperrt
  // die jeweils andere Sorte, sobald die erste gewählt ist.
  function shareKind(i: Instance, holder: number | null): PinKind {
    if (i.disposition === 'sold') return 'sold';
    if (holder != null && holder !== record?.object_id) return 'bound';
    return isFree(i) ? 'free' : 'bound';
  }

  // Was der Auftrag schon beansprucht – aus den Instanz-Embeds (gespeicherter Entwurf).
  // ``move_quantity`` ist die für ihn reservierte Teilmenge, ``pick_source_object_id`` der
  // Anteil, aus dem sie stammt: so trifft eine erneute Bearbeitung wieder dieselbe Zeile.
  const savedPicksByArticle = new Map<number, InstancePickInput[]>();
  const ownByInstance = new Map<number, number>();
  for (const i of record?.instances ?? []) {
    if (i.object_id == null) continue;
    const list = savedPicksByArticle.get(i.article_id) ?? [];
    const qty = i.move_quantity ?? i.quantity ?? 0;
    list.push({ instance_object_id: i.object_id, quantity: qty,
                from_order_object_id: i.pick_source_object_id ?? null });
    savedPicksByArticle.set(i.article_id, list);
    ownByInstance.set(i.object_id, qty);
  }

  function buildPinLine(lineId: number | null, articleId: number, unit: string, reqQty: number): PinLine {
    // **Verschrottet ist raus, alles andere ist drin** (Notiz #360): frei (grün), gebunden
    // (gelb: in Arbeit / reserviert / gesperrt) UND **verkauft**. Für eine Rücksendung muss
    // man ebenso genau sagen, WELCHES Stück zurückkommt – FIFO ergäbe dort keinen Sinn.
    //
    // Gewählt wird nicht die Instanz, sondern der **Anteil**: eine Charge à 4, an der zwei
    // Aufträge hängen, erscheint als zwei Zeilen. Damit ist mit dem Klick beantwortet, wem
    // die Menge weggenommen wird – das Backend muss nicht mehr raten (``pick_sources``).
    const shares: Share[] = [];
    for (const i of pinPool) {
      if (i.object_id == null || i.article_id !== articleId || i.disposition === 'scrapped') continue;
      const rows = i.shares && i.shares.length > 0
        ? i.shares
        : [{ order_object_id: null, order_name: null, reason: null, quantity: i.quantity ?? 0 }];
      for (const sh of rows) {
        // Der eigene Anteil ist keine fremde Zeile – er IST die Auswahl (steht unten).
        if (sh.order_object_id != null && sh.order_object_id === record?.object_id) continue;
        if ((sh.quantity ?? 0) <= 0) continue;
        shares.push({
          key: shareKey(i.object_id, sh.order_object_id ?? null),
          instanceObjectId: i.object_id, instanceQty: i.quantity ?? 0,
          quantity: sh.quantity ?? 0, capacity: sh.quantity ?? 0,
          holderObjectId: sh.order_object_id ?? null, holderName: sh.order_name ?? null,
          kind: shareKind(i, sh.order_object_id ?? null),
        });
      }
    }
    const key = lineId != null ? `line-${lineId}` : 'anchor';
    // Im Entwurf steht die Auswahl im State (nichts ist gespeichert), sonst kommt sie aus
    // den Instanz-Embeds des Auftrags.
    const raw = isCreate ? (draftPins[key] ?? []) : (savedPicksByArticle.get(articleId) ?? []);
    const picked = reconcilePicks(raw, shares);
    // Was diese Position selbst schon von einer Instanz hält – im Entwurf noch nicht
    // scharf, also für sie weiterhin verfügbar.
    for (const sh of shares) {
      const own = ownByInstance.get(sh.instanceObjectId) ?? 0;
      sh.capacity = sh.quantity + (picked.some((p) => p.instance_object_id === sh.instanceObjectId
                                                   && (p.from_order_object_id ?? null) === sh.holderObjectId)
                                   ? own : 0);
    }
    return {
      key, lineId, articleId, unit, reqQty, shares, picked,
      pickedQty: picked.reduce((s, p) => s + (p.quantity ?? 0), 0),
      // «Genug Bestand?» meint das FREI Verfügbare – gebundene Anteile zählen dafür nicht.
      availableQty: shares.filter((sh) => sh.kind === 'free').reduce((s, sh) => s + sh.quantity, 0),
      // Was sich überhaupt auswählen liesse. Reicht das nicht für die Menge, ist «Auswählen»
      // eine Sackgasse: die Auswahl liesse sich nie vervollständigen (Notiz #356).
      poolQty: shares.reduce((s, sh) => s + sh.quantity, 0),
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
  const pins = pinLines.flatMap((l) => l.picked);
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
    if (g !== 'specific') {   // «Aus Lager»/«Herstellen» = ohne Auswahl
      for (const l of pinLines) {
        if (l.picked.length > 0) await setLinePins(l, []);
      }
    }
  }

  /** Einen **Anteil** an-/abwählen bzw. seine Menge ändern – die eine Schreibstelle. */
  function togglePin(line: PinLine, share: Share, qty: number, qtyOnly?: boolean) {
    const same = (p: InstancePickInput) =>
      shareKey(p.instance_object_id, p.from_order_object_id ?? null) === share.key;
    const has = line.picked.some(same);
    const next = qtyOnly || !has
      ? [...line.picked.filter((p) => !same(p)),
         { instance_object_id: share.instanceObjectId, quantity: qty,
           from_order_object_id: share.holderObjectId }]
      : line.picked.filter((p) => !same(p));
    setLinePins(line, next);
  }

  // Mehrpositionen-Auftrag: JEDE Position entscheidet SELBST «Aus Lager (FIFO)» oder «Instanz
  // wählen» – nicht mehr global für alle. Der Modus ist abgeleitet (hat die Position Pins →
  // specific) mit einem UI-Override, solange noch keine Instanz gewählt ist.
  const [lineModes, setLineModes] = useState<Record<string, 'fifo' | 'specific'>>({});
  function lineMode(l: PinLine): 'fifo' | 'specific' {
    if (l.picked.length > 0) return 'specific';
    return lineModes[l.key] ?? 'fifo';
  }
  async function setLineMode(l: PinLine, m: 'fifo' | 'specific') {
    setLineModes((prev) => ({ ...prev, [l.key]: m }));
    if (m === 'fifo' && l.picked.length > 0) await setLinePins(l, []);
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
    ? pinLines.every((l) => lineMode(l) === 'fifo' || l.pickedQty === l.reqQty)
    : (goal !== 'specific' || (pinLines.length > 0 && pinLines.every((l) => l.pickedQty === l.reqQty)));
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
  // **Wer vorhandene Instanzen wählt, erzeugt keine** (Testnotiz #392): der Artikel-Prozess
  // beschreibt, wie etwas ENTSTEHT – er ist der Ablauf einer Erzeugung. Eine Auswahl sagt
  // «das Material gibt es schon», also braucht der Auftrag einen **eigenen** Ablauf. Vorher
  // liess sich ein Auftrag mit gewählten Instanzen und leerem Ablauf freigeben; er fuhr dann
  // den Artikel-Prozess über fremdes Material. Dieselbe Regel prüft das Backend.
  const needsOwnFlow = !isSubOrder && (isMultiPosition || goal !== 'produce');
  const flowReady = !needsOwnFlow || stepCount > 0;
  const canRelease = hasDemand && sig === savedSig
    && (isSubOrder ? subOrderReady : specificComplete && flowReady);
  const releaseHint = isSubOrder
    ? (subOrderReady ? undefined : (isSupply ? 'Erst einen Prozessschritt für den Nachschub hinzufügen' : isReturn ? 'Erst einen Prozessschritt für die Retoure hinzufügen' : 'Erst einen Prozessschritt für die Abweichung hinzufügen'))
    : !specificComplete
      ? (isMultiPosition ? 'Erst für jede Position die passenden Instanzen wählen' : `Erst genau ${reqQty} Instanz(en) wählen`)
      : !flowReady
        ? 'Erst einen Prozessschritt hinzufügen – was soll mit diesen Instanzen geschehen?'
        : 'Erst Artikel und Menge angeben';

  // **Die Auswahl fragt nichts mehr** (Notiz #370): ein Entwurf nimmt niemandem etwas weg –
  // er merkt nur vor. Die Frage «was geschieht mit dem laufenden Auftrag?» steht bei der
  // **Freigabe** (siehe ``changeStatus``), wo die Auswahl feststeht.
  async function setLinePins(line: PinLine, picks: InstancePickInput[], answer?: ShortfallAnswer) {
    if (isCreate) {
      // Im Entwurf ist die Auswahl eine reine Notiz – niemandem wird etwas weggenommen,
      // und gefragt wird erst beim Erteilen (dieselbe Regel wie bisher, nur ohne Server).
      setDraftPins((prev) => ({ ...prev, [line.key]: picks }));
      return;
    }
    try {
      const saved = line.lineId != null
        ? await api.setOrderLinePins(record.object_id as number, line.lineId, { picks })
        : await api.updateOrder(record.object_id as number, {
            picks, shortfall_response: answer, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Festlegen der Instanzen');
    }
  }

  async function addPosition(articleId: number, quantity: number) {
    if (isCreate) {
      // Erste zusätzliche Position: der bisherige Anker wird Position 0 – genau wie im
      // Backend (``_add_line``), nur eben noch im Entwurf.
      const art = articles.find((a) => a.id === articleId);
      setDraft((d) => {
        const lines = [...(d.order_lines ?? [])];
        if (d.article_id != null && lines.length === 0) {
          const anchor = articles.find((a) => a.id === d.article_id);
          lines.push({ id: -1, article_id: d.article_id, quantity: d.quantity ?? 0, position: 0,
            article_object_id: anchor?.object_id ?? null, article_name: anchor?.name ?? null,
            article_unit: anchor?.unit ?? null } as unknown as Order['order_lines'][number]);
        }
        lines.push({ id: -(lines.length + 2), article_id: articleId, quantity, position: lines.length,
          article_object_id: art?.object_id ?? null, article_name: art?.name ?? null,
          article_unit: art?.unit ?? null } as unknown as Order['order_lines'][number]);
        return { ...d, article_id: null, quantity: null, order_lines: lines };
      });
      return;
    }
    const saved = await api.addOrderLine(record.object_id as number, { article_id: articleId, quantity });
    verRef.current = saved.updated_at;
    onSaved(saved);
  }

  async function removePosition(lineId: number) {
    if (isCreate) {
      const left = (draft.order_lines ?? []).filter((l) => l.id !== lineId);
      // Bleibt EINE Position, wird der Auftrag wieder ein Einzel-Artikel-Auftrag –
      // symmetrisch zur ersten Zusatz-Position und identisch zum Backend
      // (``remove_order_line``), damit «Erzeugen» wieder möglich ist.
      if (left.length !== 1) { patchDraft({ order_lines: left }); return; }
      const art = articles.find((a) => a.id === left[0].article_id);
      patchDraft({ order_lines: [], article_id: left[0].article_id, quantity: left[0].quantity,
                   article_object_id: art?.object_id ?? null, article_name: art?.name ?? null,
                   article_unit: art?.unit ?? null });
      // Das Formular ist ab jetzt wieder die Bedarfs-Eingabe – es muss denselben Stand
      // zeigen wie der Entwurf, sonst holte der nächste Autosave den alten Anker zurück.
      const next: Form = { article_id: String(left[0].article_id), quantity: String(left[0].quantity),
                           desired_delivery_date: form.desired_delivery_date };
      setForm(next);
      setSavedSig(demandSig(next.article_id, next.quantity, effectiveDate));
      return;
    }
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
        // Der Entwurf wird NICHT gespeichert – er lebt im Browser, bis er erteilt wird.
        // Die Anzeige-Felder des Artikels wandern gleich mit, damit Titel, Positionen und
        // der gespiegelte Artikel-Prozess dieselbe Quelle lesen wie bei einem gespeicherten
        // Auftrag (`record`) und nichts einen Sonderweg braucht.
        // Bei mehreren Positionen steht der Bedarf auf den Positionen – dort nur den
        // Termin übernehmen (sonst holte das Formular den Anker-Artikel zurück und der
        // Auftrag wäre wieder ein Einzel-Artikel-Auftrag). Dieselbe Fallunterscheidung
        // wie im API-Zweig darunter.
        if (isMultiPosition) patchDraft({ desired_delivery_date: effectiveDate });
        else {
          const aid = form.article_id ? Number(form.article_id) : null;
          const art = aid != null ? articles.find((a) => a.id === aid) : undefined;
          patchDraft({ article_id: aid, quantity: qtyNum, desired_delivery_date: effectiveDate,
                       article_object_id: art?.object_id ?? null, article_name: art?.name ?? null,
                       article_unit: art?.unit ?? null });
        }
        setSavedSig(current);
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

  // Wiederkehr: dieselben drei Werte, zwei Ziele – Entwurf im Browser oder bestehender
  // Auftrag über die API (mit Optimistic Locking, sonst liefe der nächste Autosave in 409).
  const persistRecurrence = useCallback(async (v: Recurrence) => {
    if (isCreate) { setDraft((d) => ({ ...d, ...v })); return; }
    const o = await api.updateOrder(record.object_id as number, { ...v, expected_updated_at: verRef.current });
    verRef.current = o.updated_at;
    onSaved(o);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCreate, record?.object_id, onSaved]);

  async function resyncVersion() {
    if (!record) return;
    try {
      const fresh = await api.getOrder(record.object_id as number);
      verRef.current = fresh.updated_at;
      onSaved(fresh);
    } catch { /* ignore */ }
  }

  const flush = useAutosave(sig, canSave, save);

  // Der Entwurfs-Gegenpart: jede vollständige Eingabe wandert sofort in den Entwurf.
  useEffect(() => {
    if (isCreate && demandValid && sig !== savedSig) save();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCreate, demandValid, sig, savedSig]);

  // Nach Abschluss eines Prozessschritts automatisch zum nächsten aktiven springen
  function afterStep(o: Order) {
    onSaved(o);
    const next = (o.steps ?? []).find((s) => s.state === 'active');
    if (next) setSelStep(String(next.id));
  }

  // ── Den Entwurf erteilen ──────────────────────────────────────────────────────────
  // **Ein Auftrag entsteht als Ganzes oder gar nicht** (Testnotiz #386): alles, was der
  // Entwurf im Browser gesammelt hat, geht in EINEM Aufruf hinaus – Bedarf, Positionen,
  // Ablauf und Auswahl. Erst dort bekommt er seine Objektnummer. Scheitert etwas, bleibt
  // nichts zurück; wer wegklickt, hat verworfen.
  async function submitDraft(answer?: ShortfallAnswer) {
    // Anker + weitere Positionen: der Server kennt genau diese Form (die erste zusätzliche
    // Position wandelt den Anker in Position 0 um) – hier wird sie nur bedient.
    const lines = draft.order_lines ?? [];
    const pinsOf = (key: string) => draftPins[key] ?? [];
    const anchorKey = lines.length > 0 ? `line-${lines[0].id}` : 'anchor';
    const anchorPicks = pinsOf(anchorKey);
    setStatusBusy(true);
    setError(null);
    try {
      const created = await api.createOrder({
        article_id: lines.length > 0 ? lines[0].article_id : draft.article_id,
        quantity: lines.length > 0 ? lines[0].quantity : draft.quantity,
        picks: anchorPicks.length > 0 ? anchorPicks : null,
        desired_delivery_date: draft.desired_delivery_date ?? null,
        lines: lines.slice(1).map((l) => {
          const p = pinsOf(`line-${l.id}`);
          return { article_id: l.article_id, quantity: l.quantity,
                   picks: p.length > 0 ? p : null };
        }),
        steps: toStepInputs(draftSteps),
        recurrence_active: draft.recurrence_active ?? false,
        recurrence_interval_days: draft.recurrence_interval_days ?? null,
        recurrence_lead_time_days: draft.recurrence_lead_time_days ?? null,
        recurrence_anchor: draft.recurrence_anchor ?? null,
        shortfall_response: answer ?? null,
      });
      setPendingRelease(null);
      onSaved(created);
    } catch (e) {
      // Nimmt die Auswahl einem laufenden Auftrag sein Stück weg, nennt der Server die
      // Betroffenen – dann wird gefragt statt abgebrochen (Notizen #370/#387). Beim
      // Entwurf erfährt man sie erst hier: es gibt ja noch keinen Datensatz zu lesen.
      if (isShortfallQuestion(e)) {
        setDraftAffects(shortfallAffects(e));
        setPendingRelease({ target: 'released' });
      } else setError(e instanceof Error ? e.message : 'Auftrag konnte nicht erteilt werden');
    } finally {
      setStatusBusy(false);
    }
  }
  // Die betroffenen Aufträge zur offenen Frage – beim Entwurf nennt sie der Server erst mit
  // dem Fehlschlag (es gibt ja noch keinen Datensatz, den man vorher lesen könnte).
  const [draftAffects, setDraftAffects] = useState<AffectedOrder[]>([]);

  async function changeStatus(target: string, answer?: ShortfallAnswer) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      const saved = await api.updateOrder(record.object_id as number,
        { status: target as Order['status'], shortfall_response: answer,
          expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      setPendingRelease(null);
      onSaved(saved);
    } catch (e) {
      // **Die Frage kommt bei der Freigabe** (Notiz #370): Erst hier steht die Auswahl fest
      // und nimmt einem laufenden Auftrag wirklich etwas weg. Der Server sagt das mit einem
      // Code (und nennt die Betroffenen) – die Frage stellen statt sie wegzuwerfen.
      if (isShortfallQuestion(e)) setPendingRelease({ target });
      else {
        setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
        if (isVersionConflict(e)) await resyncVersion();
      }
    } finally {
      setStatusBusy(false);
    }
  }

  // Offene Unterdeckungs-Frage zur **Freigabe** (nicht mehr zur Auswahl).
  const [pendingRelease, setPendingRelease] = useState<{ target: string } | null>(null);

  // Freigeben heisst beim Entwurf **erteilen** (er entsteht erst dabei), beim bestehenden
  // Auftrag den Status wechseln – dieselbe Aktion, derselbe Knopf.
  function onStatusAction(target: string) {
    if (isCreate) submitDraft();
    else changeStatus(target);
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
    ...releasedArticles.map((a) => ({ value: String(a.id), label: `${formatObjectId(a.object_id)} · ${a.name}` })),
  ];
  const statusActions = orderActions(record.status, canRelease, releaseHint);
  const companyAddr = company ? [company.street, company.street_number].filter(Boolean).join(' ') : '';

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242). */}
      <DetailHeader
        icon={ClipboardList} iconBg="#EAF0F4" iconFg="#4A6572"
        eyebrow={!isCreate && record.reason === 'deviation' ? 'Abweichungsauftrag' : 'Auftrag'}
        title={orderName(record)} placeholder="Auftrag"
        objectId={record.object_id}
        // Der Auftrag existiert noch nicht – die Nummer entsteht mit der Freigabe (#386).
        // Prägnant statt erklärend: ein Platzhalter in der Nummern-Zeile, die Erklärung im
        // Hover (Notiz #389). So sieht der Kopf aus wie jeder andere Auftragskopf.
        objectIdText={isCreate ? '—' : undefined}
        objectIdHint={isCreate ? 'Die Objektnummer wird bei der Freigabe vergeben' : undefined}
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
        status={orderStatus(isCreate ? { status: 'draft' } : record)}
        // **Kein «Abbrechen»** (Notiz #389): verworfen wird, indem man woanders hinklickt –
        // der Entwurf lebt nur im Browser und hinterlässt nichts. Ein Knopf dafür wäre ein
        // zweiter Weg für etwas, das ohnehin von selbst passiert.
        right={demandEditable && !isCreate ? <SaveIndicator saving={saving} flash={flash} /> : undefined}
        actions={(
          <>
            {!isCreate && record.object_id != null && (
              <>
                <HeaderSep />
                <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
                  onClick={() => printObjectLabel(record.object_id as number, record.article_name ?? 'Auftrag', 'Auftrag')}>
                  <QrCode size={15} />
                </button>
              </>
            )}
            {/* Status-Aktion («Freigeben») bei den übrigen Objekt-Aktionen statt rechts
                am Status: eine Aktion gehört zu den Aktionen, der Status zeigt nur an.
                Beim Entwurf ist sie zugleich die Anlage – er entsteht erst dabei (#386). */}
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
        )}
      >
        {!isCreate && (record.replaced_by_id != null || record.replaces_id != null) && (
          <ReplacedBanner replacedBy={record.replaced_by_id ?? null} replaces={record.replaces_id ?? null} />
        )}
        {/* Reiter (nur Personal, nur bei bestehendem Auftrag): Dokumente-Reiter dazu. */}
        {isStaff && (
          <DetailTabs<OrderTab> style={{ marginTop: 10 }} active={tab} onChange={setTab} tabs={[
            { key: 'auftrag', label: 'Auftrag', icon: ClipboardList },
            // Dokumente hängen an der Objektnummer – die gibt es erst mit der Freigabe.
            { key: 'docs', label: 'Dokumente', icon: FolderOpen, disabled: isCreate,
              hint: isCreate ? 'Verfügbar, sobald der Auftrag erteilt ist' : undefined },
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
                  source={goal} onSource={(s) => pickGoal(s)} onToggle={togglePin}
                  />
              )}

              {isCreate && releasedArticles.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--warning)', background: 'var(--warning-bg)', borderRadius: 8, padding: '8px 10px' }}>
                  Kein freigegebener Artikel vorhanden – nur freigegebene sind referenzierbar.
                </div>
              )}

              {/* Weitere Position – im Entwurf jederzeit, ob schon gespeichert oder nicht. */}
              {record?.status === 'draft' && (
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
              {isCreate && !demandValid && (
                <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Pflichtfelder: Artikel und Menge</div>
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
                      <> · {formatObjectId(d.instance_object_ids[0])}{d.instance_object_ids.length > 1 ? ` +${d.instance_object_ids.length - 1}` : ''}</>
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
        {isStaff && record?.status === 'draft' && !isSubOrder && <RecurrenceCard order={record} persist={persistRecurrence} />}

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
              {/* Im Entwurf schreibt derselbe Editor in den Browser-Speicher statt in die
                  API – den Auftrag gibt es ja noch nicht (#386). */}
              <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={suppliers}
                store={isCreate ? draftStore : undefined}
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
                // Alles, was kein Schritt für sich beansprucht, gehört dem Auftrag und steht
                // am Anfang des Flusses – EINE Liste, nicht drei nebeneinander.
                subOrders={[...(record.deviations ?? []), ...(record.supply_orders ?? []),
                            ...(record.provisionings ?? [])]}
                // **Ruht der Auftrag, ruht der ganze Fluss** (Notiz #378): kein Modul ist
                // dann «aktiv», keines lässt sich öffnen – farbig bleibt nur der
                // Unter-Auftrag, der zu klären ist. Dieselbe Regel wie im Backend
                // (`process.is_paused` → jeder Schritt blockiert, jede Ausführung 409);
                // sie war bisher nur nicht zu sehen.
                paused={record.paused === true}
                selectedId={currentStepId}
                onSelectStep={setSelStep}
                onOpenOrder={(oid) => nav?.(oid)}
                renderPanel={(step) => (
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
                  onAnswer={answerShortfall} candidates={shortfallCandidates} canReduce={hasSubjectShortfall}
                  affected={selfAffected} />
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

      {/* **Die Unterdeckungs-Frage zur Freigabe** (Notiz #370) – dasselbe Fenster wie am
          laufenden Auftrag, nur zu dem Zeitpunkt, an dem die Auswahl feststeht. */}
      {pendingRelease && (
        <ShortfallDialog busy={statusBusy} affected={isCreate ? draftAffects : (record?.affects ?? [])}
          onAnswer={(a) => (isCreate ? submitDraft(a) : changeStatus(pendingRelease.target, a))}
          onClose={() => setPendingRelease(null)} />
      )}

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
function ProcessHoldNotice({ missing, canAct, busy, error, candidates, canReduce, affected, onAnswer }: {
  missing?: string;
  canAct: boolean;
  busy: boolean;
  error: string | null;
  candidates: { object_id: number; quantity: number }[];
  canReduce: boolean;
  affected: AffectedOrder[];
  onAnswer: (answer: ShortfallAnswer, instanceObjectIds?: number[]) => void;
}) {
  const [open, setOpen] = useState(false);
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
        <ShortfallDialog candidates={candidates} canReduce={canReduce} busy={busy} error={error}
          affected={affected}
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
  canProduce, produceHint, articleSelect, qtyInput,
}: {
  line?: PinLine;
  unit: string;
  title?: string;
  articleObjectId?: number | null;
  qty: string;
  source: OrderGoal;
  onSource: (s: OrderGoal) => void;
  onToggle: (line: PinLine, share: Share, qty: number, qtyOnly?: boolean) => void;
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
  const picked = line?.pickedQty ?? 0;
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
      : { text: `${picked}/${req} ${unit} gewählt`,
          warn: picked < req ? 'Auswahl unvollständig' : null };

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
/**
 * Die beanspruchte **Menge** einer gewählten Instanz – im Chip, direkt neben der Nummer.
 *
 * Zwei Dinge, die vorher fehlten und zusammen eine unverständliche Fehlermeldung ergaben
 * (Testnotiz #373): Getippt wird in ein Feld, das bereits eine Zahl enthält – wer in «2»
 * hineinschreibt, erzeugt für einen Moment «21». Ging das direkt an den Server, antwortete
 * er «Instanz … hat nur 2 – mehr lässt sich nicht wählen», obwohl niemand 21 wollte.
 *
 * Darum: die Eingabe lebt lokal, wird auf das **Machbare gekappt** und erst beim Verlassen
 * (bzw. mit Enter) übernommen. Der Server prüft weiterhin – aber als Netz, nicht als
 * Frühwarnung bei jedem Tastendruck.
 */
function QtyChip({ value, max, tone, label, onCommit }: {
  value: number; max: number; tone: string; label: string; onCommit: (v: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? String(value);
  function commit() {
    const v = Math.min(max, Number(draft ?? shown) || 0);
    setDraft(null);
    if (v > 0 && v !== value) onCommit(v);
  }
  return (
    <input value={shown} onChange={(e) => setDraft(numericOnly(e.target.value))}
      onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
      {...numericInputProps} aria-label={label}
      style={{ width: 46, textAlign: 'center', border: `1px solid ${tone}`,
        borderRadius: 999, background: '#fff', color: tone, font: 'inherit',
        padding: '1px 4px', outline: 'none' }} />
  );
}

function PinPicker({ line, onToggle, bare }: {
  line: PinLine;
  /** Anteil an-/abwählen bzw. – mit ``qtyOnly`` – nur die beanspruchte Menge ändern. */
  onToggle: (line: PinLine, share: Share, qty: number, qtyOnly?: boolean) => void;
  bare?: boolean;
}) {
  // Suche nach Instanznummer: bei ein paar Anteilen sucht das Auge, bei ein paar hundert
  // nicht mehr. Das Feld erscheint darum erst, wenn die Liste es rechtfertigt.
  const [q, setQ] = useState('');
  const SEARCH_FROM = 8;
  const needle = q.trim().replace(/\D/g, '');
  const rows = needle
    ? line.shares.filter((sh) => String(sh.instanceObjectId).includes(needle))
    : line.shares;
  // Welche Sorte wird gerade gewählt? Aus der Auswahl abgeleitet, kein Schalter.
  const chosen = line.shares.filter((sh) => isPicked(line, sh));
  const picking: PinKind | null = chosen.length === 0 ? null : chosen[0].kind;

  const body = (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {line.shares.length >= SEARCH_FROM && (
          <div style={{ position: 'relative', flex: 1, minWidth: 150 }}>
            <input value={q} onChange={(e) => setQ(numericOnly(e.target.value, { decimals: false }))}
              placeholder="Instanznummer suchen…" {...numericInputProps}
              className="w-full rounded-md border bg-white px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
              style={{ borderColor: 'var(--border-1)', paddingRight: 26 }} />
            <Search size={13} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-4)', pointerEvents: 'none' }} />
          </div>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 700, color: line.pickedQty === line.reqQty ? 'var(--success)' : 'var(--warning)' }}>
          {line.pickedQty} / {line.reqQty} {line.unit} gewählt
        </span>
      </div>
      {line.shares.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine verfügbaren Instanzen.</div>
      ) : rows.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine Instanz mit «{q}».</div>
      ) : (
        // **Eine Zeile je Anteil** (nicht je Instanz): eine Charge, an der zwei Aufträge
        // hängen, steht zweimal da – einmal je Halter. Damit sagt der Klick zugleich, WEM
        // die Menge weggenommen wird; das Backend muss nicht mehr raten.
        <div style={{ display: 'flex', flexDirection: 'column', maxHeight: 240, overflowY: 'auto',
                      border: '1px solid var(--border-1)', borderRadius: 8, background: '#fff' }}>
          {rows.map((sh, idx) => {
            const cfg = PIN_KIND[sh.kind];
            const cur = pickOf(line, sh);
            const sel = cur != null;
            // Voreingestellt ist, was noch fehlt – höchstens aber, was der Anteil hergibt.
            const want = sel ? (cur.quantity ?? sh.capacity)
                             : Math.min(sh.capacity, Math.max(line.reqQty - line.pickedQty, 0)) || sh.capacity;
            const atLimit = !sel && line.pickedQty >= line.reqQty && line.reqQty > 0;
            // **Kein Mischmasch** (Notiz #355): sobald der erste Anteil gewählt ist, steht die
            // Art des Auftrags fest. Die anderen Sorten sind dann gesperrt (das Backend weist
            // sie ohnehin ab); der Hover sagt, warum.
            const wrongKind = !sel && picking != null && picking !== sh.kind;
            const off = atLimit || wrongKind;
            return (
              <div key={sh.key} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', fontSize: 12.5,
                borderTop: idx === 0 ? 'none' : '1px solid var(--border-1)',
                background: sel ? cfg.bg : 'transparent', opacity: off ? 0.4 : 1,
              }}>
                <button type="button" disabled={off} onClick={() => onToggle(line, sh, want)}
                  title={wrongKind ? `${picking ? PIN_KIND[picking].mix : ''} – nicht mit anderen Sorten mischbar`
                    : atLimit ? 'Die Menge ist bereits beisammen' : cfg.hint}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0,
                    border: 'none', background: 'none', font: 'inherit', color: 'inherit',
                    padding: 0, textAlign: 'left', cursor: off ? 'not-allowed' : 'pointer' }}>
                  {sel ? <CheckCircle2 size={13} style={{ color: cfg.tone, flexShrink: 0 }} />
                       : <span style={{ width: 7, height: 7, borderRadius: 999, background: cfg.tone, flexShrink: 0 }} />}
                  {/* **Instanz XY im Auftrag ZZ** (Notiz #396) – zwei Objektnummern, und
                      welche welche ist, sagt das Symbol davor. Der Name des Halters stand
                      hier früher ausgeschrieben; er IST aber der Artikelname und damit in
                      jeder Zeile derselbe – er sagte also nichts und las sich wie ein Artikel. */}
                  <Boxes size={12} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
                  <span title={`Instanz ${formatObjectId(sh.instanceObjectId)}`}
                        style={{ font: 'var(--mono-sm)', color: 'var(--fg-2)' }}>
                    {formatObjectId(sh.instanceObjectId)}
                  </span>
                  <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 5,
                                 color: sh.holderObjectId != null ? cfg.tone : 'var(--fg-4)',
                                 overflow: 'hidden', whiteSpace: 'nowrap' }}
                        title={sh.holderObjectId != null
                          ? `Gehört ${sh.holderName || 'Auftrag'} ${formatObjectId(sh.holderObjectId)}`
                          : 'Gehört niemandem – frei am Lager'}>
                    {sh.holderObjectId != null ? (
                      <>
                        {sh.kind === 'bound' ? <TriangleAlert size={12} /> : <ClipboardList size={12} />}
                        <span style={{ font: 'var(--mono-sm)' }}>{formatObjectId(sh.holderObjectId)}</span>
                      </>
                    ) : 'frei'}
                  </span>
                </button>
                {/* Die Menge steht rechts – gewählt als Feld, sonst als blosse Angabe. */}
                {sel && sh.capacity > 1 ? (
                  <QtyChip value={cur.quantity ?? sh.capacity} max={sh.capacity} tone={cfg.tone}
                    label={`Menge aus ${formatObjectId(sh.instanceObjectId)}`}
                    onCommit={(v) => onToggle(line, sh, v, true)} />
                ) : (
                  <span style={{ color: 'var(--fg-3)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
                    {sh.quantity} {line.unit}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
  if (bare) return <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{body}</div>;
  return <div style={cardStyle}>{body}</div>;
}

/** Der gewählte Anteil (oder ``null``) – EINE Stelle, an der Auswahl und Zeile zueinanderfinden. */
function pickOf(line: PinLine, share: Share): InstancePickInput | null {
  return line.picked.find(
    (p) => shareKey(p.instance_object_id, p.from_order_object_id ?? null) === share.key) ?? null;
}
const isPicked = (line: PinLine, share: Share) => pickOf(line, share) != null;

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
          options={[{ value: '', label: '— Artikel wählen —' }, ...options.map((a) => ({ value: String(a.id), label: `${formatObjectId(a.object_id)} · ${a.name}` }))]} />
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
/** Die drei Werte, die «wiederkehrend» ausmachen – leer/0 = einmalig. */
type Recurrence = Pick<Order, 'recurrence_active' | 'recurrence_interval_days'
  | 'recurrence_lead_time_days' | 'recurrence_anchor'>;

function RecurrenceCard({ order, persist }: {
  // **Wohin** die Wiederkehr geschrieben wird, ist Sache des Aufrufers – in die API oder
  // in den Entwurf im Browser (#386). Dieselbe Trennung wie beim Schritt-Editor.
  order: Order; persist: (v: Recurrence) => Promise<void>;
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
      await persist({
        recurrence_active: active,
        recurrence_interval_days: active ? days : null,
        recurrence_lead_time_days: active ? Math.max(0, Math.trunc(Number(lead) || 0)) : 0,
        recurrence_anchor: active && anchor ? anchor : null,
      });
      setSavedSig(sig);
      setFlash(true); setTimeout(() => setFlash(false), 700);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
  }, [active, days, lead, anchor, sig, persist]);

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
