'use client';

import { useCallback, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Layers, MessageSquareText } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { qk, useDebouncedQuery } from '@/lib/queries';
import type {
  CapturePoint, Order, OrderSummary, PlaceRef,
  RelatedOrder, StepWork,
} from '@/types';
import { orderStatus } from '@/lib/record-status';
import { DetailBody, DetailHeader, HeaderAction, SectionSep } from '@/components/erp/detail-frame';
import { History } from '@/components/erp/history';
import { DocumentTiles } from '@/components/erp/documents';
import { LabelButton } from '@/components/scan/object-label';
import { EMPTY_GRAPH, definitionGraph, type DiagramStep, type JourneyOrigin } from '@/lib/process-graph';
import { DRAFT_OBJECT_ID, lookup } from '@/lib/vocab';
import { PROCESS_MAXW } from '@/components/erp/flow-column';
import { StepCard } from '@/components/erp/module-card';
import { ProcessColumns, toDiagramSteps } from '@/components/erp/process-columns';
import { ProcessDesigner } from '@/components/erp/process-designer';
import {
  DefinitionLines, LAGER, NEU, emptyLine, toPayload, type DefinitionLine,
} from '@/components/erp/definition-lines';
import { END_BEFORE, FREIGEGEBEN } from '@/lib/process-status';
import { CaptureWork } from '@/components/erp/capture-work';
import { BelegWork } from '@/components/erp/beleg-work';
import { PlaceTrail } from '@/components/erp/place-trail';
import { RUNTIME_CHOICE } from '@/lib/scan';
import { moduleIcon } from '@/lib/modules';
import { StepRecord } from '@/components/erp/step-record';
import { CAPTURE_ICON, blankModule, toModulePayload, type ModuleDraft } from '@/lib/modules';
import { LoopDraftCard, LoopRunCard, loopPayload, type LoopDraft } from '@/components/erp/loop-card';
import { Skeleton } from '@/components/erp/skeleton';
import { useAction } from '@/lib/use-action';
import { NOTHING } from '@/lib/when';

/**
 * Auftrag – Detailfenster.
 *
 * Der Entwurf lebt nur hier (`record === null`: keine Zeile, keine Nummer, kein Autosave).
 * **Anlegen ist Freigeben**: ein Klick legt an, vergibt die Nummer, prüft die Exklusivität,
 * erzeugt die Einzelinstanzen und schickt sie durch den Start – eine Transaktion
 * (PROCESS_CORE.md §6.3). Ob freigegeben werden darf, entscheidet der Server
 * (`services/orders.validate_draft`).
 */
/**
 * **Ein Entwurf mit bereits gewählter Einzelinstanz** (Abweichungsauftrag §3.1). Ob daraus
 * eine Abweichung wird, ergibt sich beim Freigeben aus dem Zustand des Stücks.
 */
export interface OrderSeed {
  articleObjectId: number;
  /** Nur beim Auslöser am Stück (§3.1); der Shortcut am Artikel merkt nur den Artikel vor. */
  unitNumbers?: string[];
  /**
   * In welchem Auftrag das Stück lief, als der Shortcut es griff – die Absicht. Wechselt das
   * Stück vorher den Auftrag, bricht die Freigabe ab (`UnitPick.from_order`).
   */
  fromOrder?: number | null;
  /** Wie viel – nur, wo die Menge aus der Sache folgt («12 Schrauben holen»). */
  quantity?: number;
  /** Ein vorbelegter Ablauf (z. B. ein Bewegen-Modul für «Holen lassen») – änderbar, eine Eingabehilfe. */
  steps?: { moduleType: string; target?: number }[];
}

