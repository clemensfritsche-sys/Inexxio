'use client';

import { Truck, Check, X, PauseCircle, TriangleAlert, PackageMinus, PackagePlus, CheckCircle2,
  CornerLeftDown, CornerRightUp, Clock3 } from 'lucide-react';
import type { Order, OrderDeviationInfo, OrderOrigin, OrderStep, StepResolution, StepType,
  SubOrderStep } from '@/types';
import { STEP_META, stepStateLabel } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { orderStatus } from '@/lib/record-status';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { saleStatusConfig } from '@/lib/sale';
import { Connector, FlowTerm, STEP_MAXW, kindColor } from '@/components/erp/process-steps';
import { actorHint, formatObjectId } from '@/lib/utils';

// ─── Der Ablauf eines laufenden Auftrags – dieselbe Darstellung wie die Definition ─
//
// Ein Prozess sieht überall gleich aus: der senkrechte BPMN-Fluss mit Start-/Endknoten und
// einer Karte je Modul – so, wie man ihn am Artikel definiert hat. Der einzige Unterschied
// ist, was eine Karte ZEIGT und KANN:
//
//   Definition → die Konfiguration, sortierbar
//   Ablauf     → den Zustand, und die gewählte Karte **öffnet ihr Panel in sich selbst**
//                (der Schritt wird dort bearbeitet, wo er im Fluss steht – nicht in einem
//                abgespaltenen Container darunter).
//
// **Zustand ohne Text** (Notiz #88): erledigte und noch nicht erreichte Schritte treten
// zurück (ausgegraut), nur der aktive trägt seine Farbe. Dazu ein Symbol statt eines Wortes –
// Haken (erledigt), Pause (angehalten), Kreuz (Fehler). Der Hover nennt Wer/Wann.
//
// **Unter-Aufträge stehen ZWISCHEN den Modulen** (Notiz #353) – an der Stelle, an der sie
// entstanden sind (``origin_step_id``). Das gilt für alle drei Arten, und darum sehen sie auch
// alle gleich aus (``SubOrderCard``): **Abweichung** (etwas ist schiefgegangen), **Nachschub**
// (etwas fehlte) und **Bereitstellung** (etwas musste erst hergebracht werden). Sie sind
// eingerückt – ein Unter-Auftrag ist kein Modul dieses Prozesses, sondern ein eigener Auftrag,
// der hier hineinragt; ein Klick öffnet ihn.
//
// **Und die Reihenfolge sagt, in welchem Verhältnis er zum Schritt steht** (Notiz #372): was
// den Schritt AUFHÄLT, steht VOR ihm (erst das hier, dann dieser Schritt); was aus ihm FOLGT,
// danach (die Ware kommt an, nachdem bestellt wurde). Das ist **eine Angabe am Unter-Auftrag**
// (``stage``), abgeleitet im Backend – hier wird nur einsortiert, nicht entschieden.
//
// Ein Unter-Auftrag OHNE Ursprungsschritt (an einer fremden Instanz gemeldet) gehört keinem
// Schritt – er gehört dem Auftrag und steht am Anfang des Flusses.
//
// **Ruht der Auftrag, ruht der ganze Fluss** (Notiz #378): dann tritt JEDES Modul zurück und
// keines lässt sich öffnen – der einzige farbige Knoten ist der Unter-Auftrag, der zu klären
// ist. Das ist keine zweite Regel, sondern dieselbe wie im Backend (``process.is_paused`` →
// jeder Schritt ist ``blocked``, jede Ausführung 409); sie war bisher nur nicht zu sehen.
//
// **Das Big Picture geht in BEIDE Richtungen** (Notiz #409). Am Ende ist alles ein Prozess –
// also zeigt der Fluss nicht nur, was in DIESEM Auftrag passiert, sondern auch, wie er mit
// den abgezweigten zusammenhängt:
//
//   Eltern → Abzweig : der Unter-Auftrags-Knoten steht an seiner Stelle im Ablauf und trägt
//                      seinen eigenen Prozess **angeteasert** (Miniatur-Fluss, ``SubSteps``) –
//                      wie weit er ist, sieht man ohne ihn zu öffnen; ein Klick wechselt hin.
//   Abzweig → Eltern : oberhalb des Startknotens steht, woher der Auftrag kam (Auftrag **und**
//                      Schritt), unterhalb des Endknotens, wohin seine Stücke zurückgehen –
//                      gestrichelt angebunden, weil dort der eigene Ablauf endet (``BranchNode``).
//
// Beides sind Teaser, kein zweites Detailfenster: sie nennen die Sache und öffnen sie.

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  return actorHint(s.completed_by ?? 'System', s.completed_at);
}

