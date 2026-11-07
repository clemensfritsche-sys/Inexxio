'use client';

import { useState, type CSSProperties, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, CornerUpLeft, Flag, GitBranch, MoreHorizontal, Play, Scissors, Sprout } from 'lucide-react';
import { TYPE_META } from '@/lib/erp-record';
import { BEND, FLOW_GAP, FlowNode, LANE, POINT, polyPath, port, type FlowAnchor } from './process-flow';
import { UnitNumber } from './unit-number';
import { statusCfg, isPickable, IM_PROZESS, START_AFTER, START_BEFORE, END_BEFORE, statusLabel } from '@/lib/process-status';
import { formatObjectId } from '@/lib/utils';
import { whenTitle } from '@/lib/when';
import { useErpNav } from './obj-id';
import { StatusDot } from './fields';
import type { GraphEdge, GraphUnits, JourneyStop, ProcessEventResponse, ProcessGraph } from '@/types';
import { DiagramMode, DiagramStep, JOURNEY_LIMIT, JourneyOrigin, columnRows, hasJourney, historyTip, journeyId } from '@/lib/process-graph';
import { StepCard } from '@/components/erp/module-card';

/**
 * **Die Prozessdarstellung — EINE Komponente, zwei Modi.**
 *
 * | Modus | Wo | Was |
 * |---|---|---|
 * | `definition` | Auftragsentwurf und Artikel-Spezifikation | Module anlegen, löschen, sortieren |
 * | `ausfuehrung` | freigegebener Auftrag | Zustand je Objekt, aktuelle Stelle, Ausführung |
 *
 * Zweimal zu bauen wäre an dieser Stelle der teuerste Fehler (PROCESS_CORE.md §8.1) —
 * darum ist der Modus ein Schalter und kein zweites Bauteil. Beide Modi werden **schon
 * im Auftrag** gebraucht (Entwurf ↔ freigegeben); der Artikel benutzt nur den ersten
 * und ist damit kein neuer Fall.
 *
 * Die **Definition der Einzelinstanzen** ist bewusst **nicht** Teil dieses Diagramms,
 * sondern ein Slot darüber (`head`): ein Artikel hat keine Einzelinstanzen, und ein
 * Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar.
 *
 * **Ein Prozessobjekt = eine Komponente.** Start, Modul und Ende teilen sich `FlowNode`;
 * der Modultyp ist Konfiguration, nicht ein eigenes Bauteil.
 */

/**
 * **Der Herkunfts-/Verbleibsbaum — dieselbe Linie, nur verzweigt.**
 *
 * Oben und unten am Prozess steht, aus welchen Aufträgen die Einzelinstanzen kamen und
 * wohin sie gingen. Das war eine Textzeile neben dem Bild; jetzt ist es ein **Ast** am
 * selben Strang: jeder Nachbar fällt auf einen gemeinsamen Bus und läuft von dort in
 * das Start- bzw. aus dem Ende-Objekt.
 *
 * **Gruppiert, nicht aufgezählt** — je Nachbar eine Verzweigung mit Anzahl, nicht je
 * Stück eine Linie. Bei drei Instanzen sieht man dasselbe wie bei 5000; wer die Nummern
 * braucht, öffnet den Nachbarn, und dort ist er die Mitte. Zwei Ebenen, mehr nicht:
 * Rekursion im Bild wäre Tiefe ohne Grenze.
 *
 * **Ein Bus, kein Bündel.** Alle Äste treffen sich auf **einer** Waagrechten und teilen
 * sich danach den Weg in den Knoten – wie in jedem Stammbaum. Das ist keine Überlagerung
 * zweier Aussagen (§8.1a″), sondern die Zusammenführung selbst; darum brauchen sie auch
 * keine eigenen Kanäle. Möglich ist das nur, weil die Zeile **nicht umbricht**: sonst
 * fiele ein Ast der oberen Reihe durch die untere.
 */
function fanPaths(anchors: Record<string, FlowAnchor>, prefix: string,
                  where: 'in' | 'out', keys: Array<string | number>,
                  outTrunk: string): string[] {
  const at = (id: string) => anchors[`${prefix}${id}`];
  const trunk = where === 'in' ? at('start') : at(outTrunk);
  if (!trunk) return [];
  const bus = where === 'in' ? trunk.top - BEND : trunk.bottom + BEND;
  return keys.flatMap((k) => {
    const c = at(journeyId(where, k));
    if (!c) return [];
    return [where === 'in'
      ? polyPath([[c.cx, c.bottom], [c.cx, bus], [trunk.cx, bus], [trunk.cx, trunk.top]])
      : polyPath([[trunk.cx, trunk.bottom], [trunk.cx, bus], [c.cx, bus], [c.cx, c.top]])];
  });
}

