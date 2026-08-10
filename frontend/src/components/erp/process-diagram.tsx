'use client';

import { useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import {
  Blocks, ChevronDown, ChevronUp, CornerUpLeft, Flag, GitBranch, GripVertical, Lock,
  MoreHorizontal, Play, Sprout, Trash2,
} from 'lucide-react';
import { MODULE_ICON, moduleTone } from '@/lib/modules';
import {
  BEND, FLOW_GAP, FlowFrame, FlowNode, LANE, POINT, polyPath, port, type FlowAnchor,
} from './process-flow';
import { UnitNumber } from './unit-number';
import { statusCfg, START_AFTER, START_BEFORE, END_BEFORE, statusLabel } from '@/lib/process-status';
import { formatObjectId, localDateTime } from '@/lib/utils';
import { useErpNav } from './obj-id';
import type {
  GraphEdge, GraphNode, GraphUnits, JourneyStop, ProcessGraph,
} from '@/types';

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

export interface DiagramStep {
  /**
   * **Die Identität des Moduls** (Testnotiz #687). Serverseitig vergeben und
   * unveränderlich; im Entwurf eine lokale Nummer, weil es den Datensatz noch nicht gibt.
   * Der Ereignis-Log zeigt auf sie – nie auf einen Namen, nie auf die Position.
   */
  id: number;
  moduleType: string;
  /** Wie das Modul heisst – **aus seinem Typ abgeleitet**, nicht eingegeben (#682). */
  label: string;
  /**
   * **Worauf dieses Modul wartet** (Testnotiz #698) – Objektnummern der Abweichungen,
   * deren Rückführung aussteht. Nicht leer heisst: gesperrt.
   *
   * Das Modul fragt **nicht selbst**, ob es darf; ihm wird gesagt, dass es nicht darf.
   * Die Sperre wird an einer Stelle gerendert (`StepCard`) und serverseitig durchgesetzt
   * (`process.confirm_step`) – ein künftiges Modul erbt beides, ohne eine Zeile dafür.
   */
  waitingFor?: number[];
}

export type DiagramMode = 'definition' | 'ausfuehrung';

/**
 * **Der Graph eines Entwurfs.** Ein Auftragsentwurf lebt im Browser (§6.1) – es gibt
 * ihn auf dem Server nicht, also kann der ihn auch nicht liefern.
 *
 * Das ist **keine** zweite Ableitung: hier steht keine Prozesslogik, sondern die
 * Definition selbst. Ein Entwurf hat keine Einzelinstanzen, also keine Positionen; er
 * ist nicht gelaufen, also ist keine Kante gegangen; und es gibt nichts, wovon
 * abzuzweigen wäre. Übrig bleibt die Kette Start → Module → Ende, und die *ist* die
 * Liste, die daneben bearbeitet wird.
 */
export function definitionGraph(steps: DiagramStep[],
                                back: ReturnLink[] = []): ProcessGraph {
  const chain: GraphNode[] = [
    { id: 'start', kind: 'start', at: null },
    ...steps.map((s) => ({ id: `module:${s.id}`, kind: 'module', at: s.id })),
    { id: 'end', kind: 'end', at: null },
  ];
  // **Ein Rückweg, eine Zeile** – auch bei mehreren Quellen. Je Quelle einen eigenen
  // Knoten untereinander zu hängen hiesse, die Linie zum zweiten liefe durch den ersten
  // hindurch (§4: keine Linie über einem Knoten); je Quelle eine eigene Spur wäre die
  // Kanal-Maschinerie der Nachbarspalten, mitten im Entwurf. Also: der Rückweg ist EINE
  // Zeile mit n Zielen darin – die Linie sagt **ob**, die Ziele sagen **wohin**.
  const returning = back.some((b) => b.on);
  return {
    nodes: [...chain, ...(back.length ? [{ id: 'back', kind: 'back', at: null }] : [])],
    edges: [
      ...chain.slice(0, -1).map((n, i) => ({
        id: `edge:${n.id}:${chain[i + 1].id}`,
        frm: n.id, to: chain[i + 1].id, kind: 'axis', walked: false, units: [],
      })),
      // **Die Linie ist die Antwort.** Sie gibt es nur, wenn zurückgeführt wird – das
      // Fehlen ist die Aussage, kein Strichmuster und kein zweiter Linientyp.
      ...(returning
        ? [{ id: 'edge:end:back', frm: 'end', to: 'back', kind: 'axis',
             walked: false, units: [] }]
        : []),
    ],
    problems: [],
  };
}

/**
 * **Eine geplante Rückführung im Entwurf.**
 *
 * Ein Auftrag, der einem laufenden ein Stück abnimmt, gibt es zurück – oder eben nicht.
 * Das war ein Knopfpaar («kehrt zurück» / «bleibt hier»), also eine Aussage über etwas,
 * das man daneben nicht sah. Im laufenden Bild sagt es längst **die Linie selbst**: eine
 * gekappte Ausleihe hat keinen Rückweg. Der Entwurf spricht jetzt dieselbe Sprache, mit
 * demselben Bauteil – der Knoten ist der Schalter, die Linie das Ergebnis.
 */
export interface ReturnLink {
  /** Woran die Entscheidung hängt – die Definitionszeile, die die Stücke holt. */
  key: number;
  /** Objektnummern der Aufträge, aus denen diese Zeile Stücke nimmt. */
  orders: number[];
  on: boolean;
}

/**
 * **Eine Zeile im Bild.** Ein Prozessobjekt, die Beschriftung einer Kante – oder eine
 * Zutat, die nicht zum Graph gehört (Definitionsbereich, Modulauswahl, Journey).
 *
 * Die Trennung Knoten ↔ Kante ist die Umsetzung der Regel «eine Position ist **immer**
 * eine Kante»: Stücke stehen nicht *in* einem Knoten, sondern auf dem Weg zum nächsten –
 * und genau dort steht ihre Pille, mitten auf der Linie.
 *
 * **Eine Liste, ein Index.** Das Raster mit drei Spuren braucht je Zeile eine Rasterzeile
 * und muss wissen, in welcher ein bestimmter Knoten steht; die Spalte braucht dieselbe
 * Reihenfolge zum Rendern. Zwei Zählungen davon wären zwei Wahrheiten – und die eine
 * verschöbe den Nebenauftrag gegenüber der anderen um eine Zeile.
 */
export type ColumnRow =
  | { key: string; slot: 'head' | 'tail' | 'journey-in' | 'journey-out' }
  | { key: string; node: GraphNode }
  | { key: string; edge: GraphEdge };

/**
 * Der Graph als Zeilenfolge — reines Layout, keine Ableitung.
 *
 * Die Knoten kommen in der Reihenfolge, in der der Server sie liefert; zwischen zwei
 * Knoten schiebt sich die Beschriftung ihrer Kante, sofern dort etwas steht.
 */
export function columnRows(g: ProcessGraph, extra: {
  head?: boolean; tail?: boolean; journeyIn?: boolean; journeyOut?: boolean;
} = {}): ColumnRow[] {
  const outgoing = new Map<string, GraphEdge>();
  (g.edges ?? []).forEach((e) => { if (e.kind === 'axis') outgoing.set(e.frm, e); });
  const rows: ColumnRow[] = [];
  if (extra.head) rows.push({ key: 'head', slot: 'head' });
  if (extra.journeyIn) rows.push({ key: 'journey-in', slot: 'journey-in' });
  (g.nodes ?? []).forEach((n) => {
    if (extra.tail && n.kind === 'end') rows.push({ key: 'tail', slot: 'tail' });
    rows.push({ key: n.id, node: n });
    // **Was hinausgegangen ist, steht am Abzweigepunkt.** Die out-Kante führt in eine
    // andere Spalte; ihre Stücke stehen aber hier – sie sind an dieser Stelle weg.
    (g.edges ?? [])
      .filter((e) => e.kind === 'out' && e.frm === n.id && (e.units ?? []).length)
      .forEach((e) => rows.push({ key: `on:${e.id}`, edge: e }));
    const e = outgoing.get(n.id);
    if (e && (e.units ?? []).length) rows.push({ key: `on:${e.id}`, edge: e });
  });
  if (extra.journeyOut) rows.push({ key: 'journey-out', slot: 'journey-out' });
  return rows;
}

/** In welcher Zeile steht dieser Knoten? — für das Raster mit drei Spuren. */
export function rowOfNode(rows: ColumnRow[], nodeId: string): number {
  return rows.findIndex((r) => 'node' in r && r.node.id === nodeId);
}

/**
 * **Woher die Stücke kamen, ohne dass sie ein Auftrag hergibt.**
 *
 * Ein Erzeugungsauftrag hat keinen Vorgänger – seine Stücke entstehen bei der Freigabe.
 * Das ist die einzige Herkunft, die nicht im Log steht, weil es davor nichts gab.
 */
export interface JourneyOrigin {
  label: string;
  count: number;
}

/** Wie viele Nachbarn eine Journey-Zeile **vollständig** zeigt (wie `RELATED_LIMIT`). */
export const JOURNEY_LIMIT = 3;

const journeyId = (where: 'in' | 'out', key: string | number) => `j:${where}:${key}`;

/**
 * Die Schlüssel der Äste einer Journey-Zeile — **dieselbe Liste, die sie rendert**.
 *
 * Die Zeile zeigt die Nachbarn und der Linien-Layer verbindet sie; zwei Listen dafür
 * hiessen, dass ein Ast ohne Chip oder ein Chip ohne Ast entstehen kann. Genau diese
 * Klasse Fehler hat den Abzweigepunkt ohne Nachbarn erzeugt.
 */
/** Gibt es die Herkunfts-Zeile? — **die** Bedingung, nicht eine je Aufrufer. */
export const hasJourney = (stops: JourneyStop[], origins: JourneyOrigin[] = []) =>
  stops.length > 0 || origins.length > 0;

export function journeyKeys(stops: JourneyStop[],
                            origins: JourneyOrigin[] = []): Array<string | number> {
  return [
    ...origins.map((_, i) => `new:${i}`),
    ...stops.slice(0, JOURNEY_LIMIT).map((s) => s.object_id),
  ];
}

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
                  where: 'in' | 'out', keys: Array<string | number>): string[] {
  const at = (id: string) => anchors[`${prefix}${id}`];
  // Unten hängt der Baum an der Pille der angekommenen Stücke, wenn es sie gibt – sonst
  // am Ende-Objekt. Beides ist «das Letzte auf der Achse»; welches, sagt das Bild.
  const trunk = where === 'in' ? at('start') : (at('on:edge:end:done') ?? at('end'));
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
 * Die Achsenkanten – alles, was innerhalb einer Spalte zu zeichnen ist.
 *
 * **Auch die Kante hinter dem Ende** (``to = null``). Sie hat keinen nächsten Knoten,
 * aber sehr wohl ein Ziel: die Zeile, auf der ihre Stücke stehen. Ohne sie hing die
 * Pille «angekommen» ohne Anschluss unter dem Ende – und die Rückführung in einen
 * übergeordneten Auftrag, die unter dieser Zeile abgeht, begann im Nichts.
 */
export function axisEdges(g: ProcessGraph): GraphEdge[] {
  return (g.edges ?? []).filter((e) => e.kind === 'axis');
}

/**
 * Ein einzelnes Stück, wenn jemand einen Zustandspunkt aufklappt.
 *
 * Mehr als die Nummer, weil an dieser Stelle zwei Fragen gestellt werden: *welches Stück*
 * und *seit wann läuft es hier* (#689). Der Zeitpunkt kommt aus dem Ereignis-Log; ein
 * Feld dafür gäbe es nicht zu bauen.
 */
export interface UnitChip {
  number: string;
  startedAt?: string | null;
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

export function ProcessDiagram({
  mode, steps, graph, activeStepId = null, expandedStepId = null, endStatus,
  head, tail, onDelete, renderStep, onExpand, tone, onReorder, dragging, onDragState,
  journeyIn = [], journeyOut = [], back = [], onToggleReturn, origins = [],
}: {
  mode: DiagramMode;
  steps: DiagramStep[];
  /** Der Graph vom Server. Fehlt er, ist es ein Entwurf – dann die reine Kette. */
  graph?: ProcessGraph;
  activeStepId?: number | null;
  /** Welches Modul startet aufgeklappt (#696) – im Entwurf das zuletzt angelegte. */
  expandedStepId?: number | null;
  endStatus: string;
  /** Slot über dem Start: die Definition (nur beim Auftrag). */
  head?: ReactNode;
  /** **Journey**: woher die Stücke kamen (über dem Start) und wohin sie gingen (unter
   *  dem Ende). Leer heisst «keiner» – dann steht dort nichts. */
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /** Slot **vor dem Ende**: die Modulauswahl – genau dort, wo das nächste Modul hinkäme. */
  tail?: ReactNode;
  /** Nur im Definitionsmodus: ein Modul entfernen. */
  onDelete?: (id: number) => void;
  /** Was in der Karte steht: im Entwurf die Felder des Moduls, zur Laufzeit seine Arbeit. */
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  /** Eine Position aufklappen: die einzelnen Nummern **dieser Kante** nachladen. */
  onExpand?: (edgeId: string) => Promise<UnitChip[]>;
  /** Farbfamilie je Modultyp. Ohne sie der neutrale Grundton – nie eine leere Fläche. */
  tone?: (moduleType: string) => { bg: string; fg: string; border: string };
  /** Nur im Definitionsmodus: Reihenfolge per Drag & Drop. Sie IST der Prozess. */
  onReorder?: (from: number, to: number) => void;
  dragging?: number | null;
  onDragState?: (index: number | null) => void;
  /** Nur im Entwurf: die geplanten Rückführungen (§5). */
  back?: ReturnLink[];
  onToggleReturn?: (key: number) => void;
  /** **Hier entstandene** Stücke – der Ast ohne Vorgänger. */
  origins?: JourneyOrigin[];
}) {
  const g = useMemo(() => graph ?? definitionGraph(steps, back), [graph, steps, back]);

  return (
    <div className="mx-auto w-full" style={{ maxWidth: PROCESS_MAXW }}>
      <FlowFrame lines={(a) => (
        <Axis edges={axisEdges(g)} anchors={a}
          journeyIn={journeyKeys(journeyIn, origins)} journeyOut={journeyKeys(journeyOut)} />
      )}>
        {() => (
          <FlowColumn
            graph={g} steps={steps} mode={mode} activeStepId={activeStepId}
            expandedStepId={mode === 'ausfuehrung' ? activeStepId : expandedStepId}
            endStatus={endStatus} head={head} tail={tail} onDelete={onDelete}
            renderStep={renderStep} onExpand={onExpand} tone={tone} onReorder={onReorder}
            dragging={dragging} onDragState={onDragState}
            journeyIn={journeyIn} journeyOut={journeyOut} origins={origins}
            back={back} onToggleReturn={onToggleReturn}
          />
        )}
      </FlowFrame>
    </div>
  );
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
  renderStep, onExpand, tone, onReorder, dragging, onDragState,
  journeyIn = [], journeyOut = [], faded = false, onDeviate, deviateBlocked,
  containerStyle, rowStyle, back = [], onToggleReturn, origins = [],
}: {
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
  tone?: (moduleType: string) => { bg: string; fg: string; border: string };
  onReorder?: (from: number, to: number) => void;
  dragging?: number | null;
  onDragState?: (index: number | null) => void;
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /** Ein **fremder** Auftrag daneben: vollständig sichtbar, aber nicht der Fokus. */
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
  /** Nur im Entwurf: die geplanten Rückführungen (§5) – Schalter und Linie zugleich. */
  back?: ReturnLink[];
  onToggleReturn?: (key: number) => void;
  /** **Hier entstandene** Stücke – die eine Herkunft, die nicht im Log steht. */
  origins?: JourneyOrigin[];
}) {
  const running = mode === 'ausfuehrung';
  // **Eine Bedingung, eine Zeile.** Ob es die Herkunfts-Zeile gibt, entscheidet
  // dieselbe Frage wie im Raster daneben (`ProcessColumns.mid.rows`): kommt etwas aus
  // einem Auftrag ODER entsteht etwas hier. Zwei Formulierungen davon hiessen: das
  // Raster zählt eine Zeile, die Spalte rendert sie nicht – und alles darunter sitzt
  // eine Zeile daneben.
  const rows = columnRows(graph, {
    head: !!head, tail: !!tail,
    journeyIn: hasJourney(journeyIn, origins), journeyOut: journeyOut.length > 0,
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
      opacity: faded ? 0.5 : 1,
      ...containerStyle,
    }}>
      {rows.map((row, i) => {
        if ('slot' in row) {
          const body = row.slot === 'head' ? head
            : row.slot === 'tail' ? tail
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
              <Terminal which={n.kind} endStatus={endStatus} />
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
        // **Der geplante Rückweg** – nur im Entwurf. Die Ziele sind die Schalter, die
        // Linie darüber die Antwort: sie ist da oder eben nicht.
        if (n.kind === 'back') {
          return (
            <FlowNode key={row.key} id={id} style={place(i, { width: '100%' })}>
              <ReturnSwitch links={back} onToggle={onToggleReturn} />
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
              dimmed={running && !isActive}
              // **Eingeklappt, ausser das Modul ist dran** (Testnotiz #696) – eine Regel,
              // eine Stelle. Im Entwurf ist «dran» das zuletzt angelegte Modul.
              defaultOpen={step.id === expandedStepId}
              tone={tone?.(step.moduleType)}
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
 * **Der geplante Rückweg — die Linie IST die Entscheidung** (Auftrag §5).
 *
 * Vorher zwei Knöpfe («kehrt zurück» / «bleibt hier») neben der Stückauswahl. Die
 * Aussage stand damit an einer anderen Stelle als ihre Wirkung, und man sah erst nach
 * der Freigabe, was daraus wird. Jetzt steht sie dort, wo sie passiert: unter dem Ende,
 * am Ende der Linie – und die Linie darüber gibt es nur, wenn zurückgeführt wird.
 *
 * **Kein dritter Linientyp.** Die zwei Stärken bleiben, was sie sind; ob es zurückgeht,
 * sagt die Anwesenheit der Linie – exakt wie im laufenden Bild, wo eine gekappte
 * Ausleihe schlicht keinen Rückweg hat.
 *
 * **Der Knoten bleibt, wenn die Linie geht.** Sonst gäbe es nichts mehr anzuklicken, um
 * sie zurückzuholen – und die Entscheidung wäre einmalig statt änderbar. Er ist zugleich
 * das Ziel für die Bedienung: volle Zeilenbreite, 44 px hoch, also auch auf einem
 * Telefon zu treffen.
 */
function ReturnSwitch({ links, onToggle }: {
  links: ReturnLink[]; onToggle?: (key: number) => void;
}) {
  return (
    <div className="w-full flex flex-wrap items-center justify-center gap-1.5">
      {links.map((link) => (
        <button
          key={link.key}
          type="button"
          disabled={!onToggle}
          onClick={() => onToggle?.(link.key)}
          className="inline-flex items-center gap-1.5 rounded-ds-lg text-xs"
          style={{
            minHeight: 40, padding: '8px 12px',
            border: `1px solid ${link.on ? 'var(--border-2)' : 'var(--border-1)'}`,
            background: link.on ? 'var(--bg-2)' : 'transparent',
            color: link.on ? 'var(--fg-2)' : 'var(--fg-4)',
            cursor: onToggle ? 'pointer' : 'default',
          }}
          data-tip={link.on
            ? 'Nach dem Durchlauf geht jedes Stück an genau die Stelle zurück, an der es '
              + 'ausgeschert ist. Der andere Auftrag wartet solange. — Klicken kappt die '
              + 'Rückführung.'
            : 'Die Stücke bleiben hier (z. B. Aussonderung). Der andere Auftrag läuft mit '
              + 'weniger Stücken weiter. — Klicken führt sie wieder zurück.'}
        >
          <CornerUpLeft size={13} style={{ opacity: link.on ? 1 : 0.4 }} />
          <span className="ix-tnum">
            {link.orders.map((o) => formatObjectId(o)).join(' · ')}
          </span>
          <span style={{ color: 'var(--fg-4)' }}>{link.on ? 'zurück' : 'bleibt hier'}</span>
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
 * Server hat es aus dem Log abgeleitet. Die frühere Zählung «bis zum wievielten Knoten»
 * war genau die Ableitung, die aus dem *aktuellen* Zustand kam – und darum verschwand,
 * sobald an einer Stelle nichts mehr stand.
 */
export function Axis({ edges, anchors, prefix = '', journeyIn = [], journeyOut = [] }: {
  edges: GraphEdge[]; anchors: Record<string, FlowAnchor>; prefix?: string;
  /** Die Äste des Herkunfts-/Verbleibsbaums – Schlüssel, keine Geometrie. */
  journeyIn?: Array<string | number>;
  journeyOut?: Array<string | number>;
}) {
  return (
    <>
      {fanPaths(anchors, prefix, 'in', journeyIn).map((d, i) => (
        // **Gegangen**: die Stücke sind von dort gekommen bzw. dorthin gegangen. Ein
        // Ast, der nicht passiert ist, existiert nicht – die Journey kennt nur, was im
        // Log steht.
        <Stroke key={`fan-in-${i}`} d={d} walked />
      ))}
      {fanPaths(anchors, prefix, 'out', journeyOut).map((d, i) => (
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
  return (
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
      {rest > 0 && (
        <span className="inline-flex items-center gap-1 text-[11px] px-2 py-1"
          style={{ color: 'var(--fg-4)', whiteSpace: 'nowrap' }}
          data-tip="Weitere Nachbarn – sie stehen im jeweiligen Auftrag">
          <MoreHorizontal size={12} /> {rest}
        </span>
      )}
    </div>
  );
}

function Terminal({ which, endStatus }: { which: 'start' | 'end'; endStatus: string }) {
  const Icon = which === 'start' ? Play : Flag;
  const after = which === 'start' ? START_AFTER : endStatus;
  const before = which === 'start' ? START_BEFORE : END_BEFORE;
  const cfg = statusCfg(after);
  return (
    <div
      className="flex items-center justify-center rounded-full"
      style={{ width: 46, height: 46, border: `2px solid ${cfg.color}`, background: cfg.bg, color: cfg.color }}
      data-tip={`${which === 'start' ? 'Start' : 'Ende'}: ${statusLabel(before)} → ${statusLabel(after)}`}
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
  const away = outward ? units : [];
  const total = groups.reduce((n, g) => n + g.count, 0);
  const gone = away.reduce((n, g) => n + g.count, 0);
  async function toggle() {
    if (!onExpand) return;
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (numbers === null) {
      setBusy(true);
      try { setNumbers(await onExpand(edgeId)); } finally { setBusy(false); }
    }
  }

  if (!total && !gone) return null;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="flex flex-wrap gap-1.5 justify-center">
        {gone > 0 && (
          // **Ausgeschert.** Das Stück steht hier – es arbeitet nur gerade woanders.
          // Es fehlt nicht, und es ist nicht fertig; beides zu behaupten wäre falsch.
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--warning-bg)', color: 'var(--warning)',
                     border: '1px dashed var(--warning)' }}
            data-tip="In einem Abweichungsauftrag – es steht weiterhin an dieser Stelle"
          >
            <GitBranch size={11} /> In Abweichung · {gone}
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
              <span style={{ width: 6, height: 6, borderRadius: 999, background: cfg.color }} />
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
              data-tip={u.startedAt ? `Start passiert: ${localDateTime(u.startedAt)}` : undefined}>
              <UnitNumber value={u.number} size={11} />
              {onDeviate && (
                // **Der Auslöser sitzt am Stück, an seiner Stelle im Prozess** (§3.1).
                // Er legt nichts an – er öffnet einen gewöhnlichen Auftragsentwurf, in
                // dem dieses Stück schon steht.
                <button
                  type="button"
                  onClick={() => onDeviate(u.number)}
                  disabled={!!deviateBlocked}
                  className="flex items-center disabled:opacity-40"
                  style={{ color: 'var(--warning)' }}
                  aria-label={`Abweichung für ${u.number}`}
                  data-tip={deviateBlocked ?? 'Abweichung: Auftrag auf genau dieses Stück'}
                >
                  <GitBranch size={11} />
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

/**
 * **Ein Prozessobjekt = eine Komponente.** Der Modultyp ist Konfiguration (Name,
 * Übergang, Farbe) — es gibt hier bewusst keinen Zweig je Modulart und wird auch keinen
 * geben. Die Farbe kommt aus `lib/modules.moduleTone`, gefüttert vom Backend: ein neuer
 * Modultyp ist ein Eintrag in der Registry, kein Eingriff hier.
 *
 * Prozessmodule tragen eine **eigene Farbfamilie**, getrennt von der Ampel (§5.3): sie
 * sind keine Zustände und dürfen nicht wie welche aussehen.
 */

interface DragProps {
  index: number;
  over: boolean;
  onStart: () => void;
  onEnd: () => void;
  onDrop: (from: number) => void;
}

function StepCard({ step, active, dimmed, defaultOpen, onDelete, tone, drag, children }: {
  step: DiagramStep; active: boolean; dimmed: boolean;
  /** Startet dieses Modul aufgeklappt? Sonst zu – und der Kopf klappt es auf (#696). */
  defaultOpen?: boolean;
  onDelete?: () => void;
  tone?: { bg: string; fg: string; border: string };
  drag?: DragProps;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(!!defaultOpen);
  // **Die Sperre gehört hierher, nicht ins Modul** (Testnotiz #698). Ein Modul fragt
  // nicht, ob es darf – ihm wird gesagt, dass es nicht darf. `fieldset[disabled]` schaltet
  // JEDE Eingabe und JEDEN Knopf darin ab, ganz gleich, was das Modul rendert; ein
  // künftiger Einkauf oder Verkauf erbt das, ohne eine Zeile dafür zu schreiben. Der
  // Inhalt bleibt sichtbar – man will ja sehen, was drinsteht.
  const waiting = step.waitingFor ?? [];
  const locked = waiting.length > 0;
  // **Der Übergang steht nicht mehr auf der Karte.** Er gehört zum Modultyp und ist für
  // jedes Modul derselbe (Durchläufer) – ihn hinzuschreiben wäre eine Zeile, die bei
  // jeder Karte dasselbe sagt. Was die Karten unterscheidet, ist ihre **Art**, und die
  // trägt das Symbol.
  const Icon = MODULE_ICON[step.moduleType] ?? Blocks;
  const c = tone ?? moduleTone(undefined);
  return (
    <div
      className="rounded-ds-lg"
      // **Gezogen wird am Griff, nicht an der Karte.** Ein `draggable` auf der Karte
      // macht ihren ganzen Inhalt zum Ziehgriff – und damit lässt sich in ihren
      // Eingabefeldern kein Text mehr markieren. Das fällt bei einem Modul kaum auf und
      // bei zwanzig sofort.
      onDragEnd={drag ? drag.onEnd : undefined}
      onDragOver={drag ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } : undefined}
      onDrop={drag ? (e) => {
        e.preventDefault();
        const from = Number(e.dataTransfer.getData('text/plain'));
        if (Number.isInteger(from)) drag.onDrop(from);
      } : undefined}
      style={{
        border: `1px solid ${active ? c.fg : c.border}`,
        background: c.bg,
        opacity: dimmed ? 0.55 : 1,
        padding: '11px 14px',
        // Die Zielkarte zeigt sich beim Ziehen – ohne das rät man, wo es landet.
        outline: drag?.over ? `2px dashed ${c.fg}` : undefined,
        outlineOffset: 2,
      }}
    >
      {/* **Der Kopf klappt auf** (#696) – eine Stelle, jedes Modul. Ohne Inhalt gibt es
          nichts aufzuklappen, dann ist er auch kein Knopf. */}
      <div
        className="flex items-center gap-2.5"
        role={children ? 'button' : undefined}
        tabIndex={children ? 0 : undefined}
        aria-expanded={children ? open : undefined}
        style={{ cursor: children ? 'pointer' : undefined }}
        onClick={children ? () => setOpen(!open) : undefined}
        onKeyDown={children ? (e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(!open); }
        } : undefined}
      >
        {drag && (
          <span className="flex items-center justify-center flex-none"
            style={{ width: 16, color: c.fg, opacity: 0.5, cursor: 'grab' }}
            draggable
            onClick={(e) => e.stopPropagation()}
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = 'move';
              e.dataTransfer.setData('text/plain', String(drag.index));
              drag.onStart();
            }}
            onDragEnd={drag.onEnd}
            role="button"
            aria-label={`${step.label} verschieben`}
            data-tip="Ziehen, um die Reihenfolge zu ändern">
            <GripVertical size={15} />
          </span>
        )}
        <span
          className="flex items-center justify-center rounded-md flex-none"
          style={{ width: 32, height: 32, background: 'var(--bg-1)', color: c.fg }}
        >
          <Icon size={17} />
        </span>
        <span className="text-sm font-semibold flex-1 min-w-0 truncate" style={{ color: c.fg }}>
          {step.label}
        </span>
        {locked && (
          <Lock size={13} className="flex-none" style={{ color: 'var(--warning)' }}
            data-tip={lockReason(waiting)} />
        )}
        {children && (open
          ? <ChevronUp size={14} className="flex-none" style={{ color: c.fg, opacity: 0.55 }} />
          : <ChevronDown size={14} className="flex-none" style={{ color: c.fg, opacity: 0.55 }} />)}
        {onDelete && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="flex items-center justify-center rounded"
            style={{ width: 26, height: 26, color: 'var(--danger)' }}
            data-tip="Modul entfernen. Ändern geht nicht – eine gesetzte Definition rastet ein."
            aria-label={`${step.label} entfernen`}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
      {children && open && (
        <div className="mt-2.5 pt-2.5" style={{ borderTop: '1px solid var(--border-1)' }}>
          <fieldset disabled={locked}
            style={{ border: 0, padding: 0, margin: 0, minWidth: 0,
                     opacity: locked ? 0.65 : 1 }}>
            {children}
          </fieldset>
        </div>
      )}
    </div>
  );
}

function lockReason(waiting: number[]): string {
  return `Wartet auf die Rückführung aus ${waiting.length === 1 ? 'Auftrag' : 'den Aufträgen'} `
    + waiting.map(formatObjectId).join(', ');
}