/**
 * **Die offene Unterdeckungs-Entscheidung** – sie gehört dem Auftrag (Notiz #354), also gibt
 * es sie einmal; der Fluss zeigt sie am **Gate** an der Stelle, an der er stillsteht.
 */
export type FlowDecision = { missing: string; canAct: boolean; onDecide?: () => void };

export function OrderFlow({ steps, subOrders = [], origin, decision, paused = false, selectedId, onSelectStep, onOpenOrder, renderPanel }: {
  steps: OrderStep[];
  /** Alle Unter-Aufträge des Auftrags – die ohne Ursprungsschritt stehen vor dem Fluss. */
  subOrders?: OrderDeviationInfo[];
  /** Offene Fehlmenge – wird als anklickbares Gate im Fluss gezeigt (#413). */
  decision?: FlowDecision;
  /** Woher dieser Auftrag kam und wohin er zurückgibt – nur an einem Unter-Auftrag (#409). */
  origin?: OrderOrigin | null;
  /** Ruht der Auftrag? Dann tritt der ganze Fluss zurück und nichts lässt sich öffnen (#378). */
  paused?: boolean;
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
}) {
  if (steps.length === 0 && !origin) return null;

  const rows: React.ReactNode[] = [];
  // **Ein Abzweig ist ein paralleler Pfad, kein eingerückter Kasten** (Notiz #413): die
  // Linie teilt sich (⊓), links läuft der Hauptprozess weiter bzw. wartet, rechts läuft der
  // Abzweig – und unten führt sie wieder zusammen (⊔) mit einem **Gate**, das die
  // Entscheidung trägt. ``gateUsed`` merkt, ob die offene Entscheidung schon einen Platz
  // hat: sie gehört dem Auftrag (nur eine), also wird sie genau einmal gezeigt.
  let gateUsed = false;
  const group = (list: OrderDeviationInfo[], res: StepResolution[] = []) => {
    if (list.length === 0) return null;
    const open = list.some((x) => x.status === 'draft' || x.status === 'released');
    const gate = gateState(res, open, !gateUsed && !!decision);
    if (gate === 'decide') gateUsed = true;
    return (
      <BranchGroup key={`grp-${list[0].object_id}`} branches={list} resolutions={res}
        gate={gate} decision={decision} onOpen={onOpenOrder} />
    );
  };

  // Was kein Schritt für sich beansprucht, gehört dem Auftrag – und steht am Anfang.
  const claimed = new Set(steps.flatMap((s) => (s.sub_orders ?? []).map((d) => d.object_id)));
  const loose = subOrders.filter((x) => !claimed.has(x.object_id));
  if (loose.length) rows.push(group(loose));

  for (const s of steps) {
    const meta = STEP_META[s.step_type as StepType] ?? STEP_META.purchase;
    const selected = selectedId === String(s.id) && !paused;
    // **Jeder Unter-Auftrag trägt seine Position selbst** (``stage``, im Backend abgeleitet):
    // «vorher» = er hält den Schritt auf (erst das hier, dann dieser Schritt), «nachher» = er
    // folgt aus ihm. Hier wird nur einsortiert – ohne Fallunterscheidung, weil es dieselbe
    // Sache ist: ein Unter-Auftrag an seiner Stelle im Ablauf.
    const subs = s.sub_orders ?? [];
    const before = subs.filter((x) => x.stage === 'before');
    const after = subs.filter((x) => x.stage === 'after');
    // **Die Entscheidung steht am Rückfluss des Abzweigs, nicht in der Karte** (Notiz #410):
    // «Menge angepasst 5 → 4» beantwortet die Frage «und was passiert, wenn er zurückkommt?» –
    // die stellt sich genau dort. Ohne Abzweig bleibt sie am Schritt, wo sie gefallen ist.
    const res = s.resolutions ?? [];
    const atBranch = before.length > 0;
    // Steht der Prozess ohne Abzweig still (z. B. Ausschuss in der Erzeugung), bekommt die
    // Entscheidung ein **eigenes Gate** vor dem Schritt, der nicht weiterkommt – dieselbe
    // Raute, nur ohne parallelen Pfad daneben. EIN Baustein, zwei Plätze.
    const soloGate = !atBranch && !gateUsed && !!decision && s.state !== 'done';
    if (soloGate) gateUsed = true;
    rows.push(
      ...(atBranch ? [group(before, res)] : []),
      ...(soloGate ? [<Gateway key={`gate-${s.id}`} state="decide" decision={decision} />] : []),
      <FlowCard
        key={`step-${s.id}`}
        type={s.step_type as StepType}
        label={meta.label}
        icon={meta.icon}
        detail={stepDetail(s)}
        badge={stepBadge(s)}
        resolutions={atBranch ? [] : res}
        state={s.state}
        hint={completionHint(s)}
        selected={selected}
        muted={paused}
        onClick={paused ? undefined : () => onSelectStep(String(s.id))}
      >
        {selected && renderPanel?.(s)}
      </FlowCard>,
      ...(after.length ? [group(after)] : []),
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {origin && (
        <>
          <OrderBranchTeaser origin={origin} kind="from" onOpen={onOpenOrder} />
          <Connector dashed />
        </>
      )}
      <FlowTerm kind="start" />
      {rows.map((r, i) => (
        <div key={i} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Connector />
          {r}
        </div>
      ))}
      <Connector />
      <FlowTerm kind="end" />
      {origin?.returns_to_object_id != null && (
        <>
          <Connector dashed />
          <OrderBranchTeaser origin={origin} kind="back" onOpen={onOpenOrder} />
        </>
      )}
    </div>
  );
}

/**
 * **Woher der Auftrag kam – und wohin er zurückgibt** (Notiz #409).
 *
 * Ein abgezweigter Auftrag hing bisher in der Luft: im Eltern sah man den Abzweig, aber im
 * Abzweig selbst stand nirgends, aus welchem Auftrag und – vor allem – aus welchem **Schritt**
 * er hervorgegangen ist. Genau diese Stelle ist die Antwort auf «warum gibt es mich?».
 *
 * Bewusst ein **Teaser**, kein zweites Detailfenster: Auftrag, Nummer und der Schritt, mehr
 * nicht; ein Klick wechselt hinüber. Gestrichelt angebunden, weil hier der eigene Ablauf
 * aufhört und ein anderer Auftrag beginnt – der Knoten ist kein Modul dieses Prozesses.
 *
 * **Der Rückweg ist nicht zwingend der Eltern**: wurde der Eltern abgebrochen, reicht die
 * Ausleihe durch bis zum nächsten laufenden Auftrag (Notiz #404). Welcher das ist, leitet das
 * Backend aus derselben Mechanik ab, die es auch tut – hier wird nur angezeigt.
 */
export function OrderBranchTeaser({ origin, kind, onOpen }: {
  origin: OrderOrigin;
  kind: 'from' | 'back';
  onOpen?: (objectId: number) => void;
}) {
  const from = kind === 'from';
  const objectId = from ? origin.order_object_id : origin.returns_to_object_id;
  if (objectId == null) return null;
  const name = (from ? origin.order_name : origin.returns_to_name) ?? null;
  const stepLabel = from && origin.step_type
    ? (STEP_META[origin.step_type as StepType]?.label ?? null) : null;
  const Icon = from ? CornerLeftDown : CornerRightUp;
  return (
    <button type="button" onClick={() => onOpen?.(objectId)}
      title={from
        ? `Hervorgegangen aus ${name ?? 'Auftrag'}${stepLabel ? ` · ${stepLabel}` : ''} – öffnen`
        : `Gibt beim Abschluss zurück an ${name ?? 'Auftrag'} – öffnen`}
      style={{
        width: '100%', maxWidth: STEP_MAXW, display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 13px', textAlign: 'left', cursor: 'pointer',
        border: '1px dashed var(--border-2)', borderRadius: 'var(--r-lg)', background: 'transparent',
        font: '500 12.5px var(--font-body)', color: 'var(--fg-3)',
      }}>
      <Icon size={14} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
      <span style={{ flexShrink: 0 }}>{from ? 'aus' : 'zurück an'}</span>
      {name && <span style={{ fontWeight: 700, color: 'var(--fg-2)', minWidth: 0,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>}
      <span style={{ fontFamily: 'var(--font-mono), monospace', fontSize: 12,
        fontVariantNumeric: 'tabular-nums', color: 'var(--accent)', flexShrink: 0 }}>
        {formatObjectId(objectId)}
      </span>
      {stepLabel && <span style={{ color: 'var(--fg-4)', flexShrink: 0 }}>· {stepLabel}</span>}
    </button>
  );
}

// Zustands-Symbol statt Zustands-Wort. Kein Symbol für «aktiv» – dass ein Schritt dran ist,
// sagt bereits die Farbe (er ist der einzige, der nicht zurücktritt).
const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done:    { icon: Check,       color: 'var(--success)' },
  blocked: { icon: PauseCircle, color: 'var(--warning)' },
  failed:  { icon: X,           color: 'var(--danger)' },
};

function FlowCard({ type, label, icon: Icon, detail, badge, resolutions = [], state, hint, selected, muted: forced, onClick, children }: {
  type: StepType;
  label: string;
  icon: React.ElementType;
  detail?: React.ReactNode;
  /** Fachlicher Zustand des Moduls (z. B. «Angefragt») – im Kopf, wo der Zustand hingehört. */
  badge?: React.ReactNode;
  /** Was an diesem Schritt bei einer Unterdeckung entschieden wurde (Notiz #281). */
  resolutions?: StepResolution[];
  state: string;
  hint?: string;
  selected?: boolean;
  /** Ruht der ganze Auftrag? Dann tritt auch dieser Schritt zurück (Notiz #378). */
  muted?: boolean;
  /** Fehlt der Handler, ist die Karte nicht anwählbar – der Fluss ruht. */
  onClick?: () => void;
  children?: React.ReactNode;
}) {
  const kc = kindColor(type);
  // «Nicht relevant» = erledigt, noch nicht erreicht – oder der ganze Auftrag ruht: die Karte
  // tritt zurück (gedämpft). Nur was JETZT dran ist, trägt seine Farbe.
  const muted = forced || state === 'done' || state === 'locked';
  const mark = STATE_MARK[state];
  const MarkIcon = mark?.icon;
  return (
    <div
      style={{
        position: 'relative', width: '100%', maxWidth: STEP_MAXW,
        border: `1px solid ${selected ? 'var(--fg-1)' : kc.border}`,
        borderRadius: 'var(--r-lg)', background: kc.bg,
        boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
        // Zurücktreten heisst gedämpft, nicht farblos: die Karte behält ihre Modulfarbe und
        // verliert nur an Kraft. Weiss hätte einem erledigten Schritt seine Zugehörigkeit
        // genommen – man sähe im Rückblick nicht mehr, welches Modul dort stand.
        opacity: muted ? 0.5 : 1,
        transition: 'box-shadow .16s, border-color .16s, opacity .16s',
      }}
    >
      <div onClick={onClick} title={hint}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px', cursor: onClick ? 'pointer' : 'default' }}>
        <div style={{
          width: 38, height: 38, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff',
          color: kc.fg, border: `1px solid ${kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={19} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{label}</span>
          {detail && <div style={{ marginTop: 3, fontSize: 12, color: 'var(--fg-3)' }}>{detail}</div>}
          {/* Was hier entschieden wurde, als etwas fehlte – bleibt sichtbar, auch wenn der
              Schritt längst wieder läuft (Notiz #281). Eine Zeile je Entscheidung. */}
          {resolutions.map((r, i) => <ResolutionLine key={i} r={r} />)}
        </div>
        {badge}
        {MarkIcon && <MarkIcon size={18} style={{ color: mark.color, flexShrink: 0 }} />}
      </div>
      {/* Der Schritt wird DORT bearbeitet, wo er im Fluss steht – nicht in einem eigenen
          Container darunter. Gleiche Anatomie wie die Konfiguration in der Definition. */}
      {children && (
        <div style={{ borderTop: `1px solid ${kc.border}`, padding: '14px 18px 16px' }}>
          {children}
        </div>
      )}
    </div>
  );
}

/**
 * **Was diesem Schritt widerfahren ist** – drei Ereignisse, drei Sätze (Testnotiz #405).
 *
 * Vorher gab es nur zwei Zweige: «Menge angepasst» und ein **Sammel-Else** «N ab Lager
 * ersetzt». Damit las sich auch ein **entzogener Anteil** (`share_taken` – ein anderer
 * Auftrag hat sich hier ein Stück geholt) als Ersatz aus dem Lager. Genau umgekehrt: dort
 * ist etwas **weggegangen**, nicht dazugekommen – wer «Auftrag pausieren» gewählt hatte,
 * las trotzdem «1 ab Lager ersetzt».
 *
 * Sie steht dort, wo sie gefallen ist: am Schritt, der blockiert war. Wer/wann im Hover.
 */
const RESOLUTION_META: Record<string, { icon: React.ElementType; tone: string }> = {
  quantity_confirmed: { icon: CheckCircle2, tone: 'var(--success)' },
  covered_from_stock: { icon: PackagePlus, tone: 'var(--success)' },
  share_taken: { icon: PackageMinus, tone: 'var(--warning)' },
};

function ResolutionLine({ r, first = false }: { r: StepResolution; first?: boolean }) {
  const who = actorHint(r.by, r.at);
  const meta = RESOLUTION_META[r.kind] ?? RESOLUTION_META.covered_from_stock;
  const Icon = meta.icon;
  const qty = <b style={{ color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>{r.quantity}</b>;
  return (
    <div title={who}
      style={{ marginTop: first ? 0 : 4, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
        font: '500 12px var(--font-body)', color: 'var(--fg-3)', cursor: who ? 'help' : 'default' }}>
      <Icon size={13} style={{ color: meta.tone, flexShrink: 0 }} />
      {r.kind === 'quantity_confirmed' && (
        <span>
          Menge angepasst
          <b style={{ marginLeft: 5, color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>
            {r.quantity_from} → {r.quantity_to}
          </b>
        </span>
      )}
      {r.kind === 'covered_from_stock' && <span>{qty} ab Lager ersetzt</span>}
      {r.kind === 'share_taken' && (
        <span>
          {qty} abgegeben
          {r.other_order_object_id != null && <> an <ObjId value={r.other_order_object_id} /></>}
        </span>
      )}
      {r.article_name && <span style={{ color: 'var(--fg-4)' }}>· {r.article_name}</span>}
    </div>
  );
}

// Die drei Arten von Unter-Auftrag – EIN Muster, drei Beschriftungen. Alle drei sind
// eigenständige Aufträge, die aus einem Schritt hervorgegangen sind; sie unterscheiden sich
// nur darin, WARUM (siehe ``orders.reason``) – und darum auch darin, was ihre Rückkehr in
// den Hauptprozess bedeutet (``rejoin``).
const SUB_META: Record<string, {
  label: string; icon: React.ElementType; open: string; rejoin: string;
}> = {
  deviation: {
    label: 'Abweichung', icon: TriangleAlert,
    open: 'Offene Abweichung – ihr Stück fehlt dem Auftrag, bis sie geklärt ist',
    rejoin: 'zurück in den Prozess',
  },
  supply: {
    label: 'Nachschub', icon: PackagePlus,
    open: 'Nachschub läuft – der Schritt wird von selbst wieder aktiv',
    rejoin: 'deckt den Bedarf',
  },
  provisioning: {
    label: 'Bereitstellung', icon: Truck,
    open: 'Material wird an seinen Ort gebracht',
    rejoin: 'Material ist am Ort',
  },
};

// ─── Abzweig als paralleler Pfad: Fork · Spur · Merge · Gate (Notiz #413) ──────────
//
// Ein Abzweig ist kein eingerückter Kasten neben dem Prozess, sondern ein **zweiter Pfad im
// selben Prozess**. Darum die klassische Flowchart-Grammatik:
//
//   ⊓  die Linie **teilt** sich    – links der Hauptprozess, rechts der Abzweig
//   ┆  die Hauptspur **wartet**    – gestrichelt, solange der Abzweig läuft; durchgezogen,
//                                     sobald entschieden ist (der Hauptprozess läuft weiter)
//   ⊔  die Pfade **führen zusammen**
//   ◇  das **Gate** – hier fällt die Entscheidung, und hier steht sie danach
//
// Der Zustand der Hauptspur IST die Aussage: gestrichelt = «hier geht nichts, bis das da
// drüben durch ist», durchgezogen = «läuft weiter, der Abzweig läuft daneben».

const LANE = 56;   // Breite der Hauptspur neben dem Abzweig

/** ⊓ – die Linie teilt sich. Der Bogen spannt von der Hauptspur zur Mitte des Abzweigs. */
function Fork({ tone }: { tone: string }) {
  return (
    <div style={{ display: 'flex', width: '100%', maxWidth: STEP_MAXW }}>
      <div style={{ width: LANE / 2, flex: 'none' }} />
      <div style={{
        width: '50%', flex: 'none', height: 14, borderRadius: '10px 10px 0 0',
        borderTop: `1.5px solid ${tone}`, borderLeft: `1.5px solid ${tone}`,
        borderRight: `1.5px solid ${tone}`,
      }} />
    </div>
  );
}

/** ⊔ – die Pfade führen wieder zusammen. */
function Merge({ tone }: { tone: string }) {
  return (
    <div style={{ display: 'flex', width: '100%', maxWidth: STEP_MAXW }}>
      <div style={{ width: LANE / 2, flex: 'none' }} />
      <div style={{
        width: '50%', flex: 'none', height: 14, borderRadius: '0 0 10px 10px',
        borderBottom: `1.5px solid ${tone}`, borderLeft: `1.5px solid ${tone}`,
        borderRight: `1.5px solid ${tone}`,
      }} />
    </div>
  );
}

/**
 * Die Hauptspur neben dem Abzweig – **gestrichelt, solange sie wartet**.
 *
 * Das ist keine Dekoration, sondern die Semantik: eine unterbrochene Linie sagt «hier fliesst
 * gerade nichts». Ist entschieden (Menge reduziert bzw. ersetzt), läuft der Hauptprozess
 * weiter, während der Abzweig daneben noch arbeitet – dann ist sie durchgezogen.
 */
function MainLane({ waiting }: { waiting: boolean }) {
  return (
    <div style={{ width: LANE, flex: 'none', display: 'flex', justifyContent: 'center' }}>
      <div style={waiting
        ? { width: 2, backgroundImage: 'linear-gradient(var(--border-2) 55%, transparent 55%)',
            backgroundSize: '2px 7px' }
        : { width: 2, background: 'var(--border-2)' }} />
    </div>
  );
}

/** Was das Gate unter einem Abzweig zeigt – abgeleitet, nicht gesetzt. */
function gateState(res: StepResolution[], branchOpen: boolean, decidable: boolean) {
  if (res.length > 0) return 'resolved' as const;   // entschieden – die Auflösung steht da
  if (branchOpen) return 'waiting' as const;        // läuft; der Hauptprozess wartet
  return decidable ? ('decide' as const) : null;    // durch, aber es fehlt noch etwas
}

const GATE_TONE = { decide: 'var(--warning)', waiting: 'var(--fg-4)', resolved: 'var(--success)' };
const GATE_ICON = { decide: X, waiting: Clock3, resolved: Check };

/**
 * **Das Gate – wo die Entscheidung fällt und danach steht** (Notiz #413).
 *
 * Eine Raute ist im Flowchart das Zeichen für «hier wird entschieden». Genau das passiert
 * hier: fehlt dem Auftrag etwas, ist das Gate **anklickbar** und stellt die eine Frage
 * (ersetzen · Menge reduzieren · warten). Ist entschieden, trägt dieselbe Raute die
 * Antwort. Damit ist die Entscheidung ein **Knoten im Prozess** statt einer Notiz darunter –
 * man sieht, wo sie hingehört und was aus ihr wurde.
 */
function Gateway({ state, label, decision }: {
  state: 'decide' | 'waiting' | 'resolved';
  label?: React.ReactNode;
  decision?: FlowDecision;
}) {
  const tone = GATE_TONE[state];
  const Icon = GATE_ICON[state];
  const act = state === 'decide' ? decision : undefined;
  const text = label ?? (state === 'decide'
    ? <>Es fehlt <b style={{ color: 'var(--fg-1)' }}>{act?.missing}</b> · entscheiden</>
    : state === 'waiting' ? 'wartet' : null);
  const body = (
    <>
      <span style={{
        width: 28, height: 28, flex: 'none', transform: 'rotate(45deg)', borderRadius: 5,
        border: `1.5px solid ${tone}`, background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={13} style={{ transform: 'rotate(-45deg)', color: tone }} />
      </span>
      {text && (
        <span style={{ maxWidth: STEP_MAXW - 40, textAlign: 'center',
          font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' }}>{text}</span>
      )}
    </>
  );
  const layout: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
    border: 'none', background: 'none', padding: 0,
  };
  if (!act?.canAct || !act.onDecide) return <div style={layout}>{body}</div>;
  return (
    <button type="button" onClick={act.onDecide} title="Unterdeckung entscheiden"
      style={{ ...layout, cursor: 'pointer' }}>{body}</button>
  );
}

/**
 * **Ein Abzweig als paralleler Pfad** – Fork, Hauptspur, der Abzweig, Merge, Gate.
 *
 * Mehrere Abzweige an derselben Stelle teilen sich einen Pfad (sie halten denselben Schritt
 * auf); das Gate darunter gilt für sie gemeinsam, weil die Fehlmenge dem **Auftrag** gehört
 * und nicht einem einzelnen Abzweig (Notiz #354).
 */
function BranchGroup({ branches, resolutions, gate, decision, onOpen }: {
  branches: OrderDeviationInfo[];
  resolutions: StepResolution[];
  gate: 'decide' | 'waiting' | 'resolved' | null;
  decision?: FlowDecision;
  onOpen?: (id: number) => void;
}) {
  const open = branches.some((x) => x.status === 'draft' || x.status === 'released');
  const tone = open ? 'var(--warning)' : 'var(--border-2)';
  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <Fork tone={tone} />
      <div style={{ width: '100%', maxWidth: STEP_MAXW, display: 'flex', alignItems: 'stretch' }}>
        {/* Der Hauptprozess wartet, solange der Abzweig läuft und nichts entschieden ist. */}
        <MainLane waiting={open && gate !== 'resolved'} />
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {branches.map((b) => <SubOrderBranch key={b.object_id} info={b} onOpen={onOpen} />)}
        </div>
      </div>
      <Merge tone={tone} />
      {gate && (
        <div style={{ marginTop: 8 }}>
          <Gateway state={gate} decision={decision}
            label={gate === 'resolved'
              ? <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {resolutions.map((r, i) => <ResolutionLine key={i} r={r} first />)}
                </span>
              : undefined} />
        </div>
      )}
    </div>
  );
}

/**
 * **Der Abzweig ist ein Prozess im Prozess** (Testnotiz #410).
 *
 * Die Hauptlinie wird an der Stelle **gekappt**, an der der Unter-Auftrag entstanden ist; von
 * dort führt sie in einen eigenen kleinen Fluss – **Startknoten mit dem Verweis auf den
 * Abzweig, darunter seine Prozessschritte, am Schluss der Endknoten mit der Ablenkung zurück
 * in den Hauptprozess**. Das ist keine neue Bildsprache, sondern dieselbe eine Nummer
 * kleiner: dieselben Terminal-Knoten (`FlowTerm size`), dieselben Verbinder, dieselben
 * Modulfarben und dieselbe Zustands-Regel (nur was JETZT dran ist, trägt Farbe).
 *
 * Vorher war der Abzweig eine flache Zeile mit einer Reihe Symbolen – man sah, DASS es ihn
 * gibt, aber nicht, dass der Hauptprozess hier tatsächlich anhält und über ihn läuft.
 *
 * **Und was am Ende entschieden wurde, steht am Rückfluss** – dort, wo die Linie in den
 * Hauptprozess zurückkehrt, denn genau das ist die Frage, die eine Entscheidung beantwortet:
 *
 *   ohne Entscheidung  → «zurück in den Prozess» (bzw. «deckt den Bedarf») – der Hauptfluss
 *                        ruht, bis der Abzweig durch ist; dass er ruht, sagt der
 *                        zurückgetretene Rest (Notiz #378).
 *   Menge reduziert    → «Menge angepasst 5 → 4» – der Auftrag läuft **mit weniger** weiter,
 *                        das Stück bleibt beim Abzweig.
 *   ersetzt            → «1 ab Lager ersetzt» – etwas anderes ist an dieser Stelle in den
 *                        Hauptprozess **eingemündet**, das Stück bleibt beim Abzweig.
 *
 * Der ganze Kasten öffnet den Unter-Auftrag; die Schritte darin sind bewusst nicht einzeln
 * anwählbar – ein Schritt wird in SEINEM Auftrag bearbeitet, und der ist einen Klick entfernt.
 */
function SubOrderBranch({ info, onOpen }: {
  info: OrderDeviationInfo;
  onOpen?: (id: number) => void;
}) {
  const open = info.status === 'draft' || info.status === 'released';
  const meta = SUB_META[info.reason ?? 'deviation'] ?? SUB_META.deviation;
  const Icon = meta.icon;
  const tone = open ? 'var(--warning)' : 'var(--border-1)';
  // **Sein Zustand gehört hierher** (Notiz #404): dass es diesen Unter-Auftrag gibt, steht
  // ohnehin da – ohne seinen Status muss man ihn öffnen, um zu wissen, ob noch etwas zu tun
  // ist. Dieselbe Badge wie überall (``orderStatus``), kein zweites Vokabular.
  const cfg = orderStatus({ status: info.status as Order['status'], abort_into_id: info.abort_into_id });
  const steps = info.steps ?? [];
  return (
    <div style={{ width: '100%', minWidth: 0 }}>
      <div style={{
        border: `1.5px dashed ${tone}`, borderRadius: 'var(--r-lg)',
        background: open ? 'var(--warning-bg)' : 'var(--bg-2)',
        opacity: open ? 1 : 0.62, overflow: 'hidden',
      }}>
        {/* ── Startknoten des Abzweigs, mit dem Verweis auf ihn ─────────────────── */}
        <button type="button" onClick={() => onOpen?.(info.object_id)}
          title={open ? meta.open : `${meta.label}: ${cfg.label}`}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left',
            padding: '10px 13px', border: 'none', background: 'none', cursor: 'pointer',
          }}>
          <FlowTerm kind="start" size={26} />
          <Icon size={15} style={{ color: open ? 'var(--warning)' : 'var(--fg-4)', flexShrink: 0 }} />
          <span style={{ minWidth: 0, flex: 1, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>{meta.label}</span>
            <ObjId value={info.object_id} />
          </span>
          <StatusBadge cfg={cfg} />
        </button>

        {/* ── Seine Prozessschritte – derselbe Fluss, eine Nummer kleiner ───────── */}
        {steps.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0 13px' }}>
            {steps.map((st) => (
              <div key={st.id} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <Connector height={12} />
                <SubStepCard step={st} />
              </div>
            ))}
          </div>
        )}

        {/* ── Endknoten – wohin es von hier geht, sagt der Merge samt Gate darunter ── */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0 13px 11px' }}>
          <Connector height={12} />
          <div style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, paddingTop: 9 }}>
            <FlowTerm kind="end" size={26} />
            <span style={{ minWidth: 0, flex: 1, font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' }}>
              {meta.rejoin}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Ein Prozessschritt **des Abzweigs** – eine kleine, nicht anwählbare Karte.
 *
 * Bewusst nicht `FlowCard`: die ist die operable Karte DIESES Prozesses (öffnet ihr Panel,
 * trägt Badge, Auflösungen, Wer/Wann). Hier geht es um eine Projektion eines **fremden**
 * Schritts – er wird in seinem eigenen Auftrag bearbeitet. Gemeinsam bleibt, was gemeinsam
 * sein muss: Modulfarbe, Symbol, Zustands-Regel (erledigt/noch nicht erreicht treten zurück)
 * und das Zustands-Symbol.
 */
function SubStepCard({ step }: { step: SubOrderStep }) {
  const type = step.step_type as StepType;
  const sm = STEP_META[type] ?? STEP_META.purchase;
  const kc = kindColor(type);
  const Icon = sm.icon;
  const quiet = step.state === 'done' || step.state === 'locked';
  const mark = STATE_MARK[step.state];
  const MarkIcon = mark?.icon;
  return (
    <div title={`${sm.label}: ${stepStateLabel(step.state)}`}
      style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 11px',
        border: `1px solid ${kc.border}`, borderRadius: 'var(--r-sm)', background: kc.bg,
        opacity: quiet ? 0.5 : 1, cursor: 'help',
      }}>
      <span style={{
        width: 26, height: 26, borderRadius: 5, flexShrink: 0, background: '#fff',
        border: `1px solid ${kc.border}`, color: kc.fg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={13} />
      </span>
      <span style={{ minWidth: 0, flex: 1, font: '700 12.5px var(--font-body)', color: 'var(--fg-1)' }}>
        {sm.label}
      </span>
      {MarkIcon && <MarkIcon size={14} style={{ color: mark.color, flexShrink: 0 }} />}
    </div>
  );
}

/**
 * Fachlicher Zustand eines Moduls für seinen **Kopf** (Notiz #247): Beschaffung und Verkauf
 * haben einen eigenen Fortschritt (Angefragt → Offeriert → Bestellt → Geliefert), und der
 * gehört dorthin, wo man ihn ohne Öffnen sieht – nicht in die Fläche des Panels.
 */
// Fachlicher Zwischenstand im Modul-Kopf (Beschaffung/Verkauf) – aber NUR, solange der
// Schritt läuft (Notiz #279): ist er erledigt, sagt das der Haken daneben, und «Geliefert»
// stünde als zweites Wort für dieselbe Aussage daneben.
function stepBadge(s: OrderStep): React.ReactNode {
  if (s.state === 'done') return null;
  const po = (s.purchases ?? [])[0];
  if (po?.status) return <StatusBadge cfg={purchaseStatusConfig(po.status)} size={10} />;
  const sale = (s.sales ?? [])[0];
  if (sale?.status) return <StatusBadge cfg={saleStatusConfig(sale.status)} size={10} />;
  return null;
}

// Kurzzeile je Modul: WAS gerade Sache ist – nicht die Konfiguration (die steht am Artikel).
//
// Für «angehalten» steht hier bewusst NICHTS mehr: ruht der Auftrag, sind ALLE Schritte
// blockiert – «Bestand fehlt» stünde dann an jedem einzelnen, obwohl es nur einen Grund gibt.
// Der steht dort, wo er hingehört: beim Unter-Auftrag, der die Menge bindet (#354), bzw. in
// der einen Notiz unter dem Fluss.
function stepDetail(s: OrderStep): React.ReactNode {
  if (s.state === 'failed') return 'Nicht bestanden – über die Abweichung klären';
  return undefined;
}