/**
 * Ein einzelnes Stück, wenn jemand einen Zustandspunkt aufklappt.
 *
 * Mehr als die Nummer, weil an dieser Stelle zwei Fragen gestellt werden: *welches Stück*
 * und *seit wann läuft es hier* (#689). Der Zeitpunkt kommt aus dem Ereignis-Log; ein
 * Feld dafür gäbe es nicht zu bauen.
 */
interface UnitChip {
  number: string;
  startedAt?: string | null;
  /**
   * **Der Zustand reist mit dem Stück.** Er kommt vom Server (die Antwort trägt ihn
   * längst) und wird hier gebraucht, weil aus ihm folgt, ob das Stück noch greifbar ist.
   *
   * Er wurde einmal beim Einlesen weggeworfen – und damit war der Abweichungstrigger
   * blind: er erschien auch an einem **verschrotteten** Stück, das der Server danach
   * ablehnte. Eine Angabe, die man wegwirft und dann nicht prüfen kann, ist die Form,
   * in der eine Regel an der Oberfläche verschwindet.
   */
  status?: string | null;
}

/**
 * **Die Breite gehört zum Prozessbild, nicht zu seinem Aufrufer** (Testnotiz #684).
 *
 * Es war schon EINE Komponente – aber der Artikel stellte sie in einen 880-px-Container
 * und der Auftrag in einen 620er, und damit sahen dieselben Module verschieden breit
 * aus. Eine visuelle Abweichung ist der Beweis, dass irgendwo zwei Stände sind; hier war
 * es nicht die Komponente, sondern das Mass. Also bringt sie es selbst mit: der Prozess
 * sieht überall gleich aus, weil ihn niemand mehr messen kann.
 */
export const PROCESS_MAXW = LANE.MID_MAX;

/**
 * **Was in einer Spalte steht.**
 *
 * Ausdrücklich benannt, weil die Mitte des Bildes von aussen kommt: der laufende Auftrag
 * bestückt sie anders als ein Entwurf, aber es ist **dieselbe** Spalte (Auftrag §2). Ein
 * zweiter Satz Felder dafür wäre die zweite Darstellung, die es hier nie geben darf.
 */
export interface ColumnProps {
  /** **Das Bild dieser Spalte** – vom Server, nicht hier abgeleitet. */
  graph: ProcessGraph;
  /** Der Inhalt der Module. Der Graph sagt *wo* ein Modul steht, dies *was* darin steht. */
  steps: DiagramStep[];
  /** Kennung dieser Spalte im gemeinsamen Rahmen – sonst kollidieren die Knoten-Ids. */
  prefix?: string;
  mode: DiagramMode;
  activeStepId?: number | null;
  /** Welches Modul startet **aufgeklappt** (#696). Sonst sind alle zu. */
  expandedStepId?: number | null;
  endStatus: string;
  head?: ReactNode;
  tail?: ReactNode;
  onDelete?: (id: number) => void;
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  onExpand?: (edgeId: string) => Promise<UnitChip[]>;
  onReorder?: (from: number, to: number) => void;
  dragging?: number | null;
  onDragState?: (index: number | null) => void;
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /**
   * **Kontext statt Fokus** (Auftrag §4) – ein fremder Auftrag daneben.
   *
   * Er tritt **tonal** zurück: entsättigt und leiser. Das ist bewusst das einzige
   * Mittel. Eine abgesetzte Fläche oder eine senkrechte Trennlinie wären die
   * naheliegenden Alternativen – aber die Querverbindungen laufen **durch** jede
   * Spurgrenze; eine gezeichnete Kante würde von jeder Abzweigung geschnitten und
   * brächte genau die Unruhe zurück, die hier weg soll. Ton kann man nicht schneiden.
   *
   * Die **Linie** dorthin bleibt voll: sie gehört zu diesem Fluss, nicht zum Nachbarn.
   */
  faded?: boolean;
  /** **Abweichung an genau diesem Stück** (Abweichungsauftrag §3.1): der Auslöser sitzt
   *  dort, wo das Stück gerade im Prozess steht – nicht in einem Menü darüber. */
  onDeviate?: (unitNumber: string) => void;
  /** Warum der Auslöser gerade gesperrt ist. Gesetzt = gesperrt, mit Grund im Hover. */
  deviateBlocked?: string;
  /**
   * **Die Spalte in ein fremdes Raster stellen** – `display: contents` löst den eigenen
   * Behälter auf, sodass die Knoten unmittelbar Kinder des äusseren Rasters werden.
   *
   * Das ist der Preis dafür, dass es **eine** Spaltenkomponente gibt und nicht zwei: das
   * Bild mit drei Spuren braucht dieselben Knoten in seinen Zeilen (damit eine Zeile mit
   * einem Nebenauftrag die Hauptachse mitwachsen lässt), und ein zweiter Renderer dafür
   * wäre eine zweite Darstellungsform derselben Sache.
   */
  containerStyle?: CSSProperties;
  /** Je Zeile ihr Platz im äusseren Raster. Ohne Raster leer – dann trägt der Fluss. */
  rowStyle?: (index: number) => CSSProperties;
  /** **Hier entstandene** Stücke – die eine Herkunft, die nicht im Log steht. */
  origins?: JourneyOrigin[];
  /** Der Ereignis-Log – **am Objekt**, an dem er passiert ist (§5). */
  events?: ProcessEventResponse[];
  eventTotal?: number;
  /** Nur im Entwurf: die geplanten Rückführungen – der Schalter am Anfang ihrer Linie. */
  returns?: ReturnTarget[];
  onToggleReturn?: (parentObjectId: number) => void;
}

