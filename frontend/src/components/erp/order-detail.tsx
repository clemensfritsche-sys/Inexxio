'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ClipboardList, Layers, MessageSquareText } from 'lucide-react';
import { api, type ApiError } from '@/lib/api';
import type {
  ArticleOption, ArticleProcess, CapturePoint, Order, OrderSummary, PlaceRef,
  RelatedOrder, StepWork,
  PurchaseEmbed,
} from '@/types';
import { orderStatus } from '@/lib/record-status';
import { DetailHeader, HeaderAction } from '@/components/erp/fields';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { LabelButton } from '@/components/scan/object-label';
import {
  DRAFT_OBJECT_ID, EMPTY_GRAPH, PROCESS_MAXW, StepCard, definitionGraph,
  type DiagramStep,
  type JourneyOrigin,
} from '@/components/erp/process-diagram';
import { ProcessColumns, toDiagramSteps } from '@/components/erp/process-columns';
import { ProcessDesigner } from '@/components/erp/process-designer';
import {
  DefinitionLines, LAGER, NEU, emptyLine, toPayload, type DefinitionLine,
} from '@/components/erp/definition-lines';
import { END_BEFORE } from '@/lib/process-status';
import { CaptureWork } from '@/components/erp/capture-work';
import { PurchaseWork } from '@/components/erp/purchase-work';
import { PlaceTrail } from '@/components/erp/place-trail';
import { moduleIcon } from '@/lib/modules';
import { StepRecord } from '@/components/erp/step-record';
import { CAPTURE_ICON, blankModule, toModulePayload, type ModuleDraft } from '@/lib/modules';

// Genau EIN Reiter. Er steht hier oben, weil es dabei bleibt: der Auftrag bekommt
// keine weiteren – auch keine leeren oder deaktivierten.
const TABS = [{ key: 'auftrag' as const, label: 'Auftrag', icon: ClipboardList }];

/**
 * Auftrag – Detailfenster.
 *
 * **Der Entwurf lebt nur hier.** `record === null` heisst: in der Datenbank steht nichts,
 * keine Entwurfs-Zeile, keine vorreservierte Objektnummer, kein Autosave. Wer das Fenster
 * verlässt, lässt keine Spur.
 *
 * **Anlegen ist Freigeben.** Es gibt keinen «Speichern»-Zwischenschritt: der Klick auf
 * «Freigeben» legt den Auftrag an, vergibt die Objektnummer, prüft die Exklusivität,
 * **erzeugt die neuen Einzelinstanzen**, schickt die Stücke durch das Start-Objekt und
 * loggt – alles in einer Transaktion (PROCESS_CORE.md §6.3). Danach ist die Struktur
 * eingefroren.
 *
 * Ob freigegeben werden darf, entscheidet der Server (`POST /erp/orders/validate` →
 * `services/orders.validate_draft`). Die Oberfläche formuliert die Regel nicht nach,
 * sie fragt sie ab: sonst gäbe es zwei Massstäbe für dieselbe Frage.
 */
/**
 * **Ein Entwurf mit bereits gewählter Einzelinstanz** (Abweichungsauftrag §3.1).
 *
 * Mehr ist eine «Abweichung» nicht: derselbe Entwurf, derselbe Editor, dieselbe Freigabe –
 * das Stück steht nur schon drin. Ob daraus eine Abweichung wird, entscheidet sich beim
 * Freigeben und ergibt sich aus dem Zustand des Stücks, nicht aus diesem Seed.
 */
export interface OrderSeed {
  articleObjectId: number;
  /**
   * **Nur beim Auslöser am Stück** (§3.1). Der Shortcut am Artikel (#690) merkt bewusst
   * nur den Artikel vor: wie viel, woher und mit welchem Ablauf ist die Entscheidung,
   * und die trifft der Mensch. Ein reiner Shortcut, kein zweiter Anlagepfad.
   */
  unitNumbers?: string[];
  /**
   * In welchem Auftrag das Stück lief, als der Shortcut es griff. Das ist keine
   * Zusatzinfo, sondern die **Absicht**: «ich hole es aus diesem Auftrag». Der Server
   * prüft sie bei der Freigabe – wechselt das Stück vorher den Auftrag, bricht sie ab,
   * statt still etwas anderes zu tun (`UnitPick.from_order`).
   */
  fromOrder?: number | null;
  /**
   * **Wie viel** – nur, wo die Menge aus der Sache folgt und nicht aus einer Vermutung:
   * «12 Schrauben holen» weiss, dass es zwölf sind. Der Shortcut am Artikel merkt sie
   * bewusst NICHT vor (#690) – dort ist sie eine Entscheidung.
   */
  quantity?: number;
  /**
   * **Ein vorbelegter Ablauf.** Ein «Holen lassen» ist ein ganz gewöhnlicher Auftrag mit
   * einem Bewegen-Modul – der Entwurf bringt es mit, statt es den Menschen ein zweites
   * Mal eintippen zu lassen. Änderbar wie jedes andere Modul; es ist eine Eingabehilfe,
   * keine Festlegung.
   */
  steps?: { moduleType: string; target?: number }[];
}

