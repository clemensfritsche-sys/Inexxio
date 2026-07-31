'use client';

import { Truck, Check, X, PauseCircle, TriangleAlert, PackagePlus, CheckCircle2 } from 'lucide-react';
import type { OrderDeviationInfo, OrderStep, StepResolution, StepType } from '@/types';
import { STEP_META } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { saleStatusConfig } from '@/lib/sale';
import { Connector, FlowTerm, STEP_MAXW, kindColor } from '@/components/erp/process-steps';

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
// den Schritt AUFHÄLT, steht VOR ihm (Abweichung, Nachschub – erst das hier, dann dieser
// Schritt); was aus ihm FOLGT, danach (Bereitstellung: die Ware kommt an, nachdem bestellt
// wurde). Vorher stand alles darunter – also nach einem Schritt, den man womöglich noch gar
// nicht begonnen hatte, und das las sich als «danach passiert».
//
// Ein Unter-Auftrag OHNE Ursprungsschritt (an der Instanz gemeldet, oder bevor ein Schritt
// aktiv war) gehört keinem Schritt – er gehört dem Auftrag und steht am Anfang des Flusses.

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

export function OrderFlow({ steps, deviations = [], waitingFor = [], missing, selectedId, onSelectStep, onOpenOrder, renderPanel }: {
  steps: OrderStep[];
  /** Alle Unter-Aufträge des Auftrags – die ohne Ursprungsschritt stehen vor dem Fluss. */
  deviations?: OrderDeviationInfo[];
  /** Unter-Aufträge, die die Fehlmenge des Auftrags gerade binden (``OrderResponse.waiting_for``). */
  waitingFor?: number[];
  /** Was dem Auftrag fehlt, als eine Zeile – steht beim Unter-Auftrag, der es bindet (#354). */
  missing?: string;
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
}) {
  if (steps.length === 0) return null;

  const rows: React.ReactNode[] = [];
  const subCard = (info: OrderDeviationInfo) => (
    <SubOrderCard key={`sub-${info.object_id}`} info={info} onOpen={onOpenOrder}
      missing={waitingFor.includes(info.object_id) ? missing : undefined} />
  );

  // Was kein Schritt für sich beansprucht, gehört dem Auftrag – und steht am Anfang.
  const claimed = new Set(steps.flatMap((s) => (s.deviations ?? []).map((d) => d.object_id)));
  rows.push(...deviations.filter((x) => !claimed.has(x.object_id)).map(subCard));

  for (const s of steps) {
    const meta = STEP_META[s.step_type as StepType] ?? STEP_META.purchase;
    const selected = selectedId === String(s.id);
    const card = (
      <FlowCard
        key={`step-${s.id}`}
        type={s.step_type as StepType}
        label={meta.label}
        icon={meta.icon}
        detail={stepDetail(s)}
        badge={stepBadge(s)}
        resolutions={s.resolutions ?? []}
        state={s.state}
        hint={completionHint(s)}
        selected={selected}
        onClick={() => onSelectStep(String(s.id))}
      >
        {selected && renderPanel?.(s)}
      </FlowCard>
    );
    // **Was den Schritt AUFHÄLT, steht VOR ihm; was aus ihm FOLGT, danach** (Notiz #372).
    //
    // Eine Abweichung und ein Nachschub sind Hindernisse: solange sie offen sind, kann der
    // Schritt nicht laufen – von oben nach unten gelesen heisst das «erst das hier, dann
    // dieser Schritt». Vorher standen sie darunter, also nach einem Schritt, den man noch
    // gar nicht begonnen hatte; das las sich als «danach passiert» und war schlicht falsch.
    //
    // Die **Bereitstellung** ist das Gegenstück: sie folgt aus dem Schritt (die Ware kommt
    // an, nachdem bestellt wurde) – ausser bei der Ressource, wo das Material vorher da sein
    // muss. Diese Regel steht im Backend (``provisioning._STAGE_BEFORE``); hier wird nur
    // platziert.
    const blocking = (s.deviations ?? []).map(subCard);
    const prov = (s.provisionings ?? []).map(subCard);
    if (s.provisioning_stage === 'before') rows.push(...prov, ...blocking, card);
    else rows.push(...blocking, card, ...prov);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <FlowTerm kind="start" />
      {rows.map((r, i) => (
        <div key={i} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Connector />
          {r}
        </div>
      ))}
      <Connector />
      <FlowTerm kind="end" />
    </div>
  );
}

// Zustands-Symbol statt Zustands-Wort. Kein Symbol für «aktiv» – dass ein Schritt dran ist,
// sagt bereits die Farbe (er ist der einzige, der nicht zurücktritt).
const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done:    { icon: Check,       color: 'var(--success)' },
  blocked: { icon: PauseCircle, color: 'var(--warning)' },
  failed:  { icon: X,           color: 'var(--danger)' },
};