/**
 * **Eine geplante Rückführung** – ein Quell-Auftrag und die Frage, ob es zu ihm zurückgeht.
 */
interface ReturnTarget {
  objectId: number;
  on: boolean;
}

/**
 * **Eine Spalte des Bildes.** Sie zeichnet ihre Knoten in den Rahmen, in dem sie steht –
 * eigene Linien hat sie nicht. Genau dadurch lassen sich mehrere Spalten in **einem**
 * Rahmen zeigen (übergeordneter Auftrag · eigener Ablauf · Abweichungen) und die Linien
 * dazwischen aus denselben gemessenen Ankern berechnen.
 */
export function FlowColumn({
  graph, steps, prefix = '', mode, activeStepId = null, expandedStepId = null, endStatus,
  head, tail, onDelete,
  renderStep, onExpand, onReorder, dragging, onDragState,
  journeyIn = [], journeyOut = [], faded = false, onDeviate, deviateBlocked,
  containerStyle, rowStyle, origins = [],
  events = [], eventTotal, returns = [], onToggleReturn,
}: ColumnProps) {
  const running = mode === 'ausfuehrung';
  // **Eingeklappt, ausser das Modul ist dran** (#696) – EINE Regel, EINE Stelle. Sie
  // stand zweimal (einmal je Rahmen-Aufrufer), und damit war «dran» im laufenden Auftrag
  // eine andere Frage als im Entwurf. Hier ist sie dieselbe: läuft er, ist es das aktive
  // Modul; im Entwurf das zuletzt angelegte.
  const openId = running ? activeStepId : expandedStepId;
  // **Eine Bedingung, eine Zeile.** Ob es die Herkunfts-Zeile gibt, entscheidet
  // dieselbe Frage wie im Raster daneben (`ProcessColumns.mid.rows`): kommt etwas aus
  // einem Auftrag ODER entsteht etwas hier. Zwei Formulierungen davon hiessen: das
  // Raster zählt eine Zeile, die Spalte rendert sie nicht – und alles darunter sitzt
  // eine Zeile daneben.
  const rows = columnRows(graph, {
    head: !!head, tail: !!tail,
    journeyIn: hasJourney(journeyIn, origins), journeyOut: journeyOut.length > 0,
    returns: returns.length > 0,
  });
  const byId = new Map(steps.map((s) => [s.id, s]));
  const place = (i: number, extra?: CSSProperties): CSSProperties => ({
    ...extra, ...rowStyle?.(i),
  });
  return (
    <div style={{
      // **Derselbe Takt wie im Raster** (`FLOW_GAP`): zwei Prozesspunkte müssen weit
      // genug auseinander liegen, dass die **Waagrechten** ihrer Querlinien als zwei
      // Linien lesbar bleiben. Eine eigene Zahl hier wäre ein zweiter Rhythmus – und in
      // einer Nachbarspalte, die selbst Abzweigungen trägt, prompt eine Überlagerung.
      // (Genau dort ist sie aufgetreten: dieselbe Spalte, nur nicht in der Mitte.)
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: FLOW_GAP,
      opacity: faded ? 0.55 : 1,
      filter: faded ? 'saturate(0.15)' : undefined,
      ...containerStyle,
    }}>
      {rows.map((row, i) => {
        if ('slot' in row) {
          const body = row.slot === 'head' ? head
            : row.slot === 'tail' ? tail
              : row.slot === 'return'
                ? <ReturnRow targets={returns} onToggle={onToggleReturn} />
                : <JourneyRow
                  where={row.slot === 'journey-in' ? 'in' : 'out'}
                  stops={(row.slot === 'journey-in' ? journeyIn : journeyOut)
                    .slice(0, JOURNEY_LIMIT)}
                  origins={row.slot === 'journey-in' ? origins : []}
                  rest={Math.max(0, (row.slot === 'journey-in' ? journeyIn : journeyOut).length
                    - JOURNEY_LIMIT)}
                  prefix={prefix} />;
          return (
            <FlowNode key={row.key} id={`${prefix}${row.key}`}
              style={place(i, { width: '100%' })}>{body}</FlowNode>
          );
        }
        // **Eine Kante trägt ihre Stücke.** Sie stehen nicht in einem Knoten, sondern
        // auf dem Weg zum nächsten – und die Pille sitzt genau dort, auf der Linie.
        if ('edge' in row) {
          return (
            <FlowNode key={row.key} id={`${prefix}${row.key}`} style={place(i, { width: '100%' })}>
              <StateRow
                units={row.edge.units ?? []}
                edgeId={row.edge.id}
                away={row.edge.kind === 'out'}
                onExpand={onExpand}
                onDeviate={onDeviate}
                deviateBlocked={deviateBlocked}
              />
            </FlowNode>
          );
        }
        const n = row.node;
        const id = `${prefix}${n.id}`;
        if (n.kind === 'start' || n.kind === 'end') {
          return (
            <FlowNode key={row.key} id={id} style={place(i)}>
              <Terminal which={n.kind} endStatus={endStatus}
                history={historyTip(events, n, eventTotal)} />
            </FlowNode>
          );
        }
        if (n.kind === 'fork' || n.kind === 'join') {
          return (
            <FlowNode key={row.key} id={id} style={place(i)}>
              <Point kind={n.kind} />
            </FlowNode>
          );
        }
        const step = n.at !== null && n.at !== undefined ? byId.get(n.at) : undefined;
        if (!step) return null;
        const isActive = running && step.id === activeStepId;
        const index = steps.indexOf(step);
        return (
          <FlowNode key={row.key} id={id} style={place(i, { width: '100%' })}>
            <StepCard
              step={step}
              active={isActive}
              // **Gedämpft wird nur, wo nichts mehr zu tun ist** (#821) – die Frage
              // stellt der Schritt, nicht diese Zeile.
              dimmed={running && !isActive && !step.openActions}
              history={historyTip(events, n, eventTotal)}
              defaultOpen={step.id === openId}
              onDelete={mode === 'definition' && onDelete ? () => onDelete(step.id) : undefined}
              drag={onReorder && mode === 'definition' ? {
                index,
                over: dragging !== null && dragging !== index,
                onStart: () => onDragState?.(index),
                onEnd: () => onDragState?.(null),
                onDrop: (from) => { onReorder(from, index); onDragState?.(null); },
              } : undefined}
            >
              {renderStep?.(step, isActive)}
            </StepCard>
          </FlowNode>
        );
      })}
      {(graph.problems ?? []).length > 0 && <Problems list={graph.problems ?? []} />}
    </div>
  );
}

