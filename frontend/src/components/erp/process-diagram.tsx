'use client';

import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import {
  ChevronDown, ChevronUp, CornerUpLeft, Flag, GitBranch, GripVertical, Lock,
  MoreHorizontal, Play, Scissors, Sprout, Trash2, type LucideIcon,
} from 'lucide-react';
import { moduleIcon, chainProblems, moduleTone } from '@/lib/modules';
import { TYPE_META } from '@/lib/erp-record';
import {
  BEND, FLOW_GAP, FlowNode, LANE, POINT, polyPath, port, type FlowAnchor,
} from './process-flow';
import { UnitNumber } from './unit-number';
import {
  statusCfg, isPickable, IM_PROZESS, START_AFTER, START_BEFORE, END_BEFORE, statusLabel,
} from '@/lib/process-status';
import { formatObjectId, localDateTime } from '@/lib/utils';
import { useErpNav } from './obj-id';
import type {
  GraphEdge, GraphNode, GraphUnits, JourneyStop, ProcessEventResponse, ProcessGraph,
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
   * **Die Farbfamilie – am Schritt, nicht als Prop des Rahmens.**
   *
   * Sie kam einmal über einen Rückruf von aussen (`ColumnProps.tone`), gefüttert aus dem
   * Modul-Katalog. Den lädt aber nur der Editor: der **freigegebene** Auftrag reichte
   * ihn nicht durch, und ein stiller Rückfall gab jedem Modul die Farbe der
   * Datenerfassung – die Aussonderung wechselte beim Freigeben ihr Aussehen. Als Feld
   * des Schritts kann sie nicht mehr fehlen, weil sie niemand mehr weitergeben muss.
   */
  tone: string | null;
  /**
   * **Ist dies ein Ausgang?** Dann steht dahinter nichts mehr: kein weiteres Modul (der
   * Editor bietet keines an, die Freigabe weist es ab) und kein Ende-Objekt (das Stück
   * kommt dort nie an). Eine Eigenschaft des Modultyps – siehe `Module.terminal`.
   */
  terminal: boolean;
  /**
   * **Muss die Instanz vor der Eingabe gescannt werden?**
   *
   * Ein Scan beantwortet «habe ich das richtige physische Ding vor mir». Ein Modul ohne
   * physischen Bezug (ein Geldvorgang stellt etwas in Rechnung) tut mit dem Stück gar
   * nichts – dort wäre er eine Geste ohne Aussage, und die Ausführungsstelle zeigt
   * schlicht eine Bestätigung. Eine Eigenschaft des Modultyps
   * (`Module.requires_verification`), die mit dem Schritt reist wie Farbe und Ausgang.
   *
   * Optional wie `moves` und `buys`: der **Editor** baut seine Schritte aus dem
   * Modul-Katalog und rendert nie eine Ausführung – dort gibt es die Frage nicht.
   */
  verifies?: boolean;
  /**
   * **Bewegt dieses Modul die Stücke?** Daraus folgt der Ziel-Scan.
   *
   * Vorher beantwortete das die Transportart-Liste, indem sie bei jedem anderen Modultyp
   * leer war – eine Liste als Bit. Seit «selbst oder eingekauft» aus dem Beleg folgt,
   * gibt es die Liste nicht mehr, und die Frage steht als das da, was sie ist.
   */
  moves?: boolean;
  /**
   * **Trägt dieses Modul einen Einkaufs-Beleg – und wann?** `null` = nie.
   *
   * `'if_chosen'` heisst: die Arbeit kann auch selbst erledigt werden, und genau darum
   * darf die Ausführungsstelle hier die Wahl anbieten. Sie fragt damit nach der
   * Eigenschaft und nie nach dem Modultyp.
   */
  buys?: string | null;
  /**
   * **Worauf dieses Modul wartet** (Testnotiz #698) – Objektnummern der Abweichungen,
   * deren Rückführung aussteht. Nicht leer heisst: gesperrt.
   *
   * Das Modul fragt **nicht selbst**, ob es darf; ihm wird gesagt, dass es nicht darf.
   * Die Sperre wird an einer Stelle gerendert (`StepCard`) und serverseitig durchgesetzt
   * (`process.confirm_step`) – ein künftiges Modul erbt beides, ohne eine Zeile dafür.
   */
  waitingFor?: number[];
  /**
   * ►►► **Kann man an diesem Modul noch etwas tun?** (Testnotiz #821) ◄◄◄
   *
   * Ein Modul, das nicht dran ist, wird gedämpft – und das war genau dann falsch, wenn
   * der Auftrag längst durch ist und trotzdem noch eine Rechnung oder eine Zahlung zu
   * buchen ist. Die Karte sagte optisch «hier ist nichts mehr zu tun», während ihre
   * Knöpfe funktionierten: dieselbe Fehlerform wie eine erfundene Sperre, nur in Farbe.
   *
   * **Der Schritt sagt es, nicht die Oberfläche** – abgeleitet aus derselben Tabelle,
   * die auch das Tor ist (`purchase.can` / `deal.can`). Eine Heuristik hier wäre eine
   * dritte Wahrheit. Optional wie `moves` und `buys`: der Editor rendert nie eine
   * Ausführung.
   */
  openActions?: boolean;
  /**
   * **Hat dieses Modul mehr zu berichten als die blosse Passage?** (Testnotiz #825)
   *
   * Das Protokoll bleibt für jedes Modul der Nachweis – aber wo nichts erfasst, nichts
   * verifiziert und kein Zustand geändert wird, blieben eine Nummer, ein Name und eine
   * Uhrzeit übrig. Abgeleitet am Schritt (`ProcessStepResponse.records`), nie aus dem
   * Modultyp.
   */
  records?: boolean;
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
/**
 * **Wie ein Entwurf im Bild heisst.** Er hat keine Objektnummer (§6.1) und braucht doch
 * eine Adresse: die Vorschau des Quell-Auftrags nennt ihn als Ziel ihrer Abzweigung
 * (`order:<n>`), und ohne einen gemeinsamen Wert fände die Linie ihr Ende nicht.
 *
 * Gespiegelt von `backend/app/schemas/order.DRAFT_OBJECT_ID` – der Server schreibt sie
 * in die Vorschau, diese Seite liest sie; `tests/test_frontend_mirrors.py` hält beide
 * zusammen. Null ist keine gültige Objektnummer (der Kreis beginnt bei 100'000'001),
 * kann also mit keinem echten Auftrag kollidieren.
 */
export const DRAFT_OBJECT_ID = 0;

/** Ein Bild, das der Server (noch) nicht geliefert hat. Leer, nicht erfunden. */
export const EMPTY_GRAPH: ProcessGraph = { nodes: [], edges: [], problems: [] };

export function definitionGraph(steps: DiagramStep[]): ProcessGraph {
  // **Ein terminales Modul beendet die Kette** – dieselbe Regel wie serverseitig
  // (`domain/chain.assert_closes`, `services/flow.build`): was dort ankommt, verlässt den
  // Auftrag, also gibt es dahinter kein Ende-Objekt. Und weil die Modul-Palette *vor* dem
  // Ende steht, ist sie damit ebenfalls weg – ohne eine zweite Bedingung dafür.
  const exit = steps.findIndex((s) => s.terminal);
  const chain: GraphNode[] = [
    { id: 'start', kind: 'start', at: null },
    ...steps.map((s) => ({ id: `module:${s.id}`, kind: 'module', at: s.id })),
    ...(exit === -1 ? [{ id: 'end', kind: 'end', at: null }] : []),
  ];
  return {
    nodes: chain,
    edges: chain.slice(0, -1).map((n, i) => ({
      id: `edge:${n.id}:${chain[i + 1].id}`,
      frm: n.id, to: chain[i + 1].id, kind: 'axis', walked: false, units: [],
    })),
    // Was daran nicht aufgeht, sagt die Regel selbst (`lib/modules.chainProblems`) – das
    // Bild rendert nur, was es bekommt.
    problems: chainProblems(steps),
  };
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
  | { key: string; slot: 'head' | 'tail' | 'journey-in' | 'journey-out' | 'return' }
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
  /** Der Rückführungs-Schalter des Entwurfs – **die letzte Zeile**, siehe `ReturnRow`. */
  returns?: boolean;
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
  // **Ganz unten**, denn genau dort beginnt die Rückführungslinie: sie dockt an der
  // letzten Zeile dieser Spalte an (§8.1a″). Der Schalter sitzt damit **auf** ihr.
  if (extra.returns) rows.push({ key: 'return', slot: 'return' });
  return rows;
}

/**
 * **Die Historie steht am Prozessobjekt, nicht in einer Box darunter** (Auftrag §5).
 *
 * Der Ereignis-Log ist die Wahrheit über das Vergangene (§10.3) und bleibt vollständig
 * erhalten – aufgezeichnet wird unverändert. Nur **wo** man ihn liest, ändert sich: eine
 * Liste am Fuss des Auftrags zwingt dazu, jede Zeile erst dem Objekt zuzuordnen, an dem
 * sie passiert ist. Am Objekt selbst ist diese Zuordnung die Position.
 *
 * **Ein Muster für alle**, und zwar für *alle drei* Objektarten – nicht nur für Module:
 * ``start`` und ``end`` tragen ``step_id = null``, ihre Einträge (die Hälfte des Logs)
 * wären an einem reinen Modul-Hover **unerreichbar**. Der Schlüssel ist darum nicht «das
 * Modul», sondern «dieses Prozessobjekt».
 *
 * Gekappt wird nicht verschwiegen: liefert der Server nur die letzten N von M Einträgen,
 * sagt es die letzte Zeile.
 */
export function historyTip(events: ProcessEventResponse[], node: GraphNode,
                           total?: number): string | undefined {
  const mine = events.filter((e) => (
    node.kind === 'module' ? e.step_id === node.at
      : node.kind === 'start' ? e.kind === 'start'
        : node.kind === 'end' ? e.kind === 'end' : false
  ));
  if (!mine.length) return undefined;
  const lines = mine.map((e) => [
    e.unit_number,
    `${statusLabel(e.status_before)} → ${statusLabel(e.status_after)}`,
    localDateTime(e.created_at),
    e.actor,
  ].filter(Boolean).join(' · '));
  // Der Log ist append-only – eine Korrektur wäre ein neuer Eintrag, kein geänderter.
  if (total != null && total > events.length) {
    lines.push(`… gezeigt sind die letzten ${events.length} von ${total} Einträgen`);
  }
  return lines.join('\n');
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
export interface ReturnTarget {
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

/**
 * **Ein Prozessobjekt = eine Komponente.** Der Modultyp ist Konfiguration (Name,
 * Übergang, Farbe) — es gibt hier bewusst keinen Zweig je Modulart und wird auch keinen
 * geben. Die Farbe kommt aus `lib/modules.moduleTone`, gefüttert vom Backend: ein neuer
 * Modultyp ist ein Eintrag in der Registry, kein Eingriff hier.
 *
 * Prozessmodule tragen eine **eigene Farbfamilie**, getrennt von der Ampel (§5.4): sie
 * sind keine Zustände und dürfen nicht wie welche aussehen.
 */

interface DragProps {
  index: number;
  over: boolean;
  onStart: () => void;
  onEnd: () => void;
  onDrop: (from: number) => void;
}

/**
 * **Das Zeichen eines Moduls** – getöntes Quadrat mit seinem Symbol.
 *
 * Es steht hier als eigenes Bauteil, weil es zwei Träger hat: die **Modul-Karte** und der
 * **Einkaufs-Vorgang**, der in einem Modul stattfinden kann (`ProcurementHead`). Ein
 * Einkauf sieht überall gleich aus; nachgebaut wäre er beim ersten Massänderung ein
 * zweiter Massstab.
 *
 * **Die Historie hängt am Symbol** (§5) – wie bei Start und Ende, die dieselbe Blase auf
 * ihrem Kreis tragen. Sie hing einmal an der Beschriftung, und die trägt `truncate`
 * (`overflow: hidden`): das **schneidet die Blase weg**, denn sie ist ein `::after` dieses
 * Elements.
 */
export function ModuleMark({ icon: Icon, tone, size = 32 }: {
  icon: LucideIcon; tone: string; size?: number;
}) {
  return (
    <span
      className="flex items-center justify-center rounded-md flex-none"
      style={{ width: size, height: size, background: 'var(--bg-1)', color: tone }}
    >
      <Icon size={Math.round(size * 0.53)} />
    </span>
  );
}

/**
 * ►►► **Die Hülle einer Modul-Karte — EIN Bauteil, zwei Träger.** ◄◄◄
 *
 * Rahmen in der Modulfarbe, getönte Fläche, `rounded-ds-lg`, Kopf mit `ModuleMark` und
 * Beschriftung, Haarlinie vor dem Körper. Genau das ist die Anatomie, an der man eine
 * Modul-Karte erkennt – und sie steht **einmal**.
 *
 * Getragen wird sie von `StepCard` (dem Modul selbst) und vom `ProcurementBlock` (dem
 * Einkaufs-Beleg **in** einem Modul, Testnotiz #783): «container im container, und der
 * innere ist ein 1:1 Abbild eines regulären Moduls – ist ja auch nichts anderes».
 *
 * Ein Nachbau daneben sähe heute gleich aus und wiche beim ersten Karten-Detail ab; ein
 * Wächter verbietet darum jeden eigenen Rahmen im Beleg-Block.
 *
 * `lead` und `trail` sind die Stellen, an denen ein Träger Eigenes einhängt (Ziehgriff,
 * Schloss, Chevron, Löschen) – der Rahmen selbst kennt davon nichts.
 */
export function ModuleShell({ tone, icon, label, active, lead, trail, head, body,
  history, children }: {
  tone: { fg: string; bg: string; border: string };
  icon: LucideIcon;
  label: string;
  /** Ist dieses Modul an der Reihe? Dann trägt der Rahmen die kräftige Farbe. */
  active?: boolean;
  lead?: ReactNode;
  trail?: ReactNode;
  /** Zusätzliche Eigenschaften am Kopf-Element – z. B. Aufklappen. */
  head?: React.HTMLAttributes<HTMLDivElement>;
  /** Zusätzliche Eigenschaften am äusseren Rahmen – z. B. Ziehen. */
  body?: React.HTMLAttributes<HTMLDivElement>;
  /**
   * ►►► **Die Historie hängt an der KOPFZEILE, nicht am Symbol** (Testnotiz #790). ◄◄◄
   *
   * Sie hing am 32-px-Quadrat links – man musste sie also treffen, um zu erfahren, was
   * an diesem Modul passiert ist. Gemeldet wurde genau das: «die Hover-Historie sollte
   * für den ganzen Prozessschritt-Container gelten».
   *
   * Die Kopfzeile ist dieser Container: sie läuft über die ganze Kartenbreite, und
   * zugeklappt – der Normalfall – **ist** sie die Karte. Die Blase steht damit auch
   * dort, wo man hinsieht: mittig über der Karte statt über einem Symbol am Rand.
   *
   * **Nicht am äusseren Rahmen**, obwohl der wörtlich «der ganze Container» wäre: darin
   * steht der aufgeklappte Feldsatz, und eine Historien-Blase, die beim Tippen in einem
   * Eingabefeld aufgeht, ist keine Auskunft, sondern Störung.
   *
   * Was **darin** eine eigene Blase trägt (Ziehgriff, Schloss, Löschen), gewinnt
   * weiterhin – die Regel dafür steht in `globals.css` (`:has`), nicht hier.
   *
   * Und sie darf **nie an der Beschriftung** hängen: die trägt `truncate`
   * (`overflow: hidden`), und das **schneidet die Blase weg** – sie ist ein `::after`.
   */
  history?: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-ds-lg" {...body}
      style={{
        border: `1px solid ${active ? tone.fg : tone.border}`,
        background: tone.bg,
        padding: '11px 14px',
        ...(body?.style ?? {}),
      }}>
      <div className="flex items-center gap-2.5"
        // Fokussierbar, damit die Blase auch **ohne Hover** erscheint – auf dem
        // Touchgerät per Tipp, an der Tastatur per Tab. Wo der Kopf ohnehin aufklappt,
        // ist er längst fokussierbar; `head` steht darum danach und gewinnt.
        tabIndex={history ? 0 : undefined}
        {...(history ? { 'data-tip': history, 'data-tip-list': '' } : {})}
        {...head}>
        {lead}
        <ModuleMark icon={icon} tone={tone.fg} />
        <span className="text-sm font-semibold flex-1 min-w-0 truncate"
          style={{ color: tone.fg }}>{label}</span>
        {trail}
      </div>
      {children && (
        <div className="mt-2.5 pt-2.5" style={{ borderTop: '1px solid var(--border-1)' }}>
          {children}
        </div>
      )}
    </div>
  );
}


export function StepCard({ step, active, dimmed, defaultOpen, onDelete, drag, history,
  children }: {
  step: DiagramStep; active: boolean; dimmed: boolean;
  /** Was an diesem Modul passiert ist – der Ereignis-Log, an seinem Ort (§5). */
  history?: string;
  /** Startet dieses Modul aufgeklappt? Sonst zu – und der Kopf klappt es auf (#696). */
  defaultOpen?: boolean;
  onDelete?: () => void;
  drag?: DragProps;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(!!defaultOpen);

  // ►► **Wird ein Modul zum aktiven, klappt es auf** (Testnotiz #727). ◄◄
  //
  // `defaultOpen` war ein reiner **Startwert**: wer den Auftrag öffnete, bevor die Stücke
  // ankamen, bekam `false` – und dabei blieb es. Als das Modul dann an der Reihe war,
  // blieb es zu, ohne blockiert zu sein. Genau so wurde es gemeldet.
  //
  // Der Effekt hängt an `defaultOpen` und **nur** daran: er läuft, wenn das aktive Modul
  // wechselt, nicht bei jedem Rendern. Wer selbst zuklappt, bleibt darum zugeklappt –
  // eine Entscheidung des Menschen wird nicht bei der nächsten Antwort überschrieben.
  useEffect(() => { setOpen(!!defaultOpen); }, [defaultOpen]);
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
  const Icon = moduleIcon(step.moduleType);
  // **Die Farbe kommt vom Schritt, nicht von einem Aufrufer.** Wer sie nicht kennt, malt
  // nicht irgendetwas: `moduleTone` meldet eine unbekannte Familie sichtbar (Warnfarbe),
  // statt sie stillschweigend zur Datenerfassung zu machen.
  const c = moduleTone(step.tone);
  return (
    // **Die Hülle ist geteilt** (`ModuleShell`) – dasselbe Bauteil trägt den Einkaufs-
    // Beleg *in* einem Modul (#783). Was hier dazukommt, hängt in `lead`/`trail`: der
    // Ziehgriff, das Schloss, der Chevron, das Löschen. Der Rahmen kennt davon nichts.
    <ModuleShell
      tone={c} icon={Icon} label={step.label} active={active}
      body={{
        // **Gezogen wird am Griff, nicht an der Karte.** Ein `draggable` auf der Karte
        // macht ihren ganzen Inhalt zum Ziehgriff – und damit lässt sich in ihren
        // Eingabefeldern kein Text mehr markieren. Das fällt bei einem Modul kaum auf
        // und bei zwanzig sofort.
        onDragEnd: drag ? drag.onEnd : undefined,
        onDragOver: drag
          ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
          : undefined,
        onDrop: drag ? (e) => {
          e.preventDefault();
          const from = Number(e.dataTransfer.getData('text/plain'));
          if (Number.isInteger(from)) drag.onDrop(from);
        } : undefined,
        style: {
          opacity: dimmed ? 0.55 : 1,
          // Die Zielkarte zeigt sich beim Ziehen – ohne das rät man, wo es landet.
          outline: drag?.over ? `2px dashed ${c.fg}` : undefined,
          outlineOffset: 2,
        },
      }}
      // **Der Kopf klappt auf** (#696) – eine Stelle, jedes Modul. Ohne Inhalt gibt es
      // nichts aufzuklappen, dann ist er auch kein Knopf.
      head={{
        role: children ? 'button' : undefined,
        tabIndex: children ? 0 : undefined,
        'aria-expanded': children ? open : undefined,
        style: { cursor: children ? 'pointer' : undefined },
        onClick: children ? () => setOpen(!open) : undefined,
        onKeyDown: children ? (e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(!open); }
        } : undefined,
      }}
      lead={drag ? (
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
      ) : undefined}
      trail={(
        <>
          {locked && (
            <Lock size={13} className="flex-none" style={{ color: 'var(--warning)' }}
              data-tip={lockReason(waiting)} />
          )}
          {children && (open
            ? <ChevronUp size={14} className="flex-none"
                style={{ color: c.fg, opacity: 0.55 }} />
            : <ChevronDown size={14} className="flex-none"
                style={{ color: c.fg, opacity: 0.55 }} />)}
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
        </>
      )}
      history={history}
    >
      {children && open && (
        // **Die Sperre gehört hierher, nicht ins Modul** (#698). Ein Modul fragt nicht,
        // ob es darf – ihm wird gesagt, dass es nicht darf. `fieldset[disabled]` schaltet
        // JEDE Eingabe und JEDEN Knopf darin ab, ganz gleich, was das Modul rendert.
        <fieldset disabled={locked}
          style={{ border: 0, padding: 0, margin: 0, minWidth: 0,
                   opacity: locked ? 0.65 : 1 }}>
          {children}
        </fieldset>
      )}
    </ModuleShell>
  );
}

function lockReason(waiting: number[]): string {
  return `Wartet auf die Rückführung aus ${waiting.length === 1 ? 'Auftrag' : 'den Aufträgen'} `
    + waiting.map(formatObjectId).join(', ');
}