function FlowCard({ type, label, icon: Icon, detail, badge, resolutions = [], state, hint, selected, onClick, children }: {
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
  onClick: () => void;
  children?: React.ReactNode;
}) {
  const kc = kindColor(type);
  // «Nicht relevant» = erledigt oder noch nicht erreicht: die Karte tritt zurück (weisse
  // Fläche, gedämpft). Nur was JETZT dran ist (aktiv/angehalten/Fehler), trägt seine Farbe.
  const muted = state === 'done' || state === 'locked';
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
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px', cursor: 'pointer' }}>
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
 * «Ersetzt» / «Ohne Ersatz weiter» – die Entscheidung, die eine Unterdeckung hier aufgelöst
 * hat. Sie steht dort, wo sie gefallen ist: am Schritt, der blockiert war. Wer/wann im Hover.
 */
function ResolutionLine({ r }: { r: StepResolution }) {
  const who = [r.by, r.at ? new Date(r.at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' }) : null]
    .filter(Boolean).join(' · ');
  const Icon = r.kind === 'quantity_confirmed' ? CheckCircle2 : PackagePlus;
  return (
    <div title={who || undefined}
      style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
        font: '500 12px var(--font-body)', color: 'var(--fg-3)', cursor: who ? 'help' : 'default' }}>
      <Icon size={13} style={{ color: 'var(--success)', flexShrink: 0 }} />
      {r.kind === 'quantity_confirmed' ? (
        <span>
          Menge angepasst
          <b style={{ marginLeft: 5, color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>
            {r.quantity_from} → {r.quantity_to}
          </b>
        </span>
      ) : (
        <span>
          <b style={{ color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>{r.quantity}</b> ab Lager ersetzt
        </span>
      )}
      {r.article_name && <span style={{ color: 'var(--fg-4)' }}>· {r.article_name}</span>}
    </div>
  );
}

// Die drei Arten von Unter-Auftrag – EIN Muster, drei Beschriftungen. Alle drei sind
// eigenständige Aufträge, die aus einem Schritt hervorgegangen sind; sie unterscheiden sich
// nur darin, WARUM (siehe ``orders.reason``).
const SUB_META: Record<string, { label: string; icon: React.ElementType; open: string; done: string }> = {
  deviation: {
    label: 'Abweichung', icon: TriangleAlert,
    open: 'Offene Abweichung – ihr Stück fehlt dem Auftrag, bis sie geklärt ist',
    done: 'Geklärte Abweichung',
  },
  supply: {
    label: 'Nachschub', icon: PackagePlus,
    open: 'Nachschub läuft – der Schritt wird von selbst wieder aktiv',
    done: 'Erledigter Nachschub',
  },
  provisioning: {
    label: 'Bereitstellung', icon: Truck,
    open: 'Material wird an seinen Ort gebracht',
    done: 'Material ist an seinem Ort',
  },
};

/**
 * **Ein Unter-Auftrag als Knoten im Fluss** – zwischen den Modulen, an der Stelle, an der er
 * entstanden ist (Notiz #353). Eingerückt, weil er kein Modul DIESES Prozesses ist, sondern
 * ein eigener Auftrag, der hier hineinragt; ein Klick öffnet ihn.
 *
 * Solange er offen ist, trägt er den Grund, warum der Prozess ruht – WAS fehlt, steht an
 * dieser einen Stelle (Notiz #354) und nicht zusätzlich als Kasten unter dem Fluss.
 */
function SubOrderCard({ info, missing, onOpen }: {
  info: OrderDeviationInfo; missing?: string; onOpen?: (id: number) => void;
}) {
  const open = info.status === 'draft' || info.status === 'released';
  const meta = SUB_META[info.reason ?? 'deviation'] ?? SUB_META.deviation;
  const Icon = meta.icon;
  const tone = open ? 'var(--warning)' : 'var(--border-1)';
  return (
    <div style={{ width: '100%', maxWidth: STEP_MAXW, display: 'flex', paddingLeft: 30 }}>
      <button type="button" onClick={() => onOpen?.(info.object_id)} title={open ? meta.open : meta.done}
        style={{
          flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 11, textAlign: 'left',
          padding: '11px 14px', borderRadius: 'var(--r-lg)', cursor: 'pointer',
          border: `1px solid ${tone}`, background: open ? 'var(--warning-bg)' : '#fff',
          opacity: open ? 1 : 0.6,
        }}>
        <span style={{
          width: 30, height: 30, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff',
          border: `1px solid ${tone}`, color: open ? 'var(--warning)' : 'var(--fg-4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={15} />
        </span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>{meta.label}</span>
            <ObjId value={info.object_id} />
          </span>
          {missing && (
            <span style={{ display: 'block', marginTop: 3, font: '500 12px var(--font-body)', color: 'var(--warning)' }}>
              Es fehlt {missing}
            </span>
          )}
        </span>
        {open && <PauseCircle size={16} style={{ color: 'var(--warning)', flexShrink: 0 }} />}
        {!open && <Check size={16} style={{ color: 'var(--success)', flexShrink: 0 }} />}
      </button>
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
function stepDetail(s: OrderStep): React.ReactNode {
  if (s.state === 'blocked') {
    // Zwei Gründe, warum ein Schritt hängt – und nur diese beiden: das Material ist noch
    // unterwegs, oder es fehlt. WAS fehlt, steht einmal am Auftrag (nicht je Schritt).
    if ((s.provisioning_order_object_ids ?? []).length > 0) return 'Material ist unterwegs';
    return 'Bestand fehlt';
  }
  if (s.state === 'failed') return 'Nicht bestanden – über die Abweichung klären';
  return undefined;
}