/**
 * **Abzweige- und Rückführpunkt** – die Stelle, an der sich der Strang teilt bzw. wieder
 * zusammenläuft. Ein Punkt auf der Linie, sonst nichts: was hier passiert, sagen die
 * Linien, die ihn berühren, und die Stücke, die daneben stehen.
 */
function Point({ kind }: { kind: string }) {
  return (
    <span
      style={{
        display: 'block', width: POINT, height: POINT, borderRadius: 999,
        border: '2px solid var(--fg-2)', background: 'var(--bg-1)',
      }}
      data-tip={kind === 'fork' ? 'Hier ist ein Stück ausgeschert'
        : 'Hierher kehrt ein Stück zurück'}
    />
  );
}

/**
 * **Der Schalter sitzt am ANFANG der Rückführungslinie** (Auftrag §5).
 *
 * Drei Anläufe, und der Unterschied ist jedes Mal, *wo* die Entscheidung steht:
 *
 * | | |
 * |---|---|
 * | Knopfpaar an der Stückauswahl | die Aussage stand woanders als ihre Wirkung |
 * | Ersatz-Knoten mit eigener Linie | zwei Rückweg-Linien für **eine** Entscheidung |
 * | Klick auf die ganze Nachbarspalte | kein Bedienelement, nur eine grosse Fläche |
 *
 * Jetzt: **eine Pille unter dem Ende-Objekt** – und die echte Rückführungslinie geht von
 * genau dort ab (sie dockt an der letzten Zeile dieser Spalte an, §8.1a″). Der Schalter
 * ist damit sichtbar ein Bedienelement, steht auf der Linie, die er schaltet, und
 * **bleibt**, wenn sie geht: sonst wäre die Entscheidung einmalig statt änderbar.
 *
 * Die Linie selbst bleibt die Antwort – ist sie da, geht es zurück. Kein Strichmuster,
 * keine dritte Stärke, keine zweite Linie.
 */
