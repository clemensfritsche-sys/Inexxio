import { chainProblems } from '@/lib/modules';
import { statusLabel } from '@/lib/process-status';
import { whenTitle } from '@/lib/when';
import type { GraphEdge, GraphNode, JourneyStop, ProcessEventResponse, ProcessGraph } from '@/types';

/**
 * ►►► **Das Prozessbild als reine Funktionen** – Graph eines Entwurfs, Zeilenfolge einer
 * Spalte, Historie am Prozessobjekt, Herkunft/Verbleib. Ohne React, darum allein prüfbar
 * (`scripts/process-graph.test.mjs`); gezeichnet wird in `components/erp/flow-column.tsx`. ◄◄◄
 */

export interface DiagramStep {
  /**
   * **Die Identität des Moduls** – serverseitig vergeben und unveränderlich; im Entwurf eine
   * lokale Nummer. Der Ereignis-Log zeigt auf sie, nie auf Name oder Position.
   */
  id: number;
  moduleType: string;
  /** Wie das Modul heisst – aus seinem Typ abgeleitet, nicht eingegeben. */
  label: string;
  /** **Die Farbfamilie – am Schritt**, damit sie nirgends weitergegeben werden muss. */
  tone: string | null;
  /**
   * **Ist dies ein Ausgang?** Dann steht dahinter nichts mehr – kein Modul, kein Ende-Objekt
   * (`Module.terminal`).
   */
  terminal: boolean;
  /**
   * **Muss die Instanz vor der Eingabe gescannt werden?** Ohne physischen Bezug (Geldvorgang)
   * zeigt die Ausführung nur eine Bestätigung (`Module.requires_verification`). Optional: der
   * Editor rendert nie eine Ausführung.
   */
  verifies?: boolean;
  /** **Bewegt dieses Modul die Stücke?** Daraus folgt der Ziel-Scan. */
  moves?: boolean;
  /**
   * **Worauf dieses Modul wartet** – Objektnummern der Abweichungen, deren Rückführung aussteht.
   * Nicht leer heisst gesperrt: gerendert in `StepCard`, durchgesetzt in `process.confirm_step`.
   */
  waitingFor?: number[];
  /**
   * **Kann man an diesem Modul noch etwas tun?** Dann wird es nicht gedämpft, auch wenn es nicht
   * dran ist (`voucher.can`). Optional wie `moves`.
   */
  openActions?: boolean;
  /**
   * **Hat dieses Modul mehr zu berichten als die blosse Passage?** Abgeleitet am Schritt
   * (`ProcessStepResponse.records`), nie aus dem Modultyp.
   */
  records?: boolean;
}

export type DiagramMode = 'definition' | 'ausfuehrung';

/**
 * **Der Graph eines Entwurfs.** Ein Entwurf lebt im Browser (§6.1); sein Graph ist keine
 * zweite Ableitung, sondern die Definition selbst: Start → Module → Ende.
 */
/** Ein Bild, das der Server (noch) nicht geliefert hat. Leer, nicht erfunden. */
export const EMPTY_GRAPH: ProcessGraph = { nodes: [], edges: [], problems: [] };

export function definitionGraph(steps: DiagramStep[]): ProcessGraph {
  // Ein terminales Modul beendet die Kette (`domain/chain.assert_closes`, `services/flow.build`):
  // dahinter gibt es kein Ende-Objekt und damit auch keine Modul-Palette.
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
    // Was daran nicht aufgeht, sagt `lib/modules.chainProblems`.
    problems: chainProblems(steps),
  };
}

/**
 * **Eine Zeile im Bild** – ein Prozessobjekt, die Beschriftung einer Kante oder eine Zutat
 * (Definitionsbereich, Modulauswahl, Journey). Eine Position ist immer eine Kante: die Pille
 * steht auf der Linie. Eine Liste, ein Index – für die Spalte wie für das Raster.
 */
export type ColumnRow =
  | { key: string; slot: 'head' | 'tail' | 'loop' | 'journey-in' | 'journey-out' | 'return' }
  | { key: string; node: GraphNode }
  | { key: string; edge: GraphEdge };

/**
 * Der Graph als Zeilenfolge — reines Layout: Knoten in der Reihenfolge des Servers, dazwischen
 * die Beschriftung ihrer Kante.
 */
export function columnRows(g: ProcessGraph, extra: {
  head?: boolean; tail?: boolean; journeyIn?: boolean; journeyOut?: boolean;
  /** **Die Wiederholung** – direkt unter dem Ende: dort setzt ihre Linie an (Wiederkehr §8). */
  loop?: boolean;
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
    if (extra.loop && n.kind === 'end') rows.push({ key: 'loop', slot: 'loop' });
    // Was hinausgegangen ist, steht am Abzweigepunkt – dort sind die Stücke weg.
    (g.edges ?? [])
      .filter((e) => e.kind === 'out' && e.frm === n.id && (e.units ?? []).length)
      .forEach((e) => rows.push({ key: `on:${e.id}`, edge: e }));
    const e = outgoing.get(n.id);
    if (e && (e.units ?? []).length) rows.push({ key: `on:${e.id}`, edge: e });
  });
  if (extra.journeyOut) rows.push({ key: 'journey-out', slot: 'journey-out' });
  // Ganz unten: dort dockt die Rückführungslinie an (§8.1a″), der Schalter sitzt auf ihr.
  if (extra.returns) rows.push({ key: 'return', slot: 'return' });
  return rows;
}

/**
 * **Die Historie steht am Prozessobjekt, nicht in einer Box darunter** (Auftrag §5). Der
 * Schlüssel ist das Prozessobjekt, nicht das Modul – ``start`` und ``end`` tragen
 * ``step_id = null``. Liefert der Server nur die letzten N von M, sagt es die letzte Zeile.
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
    whenTitle(e.created_at),
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
 * **Woher die Stücke eines Erzeugungsauftrags kamen**: sie entstehen bei der Freigabe – die
 * einzige Herkunft, die nicht im Log steht.
 */
export interface JourneyOrigin {
  label: string;
  count: number;
}

/** Wie viele Nachbarn eine Journey-Zeile **vollständig** zeigt (wie `RELATED_LIMIT`). */
export const JOURNEY_LIMIT = 3;

export const journeyId = (where: 'in' | 'out', key: string | number) => `j:${where}:${key}`;

/** Die Schlüssel der Äste einer Journey-Zeile — dieselbe Liste, die sie rendert. */
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
 * Die Achsenkanten – alles, was innerhalb einer Spalte zu zeichnen ist, auch die Kante hinter
 * dem Ende (``to = null``): ihr Ziel ist die Zeile, auf der ihre Stücke stehen.
 */
export function axisEdges(g: ProcessGraph): GraphEdge[] {
  return (g.edges ?? []).filter((e) => e.kind === 'axis');
}