export function OrderDetail({ record, seed, onSaved, onDeviate, onBack }: {
  /** ``null`` ⇒ Entwurf (existiert nur im Browser). Sonst genügt die **Feed-Zeile** –
   *  das Detail lädt sich selbst nach (siehe unten). */
  record: OrderSummary | Order | null;
  /** Nur beim Entwurf: eine vorgewählte Einzelinstanz. */
  seed?: OrderSeed | null;
  onSaved: (o: Order) => void;
  /** Ein Stück im Prozess soll eine Abweichung bekommen – die Seite öffnet den Entwurf. */
  onDeviate?: (seed: OrderSeed) => void;
  onBack?: () => void;
}) {
  const isDraft = record === null;

  const [lines, setLines] = useState<DefinitionLine[]>(() => {
    if (!seed) return [emptyLine(1)];
    // Mit Stück: es steht schon in der Definition, Herkunft «Lager» folgt daraus.
    // Ohne Stück (Artikel-Shortcut): nur der Artikel – Menge und Herkunft bleiben offen.
    const picked = seed.unitNumbers ?? [];
    if (picked.length) {
      return [{ key: 1, articleObjectId: seed.articleObjectId, quantity: picked.length,
                origin: LAGER,
                units: picked.map((n) => ({ number: n, fromOrder: seed.fromOrder ?? null })),
                returns: true }];
    }
    // Mit Menge, ohne Stücke: «hol mir zwölf davon» – woher, entscheidet FIFO.
    return seed.quantity
      ? [{ ...emptyLine(1), articleObjectId: seed.articleObjectId,
           quantity: seed.quantity, origin: LAGER }]
      : [{ ...emptyLine(1), articleObjectId: seed.articleObjectId }];
  });
  const [steps, setSteps] = useState<ModuleDraft[]>(() =>
    (seed?.steps ?? []).map((m, i) => ({
      ...blankModule(i + 1, m.moduleType),
      target: m.target ? String(m.target) : '',
    })));
  const [missing, setMissing] = useState<string[] | null>(null);
  /**
   * **Die Vorschau der Quell-Aufträge** (Auftrag §2). Sie kommt aus derselben Ableitung
   * wie das echte Bild (`flow.build` mit `planned`) und aus derselben Anfrage wie die
   * Freigebbarkeit – ein zweiter Aufruf dafür wäre ein zweiter Stand desselben Entwurfs.
   */
  const [preview, setPreview] = useState<RelatedOrder[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<Order | null>(null);
  // Zählt hoch, wenn die Freigabe an einer veralteten Auswahl scheitert – der Picker holt
  // die Stückliste dann neu und zeigt, wo die Stücke jetzt liegen.
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(false);

  /**
   * **Das Detail lädt seinen Auftrag selbst.**
   *
   * Der Feed liefert bewusst nur eine Zusammenfassung (`OrderSummary`) – ohne Schritte,
   * Stücke und Historie; bei 5000 Stück ist das der Unterschied zwischen einer Liste und
   * einem Megabyte. Wer die Feed-Zeile als Detail rendert, zeigt darum einen laufenden
   * Prozess als leer: kein Modul, keine Einzelinstanzen, «nicht gestartet». Genau das
   * war zu sehen – die Erzeugung lief pünktlich, die Ansicht wusste nur nichts davon.
   *
   * Die Zeile aus dem Feed dient nur noch als Adresse (`object_id`).
   */
  const objectId = record?.object_id ?? null;
  useEffect(() => {
    if (objectId == null) { setLive(null); return; }
    let dead = false;
    setLoading(true);
    api.getOrder(objectId)
      .then((o) => { if (!dead) setLive(o); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [objectId]);

  const draft = useMemo(() => ({
    lines: toPayload(lines),
    steps: steps.map(toModulePayload),
  }), [lines, steps]);

  // Freigebbarkeit beim Server erfragen, nicht selbst behaupten.
  useEffect(() => {
    if (!isDraft) { setMissing(null); setPreview([]); return; }
    let dead = false;
    api.validateOrder(draft)
      .then((v) => {
        if (dead) return;
        setMissing(v.missing ?? []);
        setPreview(v.parents ?? []);
      })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [isDraft, draft]);

  async function release() {
    setBusy(true); setError(null);
    try {
      onSaved(await api.createOrder(draft));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      // **Ein veralteter Pick ist kein blosser Fehler, sondern eine neue Lage.** Der
      // Server nennt sie mit einem Code (nicht mit einem Satz, den jemand umformulieren
      // könnte); die Auswahl wird daraufhin gegen die Wirklichkeit nachgezogen.
      const detail = (e as ApiError)?.detail as { code?: string } | undefined;
      if (detail?.code === 'pick_stale') setRefreshKey((n) => n + 1);
    } finally {
      setBusy(false);
    }
  }

  const confirmStep = useCallback(async (stepId: number, instanceObjectId: number,
                                         verification: string,
                                         values: Record<string, Record<string, unknown>>,
                                         sources: number[] = [],
                                         place: number | null = null,
                                         transport: string = '') => {
    if (!live) return;
    setBusy(true); setError(null);
    try {
      setLive(await api.confirmStep(live.object_id, stepId, values,
                                    instanceObjectId, verification, sources,
                                    place, transport));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [live]);

  /**
   * **Eine Handlung am Beschaffungs-Beleg** – derselbe Weg wie das Bestätigen: ein
   * Aufruf, die Antwort IST der neue Auftrag. Kein eigener Zustand daneben, der
   * veralten könnte.
   */
  const runPurchase = useCallback(async (
    stepId: number, body: { action: string } & Record<string, unknown>,
  ) => {
    if (!live) return;
    setBusy(true); setError(null);
    try {
      setLive(await api.updatePurchase(live.object_id, stepId, body));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [live]);

  const blocked = missing != null && missing.length > 0;
  const shown = live;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        type="order"
        // **Die Abweichung ist ein Zeichen am Symbol** (#699) – dieselbe Komponente wie
        // im Feed. Zwei Implementierungen driften garantiert auseinander (#688).
        deviation={shown?.is_deviation ?? false}
        title={shown?.name ?? null}
        placeholder="Neuer Auftrag"
        objectId={shown?.object_id ?? record?.object_id ?? null}
        objectIdText={isDraft ? '—' : undefined}
        objectIdHint={isDraft
          ? 'Die Objektnummer entsteht erst mit der Freigabe. Bis dahin existiert dieser Auftrag nur in diesem Fenster.'
          : undefined}
        status={shown ? orderStatus(shown) : undefined}
        actions={isDraft ? (
          <HeaderAction
            label="Freigeben"
            // Kein stummes Nichts-Passiert: der Knopf sagt, was noch fehlt.
            hint={blocked ? `Es fehlt: ${missing!.join(' · ')}` : 'Legt den Auftrag an und startet den Prozess'}
            disabled={busy || blocked || missing == null}
            onClick={release}
          />
        ) : shown?.object_id != null ? (
          <LabelButton objectId={shown.object_id} title={shown.name} kind="Auftrag" />
        ) : undefined}
        onBack={onBack}
        tabs={<DetailTabs tabs={TABS} active="auftrag" onChange={() => {}} />}
      />

      <div className="flex-1 p-5" style={{ background: 'var(--bg-2)' }}>
        {error && (
          <p className="mb-3 text-sm max-w-[880px] mx-auto px-3 py-2 rounded-ds-lg"
            style={{ color: 'var(--danger)', background: 'var(--danger-bg)' }}>
            {error}
          </p>
        )}

        {/* **Kein Mass von hier.** Jedes Prozessbild bringt seines mit (#684) – der
            Entwurf ist eine Spalte, der laufende Auftrag sind bis zu drei. Eine Zahl an
            dieser Stelle wäre der zweite Stand, aus dem der gemeldete Breitenunterschied
            entstanden ist. */}
        {isDraft ? (
          <DraftView lines={lines} setLines={setLines} steps={steps} setSteps={setSteps}
            refreshKey={refreshKey} parents={preview} />
        ) : shown ? (
          <RunView order={shown} busy={busy} onConfirm={confirmStep}
            onPurchase={runPurchase} onDeviate={onDeviate} />
        ) : (
          <p className="text-sm text-center" style={{ color: 'var(--fg-4)' }}>
            {loading ? 'Lädt …' : null}
          </p>
        )}

      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Entwurf — Modus «definition»
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Der Prozess folgt aus der Herkunft.**
 *
 * Sobald eine Zeile «Neu» trägt, ist der Prozess die **Vorlage des Artikels** – als
 * Kopie, mit Versionsstempel, und hier nur zu sehen, nicht zu ändern. Sie zu bearbeiten
 * hiesse, einen Stempel auf etwas zu setzen, das danach nicht mehr die Vorlage ist.
 * Ändern geht am Artikel, unter «Spezifikation».
 *
 * Ein reiner «Lager»-Auftrag greift auf Vorhandenes zu – was damit geschehen soll, weiss
 * nur dieser eine Auftrag. Dort wird frei modelliert.
 */
function DraftView({ lines, setLines, steps, setSteps, refreshKey, parents }: {
  lines: DefinitionLine[]; setLines: (l: DefinitionLine[]) => void;
  steps: ModuleDraft[]; setSteps: (s: ModuleDraft[]) => void;
  /** Hochgezählt, wenn die Freigabe an einer veralteten Auswahl scheitert. */
  refreshKey: number;
  /** Die Quell-Aufträge, wie sie nach der Freigabe aussähen (Auftrag §2). */
  parents: RelatedOrder[];
}) {
  const [articles, setArticles] = useState<ArticleOption[]>([]);
  const [template, setTemplate] = useState<ArticleProcess | null>(null);

  // Welcher Artikel bringt den Prozess mit? Der erste mit Herkunft «Neu».
  const sourceArticle = useMemo(
    () => lines.find((l) => l.origin === NEU && l.articleObjectId !== null)?.articleObjectId ?? null,
    [lines],
  );

  useEffect(() => {
    if (sourceArticle === null) { setTemplate(null); return; }
    let dead = false;
    api.getArticleProcess(sourceArticle)
      .then((p) => { if (!dead) setTemplate(p); })
      .catch(() => { if (!dead) setTemplate(null); });
    return () => { dead = true; };
  }, [sourceArticle]);

  const mirrored: DiagramStep[] | null = useMemo(() => {
    if (!template) return null;
    return (template.steps ?? []).map((s) => ({
      id: s.id, moduleType: s.module_type, label: s.label,
      tone: s.tone, terminal: s.terminal,
    }));
  }, [template]);

  const isMake = sourceArticle !== null;
  const articleName = articles.find((a) => a.object_id === sourceArticle)?.name;

  /**
   * **Die Rückführung schaltet man am Ziel** (§5) – und das Ziel ist seit der Vorschau
   * der Quell-Auftrag selbst, nicht mehr eine Ersatz-Pille unter dem Ende.
   *
   * Die Entscheidung hängt an der **Definitionszeile** (`returns`), gefragt wird sie am
   * **Auftrag**: umgeschaltet wird darum jede Zeile, die aus ihm etwas nimmt. Das ist
   * dieselbe Zusammenfassung, die der Server für die Vorschau macht (ein Auftrag kehrt
   * zurück, wenn irgendeine seiner Zeilen zurückführt) – zwei Lesarten davon ergäben
   * einen Klick, der die Linie nicht bewegt.
   */
  const toggleReturn = useCallback((parentObjectId: number) => {
    const takes = (l: DefinitionLine) => l.units.some((u) => u.fromOrder === parentObjectId);
    const on = lines.some((l) => takes(l) && l.returns);
    setLines(lines.map((l) => (takes(l) ? { ...l, returns: !on } : l)));
  }, [lines, setLines]);

  const head = (
    <DefinitionLines lines={lines} setLines={setLines} refreshKey={refreshKey}
      onArticlesChosen={setArticles} />
  );

  // Bringt eine Zeile «Neu» mit, ist der Prozess die **Vorlage des Artikels** – dann nur
  // ansehen. Sonst wird hier modelliert, mit demselben Editor wie am Artikel.
  return (
    <>
      {isMake ? (
        <ProcessColumns
          mid={{
            objectId: DRAFT_OBJECT_ID,
            graph: definitionGraph(mirrored ?? []),
            steps: mirrored ?? [],
            mode: 'definition',
            endStatus: END_BEFORE,
            head,
          }}
          parents={parents}
          onToggleReturn={toggleReturn}
        />
      ) : (
        <ProcessDesigner
          modules={steps}
          onChange={setSteps}
          parents={parents}
          onToggleReturn={toggleReturn}
          head={head}
        />
      )}

      {isMake ? (
        <p className="mt-3 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
          {mirrored?.length
            ? <>Erzeugungsprozess von <strong>{articleName}</strong> (Stand {template?.version}).
              Er wird bei der Freigabe als Kopie übernommen – geändert wird er am Artikel.</>
            : 'Lädt den Erzeugungsprozess …'}
        </p>
      ) : null}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Freigegeben — Modus «ausfuehrung»
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Der Beschaffungs-Beleg umschliesst den Scan — oder es gibt ihn nicht.**
 *
 * Ein Bauteil statt einer Bedingung an der Aufrufstelle: `purchase` ist bei jedem
 * anderen Modultyp leer, und dann steht hier schlicht der Scan. Dieselbe Bauart wie
 * `transports` und `needs` – die Oberfläche fragt nie nach dem Modultyp.
 */
function Wrapped({ purchase, busy, active, onAction, children }: {
  purchase: PurchaseEmbed | null;
  busy: boolean;
  active: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
  children: React.ReactNode;
}) {
  if (!purchase) return <>{children}</>;
  return (
    <PurchaseWork purchase={purchase} busy={busy} active={active} onAction={onAction}>
      {children}
    </PurchaseWork>
  );
}


function RunView({ order, busy, onConfirm, onPurchase, onDeviate }: {
  order: Order; busy: boolean;
  onConfirm: (stepId: number, instanceObjectId: number, verification: string,
              values: Record<string, Record<string, unknown>>,
              sources: number[], place: number | null, transport: string) => void;
  onPurchase: (stepId: number, body: { action: string } & Record<string, unknown>) => void;
  onDeviate?: (seed: OrderSeed) => void;
}) {
  const steps: DiagramStep[] = toDiagramSteps(order.steps);
  // Die einzelnen Nummern kommen erst beim Aufklappen – bei 5000 Stück ist das der
  // Unterschied zwischen einer Antwort und einem Megabyte.
  /**
   * ►►► Die **restriktivere Variante** zur offenen Frage (Abweichungsauftrag §5) ◄◄◄
   *
   * Solange im aktiven Modul erfasst wird, lässt sich keine Abweichung auslösen. Der
   * Server kann das nicht prüfen: eine begonnene Erfassung ist nirgends gespeichert (sie
   * entsteht erst beim Bestätigen). Diese Sperre ist darum **hier** – und sie ist
   * bewusst die strengere von zwei möglichen Antworten, bis die Frage entschieden ist.
   * Die dauerhafte Regel gehört an den Modultyp (`domain/modules.units_may_leave`).
   */
  const [entryStarted, setEntryStarted] = useState(false);

  /**
   * **Die eine Herkunft, die nicht im Log steht.** Ein Erzeugungsauftrag hat keinen
   * Vorgänger – seine Stücke entstehen bei der Freigabe. Alles andere kam aus einem
   * Auftrag und steht darum in `journey_in`; zusammen decken beide jedes Stück ab
   * (gemessen). Genau deshalb ist der frühere Definitions-Container weg: er sagte ein
   * zweites Mal, was am Baum steht.
   */
  const origins: JourneyOrigin[] = (order.lines ?? [])
    .filter((ln) => ln.origin === NEU)
    .map((ln) => ({ label: ln.article_name ?? 'Artikel', count: ln.quantity }));

  const expand = useCallback(async (edgeId: string) => {
    const page = await api.getOrderUnits(order.object_id, edgeId, 100, 0);
    // **Der Zustand bleibt am Stück.** Der Server sendet ihn; ihn hier wegzuwerfen war
    // der Grund, warum der Abweichungstrigger auch an einem verschrotteten Stück stand.
    return (page.units ?? []).map((u) => ({
      number: u.number, startedAt: u.started_at, status: u.status,
    }));
  }, [order.object_id]);

  // ►► **Ein Modul-Körper, zwei Wege dorthin.** ◄◄
  //
  // Er hängt hier und nicht im Diagramm, weil ihn zwei Ansichten brauchen: der volle
  // Prozess in der Mitte – und die **Lieferanten-Sicht**, die kein Prozessbild bekommt
  // (sein Beleg ist seine Sache, der Lauf des Auftrags nicht). Zwei Körper wären zwei
  // Darstellungen desselben Moduls, und die laufen auseinander.
  //
  // `internal` sagt, ob dies die **volle** Ansicht ist – und das ist keine Rollenabfrage,
  // sondern die Aussage der Aufrufstelle über sich selbst: das Modul-Protokoll
  // (`StepRecord`) ist der interne Lauf, sein Endpunkt ist Personal-only, und in einer
  // verengten Antwort hat er nichts zu suchen. Was ein Lieferant im Modul **tun** darf,
  // entscheidet dagegen der Beleg selbst (`purchase.can`).
  const stepBody = (step: DiagramStep, isActive: boolean, internal: boolean) => (
    <div className="flex flex-col gap-2.5">
      <Reason text={stepInfo(order, step.id)?.reason} />
      {/* Der Beschaffungs-Beleg umschliesst den Scan: der Wareneingang IST die
          Bestätigung, die jedes Modul abschliesst. Bei jedem anderen Modultyp ist
          `purchase` leer und es bleibt beim Inhalt allein. */}
      <Wrapped purchase={stepInfo(order, step.id)?.purchase ?? null} busy={busy}
        active={isActive} onAction={(body) => onPurchase(step.id, body)}>
        {isActive ? (
          // **Die Arbeit steht je Instanz da** – weil ein Vorgang eine Instanz ist
          // (Scan-Regel §3).
          <CaptureWork
            orderObjectId={order.object_id}
            stepId={step.id}
            points={pointsOf(order, step.id)}
            action={stepInfo(order, step.id)?.action ?? ''}
            work={workOf(order, step.id)}
            needs={stepInfo(order, step.id)?.needs ?? []}
            // **Wohin und womit** – beides kommt vom Server mit dem Schritt.
            target={stepInfo(order, step.id)?.target ?? null}
            transports={stepInfo(order, step.id)?.transports ?? []}
            busy={busy}
            onDirty={setEntryStarted}
            onDeviate={onDeviate}
            onConfirm={(instanceObjectId, verification, values, sources, place, transport) =>
              onConfirm(step.id, instanceObjectId, verification, values, sources,
                        place, transport)}
          />
        ) : (
          <PointList points={pointsOf(order, step.id)} sample={sampleOf(order, step.id)}
            action={stepInfo(order, step.id)?.action}
            reason={stepInfo(order, step.id)?.reason}
            moduleType={step.moduleType}
            target={(stepInfo(order, step.id)?.transports ?? []).length > 0
              ? (stepInfo(order, step.id)?.target ?? null)
              : undefined} />
        )}
      </Wrapped>
      {/* **Was in ihm passiert ist** (#717) – zentral, kein Protokoll je Modultyp. */}
      {internal && !isActive && <StepRecord orderObjectId={order.object_id} stepId={step.id} />}
    </div>
  );

  // **Ohne Prozessbild: die Module allein** – dieselbe Karte, nur ohne Achse. Der Graph
  // fehlt genau dann, wenn die Antwort für einen Lieferanten verengt wurde
  // (`orders._mine_only`); gezeichnet wird trotzdem `StepCard`, nicht ein Nachbau.
  if (!(order.flow?.nodes ?? []).length) {
    return (
      <div className="flex flex-col gap-3" style={{ maxWidth: PROCESS_MAXW, margin: '0 auto' }}>
        {steps.map((step) => (
          <StepCard key={step.id} step={step} dimmed={false} defaultOpen
            active={step.id === order.active_step_id}>
            {stepBody(step, step.id === order.active_step_id, false)}
          </StepCard>
        ))}
      </div>
    );
  }

  return (
    <>
      <ProcessColumns
        mid={{
          objectId: order.object_id,
          graph: order.flow ?? EMPTY_GRAPH,
          steps,
          mode: 'ausfuehrung',
          activeStepId: order.active_step_id ?? null,
          endStatus: order.end_status,
          onExpand: expand,
          onDeviate: onDeviate
            ? (unitNumber) => { void startDeviation(unitNumber, order.object_id, onDeviate); }
            : undefined,
          deviateBlocked: entryStarted
            ? 'Im aktiven Modul wurde bereits erfasst. Erst bestätigen – oder das Fenster neu laden, dann ist die Eingabe verworfen.'
            : undefined,
          // **Die Historie steht am Objekt** (§5) – und nur in der Mitte: von einem
          // Nachbarn ist sie gar nicht geladen, und sie gehört in seinen Datensatz.
          events: order.events ?? [],
          eventTotal: order.event_count ?? undefined,
          // **Jedes Modul zeigt, was es tut** (Testnotiz #696) – das aktive als Formular,
          // die übrigen als das, was in ihnen definiert ist. Ob die Karte auf- oder
          // zugeklappt startet und ob sie gesperrt ist, entscheidet das Diagramm; hier
          // steht nur der Inhalt.
          // ►► **Ein Modul zeigt seine Sache in JEDEM Zustand.** ◄◄
          //
          // Vorher standen hier zwei völlig verschiedene Körper – aktiv das Formular,
          // sonst eine **Aufzählung** dessen, was ein Modul tragen kann (Punkte, Umfang,
          // Verb, Grund, Ziel). Diese Liste musste mit jedem neuen Modul-Fakt wachsen,
          // und der Beschaffungs-Beleg stand nicht darin: ein abgeschlossenes Modul zeigte
          // von ihm **nichts**. Jetzt ist es EIN Körper, und `isActive` entscheidet allein,
          // ob **gehandelt** werden darf – nicht, ob etwas zu sehen ist.
          renderStep: (step, isActive) => stepBody(step, isActive, true),
        }}
        parents={order.parents ?? []}
        deviations={order.deviations ?? []}
        deviationTotal={order.deviation_total ?? 0}
        journeyIn={order.journey_in ?? []}
        journeyOut={order.journey_out ?? []}
        origins={origins}
      />
    </>
  );
}

/**
 * Was dieses Modul erfassen wird – seine eingefrorene Definition.
 *
 * Für ein Modul, das nicht an der Reihe ist: es soll zeigen, **was** es tut, ohne es tun
 * zu lassen. Die erfassten *Werte* eines erledigten Moduls stehen nicht hier, sondern in
 * der Historie – sie sind ein Ereignis, keine Eigenschaft des Moduls.
 */
/**
 * **Warum hier ausgesondert wird** – aus der Definition, nicht vom Band.
 *
 * Der Grund wird beim Modellieren gegeben (`domain/modules.Aussondern`) und ist damit
 * für jedes Stück derselbe. Er steht an der Ausführungsstelle, weil dort die Frage
 * gestellt wird – aber als **Auskunft**, nicht als Eingabefeld.
 */
function Reason({ text }: { text?: string | null }) {
  if (!text) return null;
  return (
    <p className="flex items-start gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
      <MessageSquareText size={13} style={{ flex: 'none', marginTop: 1, color: 'var(--fg-4)' }} />
      <span>{text}</span>
    </p>
  );
}

function PointList({ points, sample, action, reason, moduleType, target }: {
  points: CapturePoint[]; sample?: string; action?: string; reason?: string | null;
  /** Für das Symbol – aus derselben Zuordnung, aus der es auch die Palette nimmt. */
  moduleType?: string;
  /**
   * **Wohin dieses Modul bringt** – aus der Definition, bereits aufgelöst.
   *
   * `null` heisst bei einem Bewegungsmodul *nicht* «vergessen», sondern «wird beim
   * Ausführen gewählt». Beides muss dastehen: ein offenes Ziel, das aussieht wie eine
   * Lücke, liest sich als Fehler in der Definition.
   */
  target?: PlaceRef | null;
}) {
  // **Ein Modul ohne Erfassungspunkte hat trotzdem etwas zu sagen.** Das Aussondern
  // erfasst nichts – was es tut, steht in seinem Verb und warum in seinem Grund; das
  // Bewegen sagt zusätzlich, wohin. Ohne diese Zeilen stünde die Karte leer da.
  if (!points.length) {
    const Icon = moduleIcon(moduleType);
    return action ? (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
          <Icon size={13} style={{ color: 'var(--fg-4)' }} />
          <span>{action}</span>
        </div>
        {target !== undefined && (
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
            <span style={{ color: 'var(--fg-4)' }}>nach</span>
            {target
              ? <PlaceTrail place={{ holder: target, chain: [target] }} />
              : (
                <span className="text-fg-4"
                  data-tip="Dieses Modul hat kein festes Ziel – der Ausführende scannt, wohin die Stücke gehen.">
                  wird beim Ausführen gescannt
                </span>
              )}
          </div>
        )}
        <Reason text={reason} />
      </div>
    ) : null;
  }
  return (
    <div className="flex flex-col gap-1">
      {/* **Die Stichprobenregel gehört zur Definition** – sie sagt, an wie vielen Stücken
          erfasst wird. Der Satz kommt vom Server (`sampling.describe`); wie viele es
          konkret wurden, sagt erst die Ziehung am aktiven Modul. */}
      {sample && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-4)' }}>
          <Layers size={13} />
          <span>Stichprobe: {sample}</span>
        </div>
      )}
      {points.map((p) => {
        const Icon = CAPTURE_ICON[p.type] ?? CAPTURE_ICON.text;
        return (
          <div key={p.key} className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
            <Icon size={13} style={{ color: 'var(--fg-4)' }} />
            <span className="flex-1 min-w-0 truncate" style={{ color: 'var(--fg-2)' }}>{p.label}</span>
            {p.target != null && (
              <span className="ix-tnum">
                Soll {p.target}{p.tolerance ? ` ± ${p.tolerance}` : ''}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * **Wartet dieser Auftrag auf eine Rückführung?** Abgeleitet, nicht gespeichert – es
 * wartet, wer noch eine offene rückführende Verbindung hat. Steht hier nichts, wartet er
 * auf nichts; ein Platzhalter «wartet auf 0» wäre eine Zeile ohne Aussage.
 */

/**
 * **Welcher Artikel gehört zu diesem Stück?** Die Nummer sagt es zur Hälfte: ihr vorderer
 * Teil ist die Objektnummer der Instanz, und die Instanz kennt ihren Artikel. Gefragt wird
 * darum der bestehende Endpunkt – ein zweites Feld an der Stück-Antwort wäre eine Kopie,
 * die auseinanderlaufen kann.
 */
async function startDeviation(
  unitNumber: string, fromOrder: number, open: (seed: OrderSeed) => void,
) {
  const instanceId = Number(unitNumber.split('-')[0]);
  if (!Number.isInteger(instanceId)) return;
  const instance = await api.getInstance(instanceId);
  if (instance.article_object_id == null) return;
  // Woher das Stück kommt, weiss diese Stelle sicher: aus dem Auftrag, dessen Prozess
  // gerade offen ist. Genau das ist die Aussage, die der Server bei der Freigabe prüft.
  open({ articleObjectId: instance.article_object_id, unitNumbers: [unitNumber], fromOrder });
}

/** Das Modul eines Schritts, wie der Server es beschreibt – die eine Lesestelle. */
function stepInfo(order: Order, stepId: number) {
  return (order.steps ?? []).find((s) => s.id === stepId);
}

/** Die Stichprobenregel eines Moduls – als Satz, vom Server (`ProcessStepResponse.sample`). */
function sampleOf(order: Order, stepId: number): string | undefined {
  return stepInfo(order, stepId)?.sample;
}

/** Die Erfassungspunkte eines Moduls – aus seiner eingefrorenen Definition. */
function pointsOf(order: Order, stepId: number): CapturePoint[] {
  const step = (order.steps ?? []).find((s) => s.id === stepId);
  const cfg = step?.config as { points?: CapturePoint[] } | null | undefined;
  return cfg?.points ?? [];
}

/**
 * Wie viele Stücke stehen gerade davor – die Erfassung gilt für sie alle.
 *
 * Aus **derselben** Quelle wie das Bild (`order.flow`): eine Position ist eine Kante,
 * und die Kanten, die in dieses Modul münden, tragen sie. Eine zweite Liste daneben
 * hätte irgendwann eine andere Zahl genannt als das Diagramm daneben zeigt.
 */
function workOf(order: Order, stepId: number): StepWork[] {
  return order.steps?.find((s) => s.id === stepId)?.work ?? [];
}

/*
 * **Der Definitions-Container ist entfallen** (Punkt 6). Er sagte «3× Blech, neu
 * erzeugt» — dieselbe Auskunft, die jetzt oben am Baum steht: was hier entstanden ist,
 * als eigener Ast; was aus einem Auftrag kam, als Ast mit dessen Objektnummer. Beides
 * zusammen deckt jedes Stück ab (gemessen), also war es eine zweite Anzeige derselben
 * Sache — und die läuft irgendwann der ersten davon.
 */

/*
 * **Die History-Box ist entfallen** (Auftrag §5). Der Ereignis-Log bleibt vollständig –
 * aufgezeichnet wird unverändert, und der Server liefert ihn weiter. Nur der ORT ist ein
 * anderer: die Einträge stehen jetzt am **Prozessobjekt**, an dem sie passiert sind
 * (`process-diagram.historyTip`). Eine Liste am Fuss zwang dazu, jede Zeile erst dem
 * Objekt zuzuordnen; am Objekt selbst IST diese Zuordnung die Position.
 *
 * Entscheidend dabei: `start` und `end` tragen **kein** Modul (`step_id = null`) – ein
 * Hover nur an Modulen hätte die Hälfte des Logs unerreichbar gemacht. Alle drei
 * Objektarten tragen darum dieselbe Blase, und die Kappungs-Notiz («die letzten N von M»)
 * steht als letzte Zeile darin.
 */