function ReturnRow({ targets, onToggle }: {
  targets: ReturnTarget[]; onToggle?: (objectId: number) => void;
}) {
  return (
    <div className="w-full flex flex-wrap items-center justify-center gap-1.5">
      {targets.map((t) => (
        <button
          key={t.objectId}
          type="button"
          disabled={!onToggle}
          onClick={() => onToggle?.(t.objectId)}
          className="inline-flex items-center gap-1.5 rounded-full text-xs"
          // **Kein Strichmuster, auch nicht am Rand.** Der Schalter steht am Anfang einer
          // Linie; ein gestrichelter Rahmen dort läse sich als dritte Linienart (§8.1a).
          // Sein Zustand steht ohnehin zweifach da: im Symbol und im Wort.
          style={{
            minHeight: 36, padding: '7px 12px',
            border: `1px solid var(${t.on ? '--border-2' : '--border-1'})`,
            background: t.on ? 'var(--bg-1)' : 'transparent',
            color: t.on ? 'var(--fg-2)' : 'var(--fg-4)',
            cursor: onToggle ? 'pointer' : 'default',
          }}
          data-tip={t.on
            ? `Nach dem Durchlauf geht jedes Stück an genau die Stelle in Auftrag `
              + `${formatObjectId(t.objectId)} zurück, an der es ausgeschert ist. `
              + `Klicken kappt die Rückführung.`
            : `Die Stücke bleiben hier; Auftrag ${formatObjectId(t.objectId)} läuft mit `
              + `weniger weiter. Klicken führt sie wieder zurück.`}
        >
          {t.on ? <CornerUpLeft size={13} /> : <Scissors size={13} />}
          {t.on ? 'kehrt zurück' : 'bleibt hier'}
          {targets.length > 1 && (
            <span className="ix-tnum" style={{ color: 'var(--fg-4)' }}>
              {formatObjectId(t.objectId)}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/**
 * **Sichtbar kaputt statt still falsch.**
 *
 * Ein Bild, das eine Einzelinstanz verliert oder doppelt zeigt, ist schlimmer als
 * keines – es sieht ja vollständig aus. Verletzt der Graph eine Invariante, sagt die
 * Oberfläche das an der Stelle, an der man sonst der Zeichnung glauben würde.
 */
function Problems({ list }: { list: string[] }) {
  return (
    <div className="w-full rounded-ds-lg text-[12px]"
      style={{ border: '1px solid var(--danger)', background: 'var(--danger-bg)',
               color: 'var(--danger)', padding: '8px 11px' }}>
      <strong>Das Bild ist nicht verlässlich.</strong>
      <ul className="mt-1 list-disc pl-4">
        {list.map((p) => <li key={p}>{p}</li>)}
      </ul>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Linien — berechnet aus gemessenen Ankern, nirgends eingetragen
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Die Achse einer Spalte.** Je Kante ein Zug, von Knoten zu Knoten – senkrecht heraus
 * und senkrecht hinein (§8.1a).
 *
 * Ob eine Kante kräftig ist, steht **an der Kante** und wird hier nicht gerechnet: der
 * Server hat es aus dem Log abgeleitet – nie aus dem aktuellen Zustand.
 */
export function Axis({ edges, anchors, prefix = '', journeyIn = [], journeyOut = [] }: {
  edges: GraphEdge[]; anchors: Record<string, FlowAnchor>; prefix?: string;
  /** Die Äste des Herkunfts-/Verbleibsbaums – Schlüssel, keine Geometrie. */
  journeyIn?: Array<string | number>;
  journeyOut?: Array<string | number>;
}) {
  // **Wo die Achse endet, hängt der Verbleibs-Baum.** Das ist die letzte Achsenkante –
  // die ohne nächsten Knoten. Sie führt hinter dem Ende-Objekt hinaus, bei einem
  // terminalen Modul aus diesem selbst; welcher Fall es ist, muss hier niemand wissen.
  const exit = edges.find((e) => e.to == null);
  const outTrunk = exit && anchors[`${prefix}on:${exit.id}`] ? `on:${exit.id}`
    : (exit?.frm ?? 'end');
  return (
    <>
      {fanPaths(anchors, prefix, 'in', journeyIn, outTrunk).map((d, i) => (
        // **Gegangen**: die Stücke sind von dort gekommen bzw. dorthin gegangen. Ein
        // Ast, der nicht passiert ist, existiert nicht – die Journey kennt nur, was im
        // Log steht.
        <Stroke key={`fan-in-${i}`} d={d} walked />
      ))}
      {fanPaths(anchors, prefix, 'out', journeyOut, outTrunk).map((d, i) => (
        <Stroke key={`fan-out-${i}`} d={d} walked />
      ))}
      {edges.map((e) => {
        const A = anchors[`${prefix}${e.frm}`];
        // Ohne nächsten Knoten führt die Kante zu der Zeile, die ihre Stücke trägt
        // (`columnRows` legt sie unter dem Schlüssel `on:<Kante>` an). Gibt es dort
        // nichts, gibt es auch nichts zu zeichnen.
        const B = anchors[`${prefix}${e.to ?? `on:${e.id}`}`];
        if (!A || !B) return null;
        return (
          <Stroke key={e.id}
            d={polyPath([port(A, 'bottom'), port(B, 'top')])} walked={e.walked} />
        );
      })}
    </>
  );
}

/**
 * **Zwei Stärken, sonst nichts** (§8.1a). Jede Linie des Bildes geht durch dieses eine
 * Bauteil: gegangen ist kräftig, ausstehend eine Haarlinie. Keine dritte Farbe, kein
 * zweiter Linientyp – und darum auch keine Stelle, an der ein dritter entstehen könnte.
 */
export function Stroke({ d, walked }: { d: string; walked: boolean }) {
  if (!d) return null;
  return (
    <path
      d={d}
      fill="none"
      stroke={walked ? 'var(--fg-2)' : 'var(--border-2)'}
      strokeWidth={walked ? 2.5 : 1.5}
      strokeLinecap="round"
    />
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Knoten
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Die Journey** – woher die Stücke dieses Auftrags kamen, wohin sie gingen.
 *
 * Ein Stück ist immer in genau einem Auftrag aktiv; alles ist ein einziger Prozess, nur
 * in Aufträge aufgeteilt. Diese Zeile setzt die Teilung wieder zusammen: über dem Start
 * der Auftrag davor, unter dem Ende der danach.
 *
 * **Gruppiert, nicht aufgezählt.** Bei 5000 Stück wären 5000 Verweise weder darstellbar
 * noch lesbar – und die Frage lautet «wie viele kamen woher», nicht «welche». Wer die
 * einzelnen Stücke sehen will, öffnet den genannten Auftrag; dort stehen sie.
 *
 * Gibt es keinen Nachbarn, steht hier **nichts**: der Knoten entsteht gar nicht erst.
 * Ein Platzhalter «kein Vorgänger» wäre eine Zeile, die nichts sagt.
 */
function JourneyRow({ where, stops, origins, prefix, rest }: {
  where: 'in' | 'out';
  stops: JourneyStop[];
  /** Nur oben: die **hier entstandenen** Stücke – sie haben keinen Vorgänger. */
  origins: JourneyOrigin[];
  prefix: string;
  /** Wie viele Nachbarn nicht gezeigt werden. Gekappt, aber nicht verschwiegen. */
  rest: number;
}) {
  // Der Sprung zum Nachbarn läuft über die **bestehende** Navigation (`ErpNavContext`) –
  // dieselbe, mit der jede Objektnummer im ERP ihren Datensatz öffnet. Ein eigener
  // Handler wäre ein zweiter Weg zur selben Sache.
  const nav = useErpNav();
  // **Der Rest ist kein Ast** (#1035): der «… N»-Hinweis hat keine Linie und steht darum
  // auf einer eigenen Zeile, auf der Seite weg vom Stamm (`where`) – als Kind der
  // zentrierten Chip-Reihe verschöbe er sie um seine halbe Breite.
  const note = rest > 0 && (
    <span className="inline-flex items-center gap-1 text-[11px]"
      style={{ color: 'var(--fg-4)', whiteSpace: 'nowrap' }}
      data-tip="Weitere Nachbarn – sie stehen im jeweiligen Auftrag">
      <MoreHorizontal size={12} /> {rest}
    </span>
  );
  return (
    <div className="flex flex-col items-center" style={{ gap: 4 }}>
    {where === 'in' && note}
    <div className="flex items-start justify-center gap-1.5" style={{ flexWrap: 'nowrap' }}>
      {origins.map((o, i) => (
        <FlowNode key={`new-${i}`} id={`${prefix}${journeyId(where, `new:${i}`)}`}>
          <span
            className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)',
                     color: 'var(--fg-3)', whiteSpace: 'nowrap' }}
            data-tip={`${o.count}× ${o.label} entstehen in diesem Auftrag – kein Vorgänger`}
          >
            <Sprout size={11} style={{ color: 'var(--fg-4)' }} />
            <span className="ix-tnum">{o.count}×</span>
            <span className="truncate" style={{ maxWidth: 120 }}>{o.label}</span>
          </span>
        </FlowNode>
      ))}
      {stops.map((j) => (
        <FlowNode key={j.object_id} id={`${prefix}${journeyId(where, j.object_id)}`}>
          <button
            type="button"
            onClick={nav ? () => nav(j.object_id) : undefined}
            disabled={!nav}
            className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)',
                     color: 'var(--fg-3)', whiteSpace: 'nowrap' }}
            data-tip={`${j.name} · ${j.unit_count} Stück – öffnen`}
          >
            <span className="ix-tnum">{formatObjectId(j.object_id)}</span>
            <span style={{ color: 'var(--fg-4)' }}>· {j.unit_count}</span>
          </button>
        </FlowNode>
      ))}
    </div>
    {where === 'out' && note}
    </div>
  );
}

function Terminal({ which, endStatus, history }: {
  which: 'start' | 'end'; endStatus: string;
  /** Was hier passiert ist – dieselbe Blase wie am Modul (§5). */
  history?: string;
}) {
  const Icon = which === 'start' ? Play : Flag;
  const after = which === 'start' ? START_AFTER : endStatus;
  const before = which === 'start' ? START_BEFORE : END_BEFORE;
  const cfg = statusCfg(after);
  const head = `${which === 'start' ? 'Start' : 'Ende'}: ${statusLabel(before)} → ${statusLabel(after)}`;
  return (
    <div
      className="flex items-center justify-center rounded-full"
      // Fokussierbar, damit die Blase auch **ohne Hover** erscheint – auf dem Touchgerät
      // per Tipp, an der Tastatur per Tab. Ein zweites Muster dafür gibt es nicht.
      tabIndex={history ? 0 : undefined}
      style={{ width: 46, height: 46, border: `2px solid ${cfg.color}`, background: cfg.bg, color: cfg.color }}
      data-tip={history ? `${head}\n${history}` : head}
      data-tip-list={history ? '' : undefined}
    >
      <Icon size={19} />
    </div>
  );
}

/**
 * Was steht hier gerade? **Eine Pille je Zustand, mit Anzahl** – nicht eine je Stück.
 *
 * Bei Menge 5000 wären 5000 Pillen weder darstellbar noch lesbar; und die Frage, die
 * man an dieser Stelle hat, ist «wie viele stehen wo», nicht «welche». Wer die Nummern
 * braucht, klappt auf: dann und nur dann werden sie geholt.
 */
function StateRow({ units, edgeId, away: outward = false, onExpand, onDeviate,
  deviateBlocked }: {
  /** Was auf dieser Kante steht – vom Server gezählt, hier nur gezeigt. */
  units: GraphUnits[];
  /** **Die Position.** Zähler und Aufklappen fragen dieselbe (Befund 2.1). */
  edgeId: string;
  /** Führt die Kante **hinaus** in einen anderen Auftrag? Dann sind es ausgescherte
   *  Stücke – und nur dann. Am `active`-Flag abzulesen wäre falsch: hinter dem Ende
   *  steht ebenfalls Geschlossenes, und das ist keine Abweichung, sondern der Weiterweg. */
  away?: boolean;
  onExpand?: (edgeId: string) => Promise<UnitChip[]>;
  onDeviate?: (unitNumber: string) => void;
  deviateBlocked?: string;
}) {
  const [open, setOpen] = useState(false);
  const [numbers, setNumbers] = useState<UnitChip[] | null>(null);
  const [busy, setBusy] = useState(false);
  const groups = outward ? [] : units;
  /**
   * **Die Linie sagt die Vergangenheit, die Pille die Gegenwart** (Auftrag §1).
   *
   * Beides stand hier einmal in einem Wort: eine ausgescherte Zeile hiess «In
   * Abweichung», für immer – auch wenn der Nachbar längst fertig war und das Stück
   * nirgends mehr in einem Prozess stand. Die Aussage war in der Gegenwartsform und
   * meinte die Vergangenheit.
   *
   * Beantwortet wird sie jetzt aus dem **Status**, den die Kante ohnehin mitbringt: er
   * ist die Gegenwart des Stücks. `im_prozess` heisst «es arbeitet gerade woanders»;
   * alles andere heisst «es ist dort geblieben». Die **Linie** bleibt unberührt – dass
   * hier etwas ausgeschert ist, ist passiert und bleibt wahr.
   */
  const away = outward ? units.filter((u) => u.status === IM_PROZESS) : [];
  const handed = outward ? units.filter((u) => u.status !== IM_PROZESS) : [];
  const total = groups.reduce((n, g) => n + g.count, 0);
  const gone = away.reduce((n, g) => n + g.count, 0);
  const left = handed.reduce((n, g) => n + g.count, 0);
  async function toggle() {
    if (!onExpand) return;
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (numbers === null) {
      setBusy(true);
      try { setNumbers(await onExpand(edgeId)); } finally { setBusy(false); }
    }
  }

  if (!total && !gone && !left) return null;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="flex flex-wrap gap-1.5 justify-center">
        {gone > 0 && (
          // **Ausgeschert und noch dort.** Das Stück steht hier – es arbeitet nur gerade
          // woanders. Es fehlt nicht, und es ist nicht fertig; beides wäre falsch.
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--warning-bg)', color: 'var(--warning)',
                     border: '1px dashed var(--warning)' }}
            data-tip="In einem Abweichungsauftrag – es steht weiterhin an dieser Stelle"
          >
            <GitBranch size={11} /> In Abweichung · {gone}
          </span>
        )}
        {left > 0 && (
          // **Ausgeschert und dort geblieben.** Die Abzweigung bleibt im Bild – sie ist
          // passiert. Nur ist dieses Stück nicht mehr «in Abweichung»: es ist weg.
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--bg-3)', color: 'var(--fg-3)',
                     border: '1px dashed var(--border-2)' }}
            data-tip="Hier ausgeschert und dort geblieben – die Rückführung war gekappt"
          >
            <GitBranch size={11} /> Abgegeben · {left}
          </span>
        )}
        {groups.map((g) => {
          const cfg = statusCfg(g.status);
          const active = g.active;
          return (
            <button
              key={`${g.status}-${g.active}`}
              type="button"
              onClick={toggle}
              disabled={!onExpand}
              // **Hier stehen sie jetzt.** Die kräftige Linie endet an dieser Stelle –
              // der leise Ring ist ihr Fixpunkt in einem langen Bild, in der Farbe, die
              // die Pille ohnehin trägt. Keine zweite Aussage, keine neue Farbe.
              className={`inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum${active ? ' ix-live' : ''}`}
              style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}22`,
                       ['--ix-live' as string]: `${cfg.color}55` }}
              data-tip={onExpand ? 'Nummern anzeigen' : cfg.label}
            >
              <StatusDot color={cfg.color} />
              {cfg.label} · {g.count}
              {onExpand && (open
                ? <ChevronUp size={11} style={{ opacity: 0.6 }} />
                : <ChevronDown size={11} style={{ opacity: 0.6 }} />)}
            </button>
          );
        })}
      </div>
      {open && (
        <div className="flex flex-wrap gap-1 justify-center max-w-full">
          {busy && <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>Lädt …</span>}
          {numbers?.map((u) => (
            <span key={u.number} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded"
              style={{ background: 'var(--bg-3)', color: 'var(--fg-3)' }}
              // **Seit wann läuft dieses Stück hier?** (Testnotiz #689) Aus dem
              // Ereignis-Log – der Start ist ein Ereignis wie jedes andere.
              data-tip={u.startedAt ? `Start passiert: ${whenTitle(u.startedAt)}` : undefined}>
              <UnitNumber value={u.number} size={11} />
              {onDeviate && isPickable(u.status) && (
                // **Der Auslöser sitzt am Stück, an seiner Stelle im Prozess** (§3.1).
                // Er legt nichts an – er öffnet einen gewöhnlichen Auftragsentwurf, in
                // dem dieses Stück schon steht.
                //
                // **An einem Stück in einem Endzustand gibt es ihn nicht.** Nicht
                // ausgegraut, sondern gar nicht: ein Knopf, der nie etwas tun kann, ist
                // kein Angebot. Die Bedingung nennt keinen Status – sie fragt dieselbe
                // Eigenschaft, aus der auch der Server seine Ablehnung zieht.
                <button
                  type="button"
                  onClick={() => onDeviate(u.number)}
                  disabled={!!deviateBlocked}
                  className="flex items-center disabled:opacity-40"
                  style={{ color: 'var(--warning)' }}
                  aria-label={`Auftrag auf ${u.number}`}
                  data-tip={deviateBlocked ?? 'Auftrag auf genau dieses Stück'}
                >
                  {/* **Das reguläre Auftragssymbol** (Testnotiz #728) – aus derselben
                      Zuordnung wie überall (`TYPE_META.order`). Der Knopf legt einen ganz
                      gewöhnlichen Auftrag an; was daraus wird, entscheidet die Auswahl
                      (#608), nicht das Symbol. */}
                  <TYPE_META.order.icon size={11} />
                </button>
              )}
            </span>
          ))}
          {numbers && numbers.length < total && (
            // Ein stumm gekappte Liste sähe aus wie die ganze Wahrheit.
            <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>
              … {numbers.length} von {total}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
