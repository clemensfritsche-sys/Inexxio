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
   * Optional wie `moves`: der **Editor** baut seine Schritte aus dem Modul-Katalog und
   * rendert nie eine Ausführung – dort gibt es die Frage nicht.
   */
  verifies?: boolean;
  /** **Bewegt dieses Modul die Stücke?** Daraus folgt der Ziel-Scan. */
  moves?: boolean;
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
   * **Kann man an diesem Modul noch etwas tun?** (#821) – dann wird es nicht gedämpft,
   * auch wenn es nicht dran ist (eine Rechnung lässt sich nach dem Durchlauf noch buchen).
   * Der Schritt sagt es, abgeleitet aus derselben Tabelle, die auch das Tor ist
   * (`voucher.can`). Optional wie `moves`: der Editor rendert nie eine Ausführung.
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

export const journeyId = (where: 'in' | 'out', key: string | number) => `j:${where}:${key}`;

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