export function OrderDetail({ record, seed, onSaved, onDeviate, onBack }: {
  /** ``null`` ⇒ Entwurf (nur im Browser). Sonst genügt die Feed-Zeile – das Detail lädt sich selbst. */
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
  // **Die Wiederholung lebt im Entwurf** – eingefroren wird sie mit der Freigabe.
  const [loop, setLoop] = useState<LoopDraft | null>(null);
  const { busy, error, run } = useAction();
  // Zählt hoch, wenn die Freigabe an einer veralteten Auswahl scheitert – der Picker holt
  // die Stückliste dann neu und zeigt, wo die Stücke jetzt liegen.
  const [refreshKey, setRefreshKey] = useState(0);

  /**
   * **Das Detail lädt seinen Auftrag selbst.** Der Feed liefert nur `OrderSummary` (ohne
   * Schritte, Stücke, Historie); die Zeile dient nur als Adresse. Die Antwort jeder Handlung
   * IST der neue Auftrag (`setQueryData`); nachgeladen wird über `lib/feed.TOUCHES`.
   */
  const objectId = record?.object_id ?? null;
  const qc = useQueryClient();
  const orderQuery = useQuery({
    queryKey: qk.order(objectId ?? 0),
    queryFn: ({ signal }) => api.getOrder(objectId!, { signal }),
    enabled: objectId != null,
    meta: { what: 'Auftrag' },
  });
  const live = objectId == null ? null : orderQuery.data ?? null;
  const setLive = useCallback((o: Order) => {
    if (objectId != null) qc.setQueryData(qk.order(objectId), o);
  }, [qc, objectId]);

  const draft = useMemo(() => ({
    lines: toPayload(lines),
    steps: steps.map(toModulePayload),
    loop: loopPayload(loop, lines),
  }), [lines, steps, loop]);

  // Freigebbarkeit beim Server erfragen. Die Vorschau der Quell-Aufträge (Auftrag §2) kommt
  // aus derselben Antwort.
  const check = useDebouncedQuery({
    name: 'order', input: isDraft ? draft : null, ask: api.validateOrder, what: 'Prüfung des Auftrags',
  });
  const missing: string[] | null = !isDraft ? null
    : check.data ? (check.data.missing ?? [])
      : check.error ? [`Prüfung nicht möglich – ${check.error.message}`] : null;
  const preview: RelatedOrder[] = (isDraft && check.data?.parents) || [];

  async function release() {
    const made = await run(() => api.createOrder(draft), (e) => {
      // Ein veralteter Pick ist eine neue Lage: der Server nennt sie mit einem Code, die
      // Auswahl wird nachgezogen.
      if (e instanceof ApiError && e.code === 'pick_stale') setRefreshKey((n) => n + 1);
    });
    if (made) onSaved(made);
  }

  /** **Eine Handlung am Auftrag**: ein Befehl, die Antwort IST der neue Auftrag (in den Cache). */
  const act = useCallback(async (fn: (id: number) => Promise<Order>) => {
    if (objectId == null) return;
    const o = await run(() => fn(objectId));
    if (o) setLive(o);
  }, [objectId, run, setLive]);

  const confirmStep = useCallback(async (stepId: number,
                                        instanceObjectId: number | null,
                                         verification: string,
                                         values: Record<string, Record<string, unknown>>,
                                         sources: number[] = [],
                                         place: number | null = null) => {
    await act((id) => api.confirmStep(id, stepId, values, instanceObjectId, verification,
                                      sources, place));
  }, [act]);

  /** **Eine Handlung am Beleg** – ein Aufruf, die Antwort IST der neue Auftrag. */
  const runVoucher = useCallback(async (
    stepId: number, body: { action: string } & Record<string, unknown>,
  ) => {
    await act((id) => api.updateVoucher(id, stepId, body));
  }, [act]);

  /** **Die Wiederholung beenden** – derselbe Weg: ein Befehl, die Antwort ist der Auftrag. */
  const endLoop = useCallback(() => act((id) => api.endLoop(id)), [act]);

  /** Den Auftrag neu holen – für die Online-Zahlung, die keine Antwort hat (bucht der Webhook). */
  const { refetch } = orderQuery;
  const reload = useCallback(() => { void refetch(); }, [refetch]);

  const blocked = missing != null && missing.length > 0;
  const loadError = !live && orderQuery.error ? orderQuery.error.message : null;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        type="order"
        // Die Abweichung ist ein Zeichen am Symbol – dieselbe Komponente wie im Feed.
        deviation={live?.is_deviation ?? false}
        title={live?.name ?? null}
        placeholder="Neuer Auftrag"
        objectId={live?.object_id ?? record?.object_id ?? null}
        objectIdText={isDraft ? NOTHING : undefined}
        objectIdHint={isDraft
          ? 'Die Objektnummer entsteht erst mit der Freigabe. Bis dahin existiert dieser Auftrag nur in diesem Fenster.'
          : undefined}
        status={live ? orderStatus(live) : undefined}
        actions={isDraft ? (
          <HeaderAction
            label="Freigeben"
            // Kein stummes Nichts-Passiert: der Knopf sagt, was noch fehlt.
            hint={blocked ? `Es fehlt: ${missing!.join(' · ')}` : 'Legt den Auftrag an und startet den Prozess'}
            disabled={busy || blocked || missing == null}
            onClick={release}
          />
        ) : live?.object_id != null ? (
          <LabelButton objectId={live.object_id} title={live.name} kind="Auftrag" />
        ) : undefined}
        onBack={onBack}
      />

      <div className="flex-1 p-5" style={{ background: 'var(--bg-2)' }}>
        {(error ?? loadError) && (
          <p className="mb-3 text-sm max-w-[880px] mx-auto px-3 py-2 rounded-ds-lg"
            style={{ color: 'var(--danger)', background: 'var(--danger-bg)' }}>
            {error ?? loadError}
          </p>
        )}

        {/* Kein Mass von hier: jedes Prozessbild bringt seines mit. */}
        {isDraft ? (
          <DraftView lines={lines} setLines={setLines} steps={steps} setSteps={setSteps}
            refreshKey={refreshKey} parents={preview}
            loop={<LoopDraftCard loop={loop} onChange={setLoop} lines={lines} />} />
        ) : live ? (
          <RunView order={live} busy={busy} onConfirm={confirmStep}
            onVoucher={runVoucher} onReload={reload}
            onDeviate={onDeviate} onEndLoop={endLoop} />
        ) : (
          loadError ? null : <div style={{ maxWidth: 880, margin: '0 auto' }}><Skeleton block={140} lines={5} label="Auftrag wird geladen" /></div>
        )}
        {!isDraft && live?.object_id != null && (
          <DetailBody gap={22} style={{ paddingBottom: 40 }}>
            <DocumentTiles objectId={live.object_id} />
            <SectionSep label="Verlauf" />
            <History objectId={live.object_id} />
          </DetailBody>
        )}

      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Entwurf — Modus «definition»
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Der Prozess folgt aus der Herkunft.** Trägt eine Zeile «Neu», ist er die Vorlage des
 * Artikels – hier nur zu sehen, geändert wird am Artikel. Ein reiner «Lager»-Auftrag wird
 * hier frei modelliert.
 */
function DraftView({ lines, setLines, steps, setSteps, refreshKey, parents, loop }: {
  lines: DefinitionLine[]; setLines: (l: DefinitionLine[]) => void;
  steps: ModuleDraft[]; setSteps: (s: ModuleDraft[]) => void;
  /** Hochgezählt, wenn die Freigabe an einer veralteten Auswahl scheitert. */
  refreshKey: number;
  /** Die Quell-Aufträge, wie sie nach der Freigabe aussähen (Auftrag §2). */
  parents: RelatedOrder[];
  /** Die Karte «Wiederholen» – unter dem Ende, im Editor wie bei einer Vorlage. */
  loop: React.ReactNode;
}) {
  // Welcher Artikel bringt den Prozess mit? Der erste mit Herkunft «Neu».
  const sourceArticle = useMemo(
    () => lines.find((l) => l.origin === NEU && l.articleObjectId !== null)?.articleObjectId ?? null,
    [lines],
  );
  // Die Vorlage ist eingefroren – einmal gelesen, gilt sie.
  const templateQuery = useQuery({
    queryKey: qk.articleProcess(sourceArticle ?? 0),
    queryFn: ({ signal }) => api.getArticleProcess(sourceArticle!, { signal }),
    enabled: sourceArticle !== null,
    staleTime: Infinity,
    meta: { what: 'Erzeugungsprozess' },
  });
  const template = sourceArticle === null ? null : templateQuery.data ?? null;

  const mirrored: DiagramStep[] | null = useMemo(() => {
    if (!template) return null;
    return (template.steps ?? []).map((s) => ({
      id: s.id, moduleType: s.module_type, label: s.label,
      tone: s.tone, terminal: s.terminal,
    }));
  }, [template]);

  const isMake = sourceArticle !== null;

  /**
   * **Die Rückführung schaltet man am Ziel** (§5), dem Quell-Auftrag. Die Entscheidung hängt
   * an der Definitionszeile (`returns`); umgeschaltet wird jede Zeile, die aus diesem Auftrag
   * nimmt – dieselbe Zusammenfassung wie die Vorschau des Servers.
   */
  const toggleReturn = useCallback((parentObjectId: number) => {
    const takes = (l: DefinitionLine) => l.units.some((u) => u.fromOrder === parentObjectId);
    const on = lines.some((l) => takes(l) && l.returns);
    setLines(lines.map((l) => (takes(l) ? { ...l, returns: !on } : l)));
  }, [lines, setLines]);

  const head = (
    <DefinitionLines lines={lines} setLines={setLines} refreshKey={refreshKey} />
  );

  // Bringt eine Zeile «Neu» mit, ist der Prozess die Vorlage des Artikels – nur ansehen.
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
            loop,
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
          loop={loop}
        />
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Freigegeben — Modus «ausfuehrung»
// ─────────────────────────────────────────────────────────────────────────────

function RunView({ order, busy, onConfirm, onVoucher, onReload,
                   onDeviate, onEndLoop }: {
  order: Order; busy: boolean;
  onConfirm: (stepId: number, instanceObjectId: number | null, verification: string,
              values: Record<string, Record<string, unknown>>,
              sources: number[], place: number | null) => void;
  /** Eine Handlung am Beleg des Moduls «Zahlung». */
  onVoucher: (stepId: number,
              body: { action: string } & Record<string, unknown>) => void;
  /** Den Auftrag neu laden – für die Online-Zahlung (bucht der Webhook, keine Antwort). */
  onReload: () => void;
  onDeviate?: (seed: OrderSeed) => void;
  onEndLoop: () => void;
}) {
  const steps: DiagramStep[] = toDiagramSteps(order.steps);
  // Die einzelnen Nummern kommen erst beim Aufklappen.
  /**
   * ►►► Die **restriktivere Variante** zur offenen Frage (Abweichungsauftrag §5) ◄◄◄
   * Solange im aktiven Modul erfasst wird, lässt sich keine Abweichung auslösen. Der Server
   * kann das nicht prüfen (eine begonnene Erfassung ist nirgends gespeichert). Die dauerhafte
   * Regel gehört an den Modultyp (`domain/modules.units_may_leave`).
   */
  const [entryStarted, setEntryStarted] = useState(false);

  /**
   * **Die eine Herkunft, die nicht im Log steht**: die Stücke eines Erzeugungsauftrags
   * entstehen bei der Freigabe. Alles andere steht in `journey_in`.
   */
  const origins: JourneyOrigin[] = (order.lines ?? [])
    .filter((ln) => ln.origin === NEU)
    .map((ln) => ({ label: ln.article_name ?? 'Artikel', count: ln.quantity }));

  const expand = useCallback(async (edgeId: string) => {
    const page = await api.getOrderUnits(order.object_id, edgeId, 100, 0);
    // Der Zustand bleibt am Stück – der Abweichungstrigger braucht ihn.
    return (page.units ?? []).map((u) => ({
      number: u.number, startedAt: u.started_at, status: u.status,
    }));
  }, [order.object_id]);

  // **Ein Modul-Körper, zwei Wege dorthin**: der volle Prozess und die Partner-Sicht ohne
  // Prozessbild. `internal` ist die Aussage der Aufrufstelle über sich selbst (das Protokoll
  // ist Personal-only); was ein Partner tun darf, entscheidet der Beleg (`voucher.can`).
  const stepBody = (step: DiagramStep, isActive: boolean, internal: boolean) => {
    // Ein Modul ohne Scan bekommt eine Bestätigung, kein Scan-Tor (`step.verifies`) – ein
    // Vorgang, nicht einer je Instanz. Eine Gegenpartei bestätigt kein Modul.
    const plain = step.verifies === false;
    // Warum jetzt nicht? – der Satz kommt vom Server (`Module.passes_itself`).
    const blocked = stepInfo(order, step.id)?.blocked ?? null;
    // Der Beleg umschliesst den Scan; erkannt daran, dass es einen gibt, nie am Modultyp.
    const paper = stepInfo(order, step.id)?.voucher ?? null;
    const work = !internal ? null : isActive && plain ? (
      // Der Modul-Knopf IST ein Knopf (`erp-actbtn-primary`); kann er nichts tun, gibt es ihn
      // nicht – was im Weg steht, sagt die Karte (`step.blocked`).
      blocked ? null : (
        <button type="button" className="erp-actbtn erp-actbtn-primary w-full"
          disabled={busy} style={{ height: 42, fontSize: 14 }}
          onClick={() => onConfirm(step.id, null, 'manual', {}, [], null)}>
          <Check size={16} /> {stepInfo(order, step.id)?.action ?? 'Bestätigen'}
        </button>
      )
    ) : isActive ? (
      // Die Arbeit steht je Instanz da – ein Vorgang ist eine Instanz (Scan-Regel §3).
      <CaptureWork
        orderObjectId={order.object_id}
        stepId={step.id}
        points={pointsOf(order, step.id)}
        action={stepInfo(order, step.id)?.action ?? ''}
        work={workOf(order, step.id)}
        needs={stepInfo(order, step.id)?.needs ?? []}
        // **Wohin und womit** – beides kommt vom Server mit dem Schritt.
        target={stepInfo(order, step.id)?.target ?? null}
        moves={step.moves}
        busy={busy}
        onDirty={setEntryStarted}
        onDeviate={onDeviate}
        onConfirm={(instanceObjectId, verification, values, sources, place) =>
          onConfirm(step.id, instanceObjectId, verification, values, sources, place)}
      />
    ) : paper ? (
      // Ein Modul, das seine Sache selbst zeigt (Beleg), braucht keine `PointList` daneben.
      null
    ) : (
      <PointList points={pointsOf(order, step.id)} sample={sampleOf(order, step.id)}
        action={stepInfo(order, step.id)?.action}
        reason={stepInfo(order, step.id)?.reason}
        moduleType={step.moduleType}
        target={step.moves ? (stepInfo(order, step.id)?.target ?? null) : undefined} />
    );
    return (
    <div className="flex flex-col gap-2.5">
      <Reason text={stepInfo(order, step.id)?.reason} />
      {paper ? (
        <BelegWork voucher={paper} busy={busy} active={isActive}
          orderObjectId={order.object_id} stepId={step.id}
          onAction={(body) => onVoucher(step.id, body)} onPaid={onReload}>
          {work}
        </BelegWork>
      ) : work}
      {/* Was in ihm passiert ist – zentral, nur wo es mehr gibt als die Passage (`step.records`). */}
      {internal && !isActive && step.records !== false
        && <StepRecord orderObjectId={order.object_id} stepId={step.id} />}
    </div>
    );
  };

  // Ohne Prozessbild (Partner, `orders._mine_only`): die Module allein, dieselbe `StepCard`.
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
          endStatus: FREIGEGEBEN,
          onExpand: expand,
          onDeviate: onDeviate
            ? (unitNumber) => { void startDeviation(unitNumber, order.object_id, onDeviate); }
            : undefined,
          deviateBlocked: entryStarted
            ? 'Im aktiven Modul wurde bereits erfasst. Erst bestätigen – oder das Fenster neu laden, dann ist die Eingabe verworfen.'
            : undefined,
          // Die Historie steht am Objekt (§5) – nur in der Mitte, Nachbarn haben sie nicht geladen.
          events: order.events ?? [],
          eventTotal: order.event_count ?? undefined,
          // Ein Modul zeigt seine Sache in jedem Zustand; `isActive` entscheidet nur übers Handeln.
          renderStep: (step, isActive) => stepBody(step, isActive, true),
          loop: order.loop
            ? <LoopRunCard loop={order.loop} busy={busy} onEnd={onEndLoop} />
            : undefined,
        }}
        loopWalked={order.loop?.successor != null}
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
 * Was dieses Modul erfassen wird – seine eingefrorene Definition. Erfasste Werte stehen in
 * der Historie, nicht hier.
 */
/**
 * **Warum hier ausgesondert wird** – aus der Definition (`domain/modules.Aussondern`), als
 * Auskunft, nicht als Eingabefeld.
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
   * Wohin dieses Modul bringt. `null` heisst beim Bewegen «wird beim Ausführen gewählt» und
   * muss so dastehen, nicht als Lücke.
   */
  target?: PlaceRef | null;
}) {
  // Ein Modul ohne Erfassungspunkte hat trotzdem etwas zu sagen: Verb, Grund, Ziel.
  if (!points.length) {
    const Icon = moduleIcon(moduleType);
    return action ? (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
          <Icon size={13} style={{ color: 'var(--fg-4)' }} />
          <span>{action}</span>
        </div>
        {/* Dasselbe Wort wie im Editor (`RUNTIME_CHOICE`) – ein Zustand, eine Formulierung. */}
        {target !== undefined && (
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
            {target ? (
              <>
                <span style={{ color: 'var(--fg-4)' }}>nach</span>
                <PlaceTrail place={{ holder: target, chain: [target] }} />
              </>
            ) : (
              <span className="text-fg-4"
                data-tip="Dieses Modul hat kein festes Ziel – wohin die Stücke gehen, bestimmt der Ausführende.">
                {RUNTIME_CHOICE}
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
      {/* Die Stichprobenregel gehört zur Definition (`sampling.describe`); die konkrete
          Zahl sagt erst die Ziehung am aktiven Modul. */}
      {sample && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-4)' }}>
          <Layers size={13} />
          <span>Stichprobe: {sample}</span>
        </div>
      )}
      {points.map((p) => {
        const Icon = lookup(CAPTURE_ICON, p.type) ?? CAPTURE_ICON.text;
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

/** **Wartet dieser Auftrag auf eine Rückführung?** Abgeleitet: offene rückführende Verbindung. */

/**
 * Welcher Artikel gehört zu diesem Stück? Der vordere Teil der Nummer ist die Instanz, die
 * Instanz kennt ihren Artikel – gefragt wird der bestehende Endpunkt.
 */
async function startDeviation(
  unitNumber: string, fromOrder: number, open: (seed: OrderSeed) => void,
) {
  const instanceId = Number(unitNumber.split('-')[0]);
  if (!Number.isInteger(instanceId)) return;
  const instance = await api.getInstance(instanceId);
  if (instance.article_object_id == null) return;
  // Woher das Stück kommt: aus dem offenen Auftrag – genau das prüft der Server bei der Freigabe.
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
 * Wie viele Stücke gerade davor stehen – aus derselben Quelle wie das Bild (`order.flow`):
 * die Kanten, die in dieses Modul münden.
 */
function workOf(order: Order, stepId: number): StepWork[] {
  return order.steps?.find((s) => s.id === stepId)?.work ?? [];
}

/*
 * **Der Ereignis-Log steht am Prozessobjekt**, an dem er passiert ist
 * (`lib/process-graph.historyTip`) – Start, Module und Ende tragen dieselbe Blase, denn
 * `start`/`end` haben kein Modul (`step_id = null`).
 */

