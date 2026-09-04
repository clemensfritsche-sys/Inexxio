/**
 * Prozessschrittmodule und Erfassungspunkt-Typen — **Symbole und Farben**, sonst nichts.
 *
 * Die Listen selbst stehen im Backend (`domain/modules.py`, `domain/capture_types/`) und
 * kommen über `GET /erp/orders/module-catalog`. Hier liegt nur, was eine Antwort nicht
 * transportieren kann: das Icon und die konkreten Farbwerte. **Welche** Farbfamilie ein
 * Modultyp trägt, sagt das Backend (`tone`) – ein neuer Modultyp ist damit ein Eintrag in
 * der Registry und kein Eingriff in die Oberfläche.
 *
 * `backend/tests/test_frontend_mirrors.py` prüft, dass Symbole und Farbfamilien **genau**
 * die Schlüssel des Backends abdecken: ein Typ ohne Symbol wäre eine leere Fläche, ein
 * Symbol ohne Typ eine tote Zeile.
 */

import {
  Blocks, Camera, CircleHelp, ClipboardCheck,
  HandCoins, Handshake, MoveRight, PackageX, PenLine, Ruler, ShoppingCart,
  ThumbsUp, Type, type LucideIcon,
} from 'lucide-react';

import { emptyLine, type DefinitionLine } from '@/components/erp/definition-lines';

/** Erfassungspunkt-Typen (`domain/capture_types/`). */
export const CAPTURE_ICON: Record<string, LucideIcon> = {
  text: Type,
  bool: ThumbsUp,
  photo: Camera,
  signature: PenLine,
  measure: Ruler,
};

/** Prozessschrittmodule (`domain/modules.py`). */
export const MODULE_ICON: Record<string, LucideIcon> = {
  datenerfassung: ClipboardCheck,
  aussondern: PackageX,
  verbrauch: Blocks,
  // Von hier nach dort – bewusst **kein** Transportmittel (kein Lastwagen, kein
  // Gabelstapler): womit bewegt wird, entscheidet sich erst bei der Ausführung.
  bewegen: MoveRight,
  // **Geld wechselt die Hand** – in beide Richtungen dasselbe Symbol, denn es ist
  // dasselbe Modul. Welche Richtung gilt, sagt das Zeichen **im** Vorgang
  // (`DEAL_DIRECTION`), nicht die Kachel: eine Palette mit zwei fast gleichen Symbolen
  // wäre wieder die Trennung, die dieses Modul gerade aufhebt.
  zahlung: HandCoins,
};

/**
 * ►►► **Die beiden Richtungen eines Geldvorgangs — Symbol und Satz.** ◄◄◄
 *
 * Alles Übrige zur Richtung (Wörter, Stufen, Verben) **reist mit dem Vorgang**
 * (`DealEmbed`); hier steht nur, was eine Antwort nicht transportieren kann. Gespiegelt
 * von `backend/app/domain/deal.py`, deckungsgleich gehalten von `test_frontend_mirrors`.
 *
 * **Keine zwei Farben**: die Richtung ist eine Aussage über den Fluss, kein Zustand –
 * und Farbe ist im ERP für die Ampel reserviert.
 *
 * ►►► **«Einnahme» ↔ «Ausgabe», nicht «Verkauf» ↔ «Einkauf»** (Testnotiz #831). ◄◄◄
 *
 * Dieses Modul entstand aus der Einsicht, dass der kleinste gemeinsame Nenner **nicht die
 * Ware** ist, sondern Geld mit einer zweiten Partei. Miete, Lohn, Gebühr, Spesen und ein
 * Transport sind keine Käufe – ein Wert, der «Verkauf» heisst, ist damit **enger als das
 * Modul**, und beim ersten Mietvertrag ist er schlicht falsch. *Meine frühere Wahl (#804,
 * «die Werte heissen wie beim Handel») wird damit zurückgenommen: sie stimmte für die
 * beiden Fälle, die zufällig zuerst gebaut wurden.*
 *
 * ►►► **Die Wörter bleiben — die SYMBOLE kommen vom Handel** (Testnotiz #845). ◄◄◄
 *
 * Zwei diagonal entgegengesetzte Pfeile standen hier, und die Begründung war «ein Pfeil
 * sagt, wohin das Geld fliesst, und mehr behauptet dieses Modul nicht». Am Bildschirm
 * gemessen war das zu wenig: zwei Pfeile derselben Familie, gespiegelt, sind auf 15 px
 * das **gleiche** Zeichen mit anderer Neigung – man muss hinsehen, statt zu erkennen.
 * Einkaufswagen und Handschlag sind **verschiedene Dinge**, und das Haus schreibt damit
 * längst dieselbe Unterscheidung: eine Bildsprache statt zweier. *Sie standen einmal in
 * einer eigenen Zuordnung (`FLOW`, gespiegelt vom Handels-Beleg); mit den Modulen
 * «Beschaffen»/«Verkauf» ist sie entfallen, und die beiden Symbole stehen jetzt dort, wo
 * sie gebraucht werden – eine Zuordnung mit einem Leser ist keine.*
 *
 * **Das Wort trägt die Weite, das Symbol die Wiedererkennung.** Der Einwand aus #831
 * bleibt gültig und bleibt beantwortet – er galt den **Werten** («Verkauf» ist enger als
 * ein Modul, das auch Miete und Lohn kann), und die heissen unverändert «Einnahme» ↔
 * «Ausgabe». Ein Symbol behauptet keinen Namen; es zeigt die häufigste Gestalt der
 * Sache, und Geld kommt herein, weil man etwas verkauft.
 */
export const DEAL_DIRECTION: Record<string, {
  icon: LucideIcon; label: string; hint: string;
}> = {
  in: {
    // Der Handschlag – Geld kommt herein, weil eine Zusage nach aussen erfüllt wird.
    icon: Handshake, label: 'Einnahme',
    hint: 'Einnahme – wir stellen Rechnung, Geld kommt herein.',
  },
  out: {
    // Der Einkaufswagen – Geld geht hinaus, weil wir etwas beziehen.
    icon: ShoppingCart, label: 'Ausgabe',
    hint: 'Ausgabe – wir bekommen Rechnung, Geld geht hinaus.',
  },
};

/**
 * ►►► **Was in BEIDEN Richtungen gleich heisst.** ◄◄◄
 *
 * «Kunde» ↔ «Lieferant» standen einmal je Richtung da, und jede Aufrufstelle musste sich
 * das richtige Wort holen. Es ist aber **dieselbe Rolle**: der andere im Geschäft. Ein
 * Wort dafür nimmt eine ganze Fehlerklasse weg – die falsche Wahl gibt es dann nicht mehr.
 *
 * **Singular = Plural.** Damit ist das «Kundeen»-Problem (#787) *strukturell* erledigt
 * statt durch einen zweiten gepflegten Wert. Gespiegelt von `domain/deal`.
 */
export const DEAL_PARTY = 'Partner';

/*
 * ►►► **Der Steuersatz und sein Name stehen hier NICHT mehr** (Testnotiz #851). ◄◄◄
 *
 * `DEFAULT_VAT` war die Vorgabe eines Modul-Feldes, `VAT_LABEL` seine Beschriftung – und
 * das Feld ist entfallen: der Satz hängt an der **Sache**, nicht am Modul. Gefragt wird
 * er je Position an der Ausführungsstelle, und dorthin reisen Katalog, Vorgabe und Wort
 * mit dem Vorgang (`DealEmbed.vat_rates` / `.vat_rate` / `.vat_label`).
 *
 * Ein Spiegel ohne Leser ist kein Spiegel, sondern eine zweite Wahrheit, die niemand
 * vergleicht.
 */

/**
 * **Was bei einem Partner zu tun ist** – seine Artikelnummer, sein Shop-Link oder ein Satz.
 *
 * Eine Eigenschaft der **Paarung** Modul × Partner, in beiden Richtungen und **Pflicht**.
 * Der frühere freiwillige Satz am Vorgang war ihre optionale Doppelung (#805) – und ein
 * Feld, das man ausfüllen *kann*, wird an der Hälfte der Stellen leer gelassen.
 */
export const DEAL_TASK = 'Was ist zu tun?';
export const DEAL_TASK_HINT = 'Artikelnummer, Link oder Beschreibung';

/** Die Richtung zu einem Schlüssel. Unbekannt → Ausgabe, wie im Backend (`deal.of`). */
export function dealDirection(direction: string | undefined | null) {
  return DEAL_DIRECTION[direction ?? ''] ?? DEAL_DIRECTION.out;
}

/**
 * **Die Stufen eines Geldvorgangs — als Schlüssel, nicht als Wort.**
 *
 * Wie sie *heissen*, sagt der Server (`DealEmbed.stages[].label`) – das hängt an der
 * Richtung. Was die Oberfläche braucht, ist die **Identität**: an welcher Stufe die
 * Zusage steht und an welcher der Scan. `test_frontend_mirrors` hält sie mit
 * `domain/deal.STAGES` deckungsgleich; deutsche Wörter im Rumpf wären an einem Vorgang
 * der anderen Richtung still falsch.
 */
export const DEAL_STAGE = {
  offer: 'offer',
  agreed: 'agreed',
  /** **Ausgänge, keine Stufen** – man kommt dort an, statt hindurchzugehen. */
  done: 'done',
  cancelled: 'cancelled',
} as const;

/**
 * ►►► **Die Zustände einer Angebotszeile.** ◄◄◄
 *
 * `gewaehlt` entsteht nicht durch Tippen, sondern dadurch, dass bei dieser Zeile zugesagt
 * wurde – ein Zustand ist eine Folge. Gespiegelt von `domain/deal.QUOTE_STATES`.
 */
export const QUOTE_STATE = {
  asked: 'angefragt',
  quoted: 'offeriert',
  declined: 'abgelehnt',
  chosen: 'gewaehlt',
} as const;

/**
 * **Die Farbfamilien der Module — die eine Stelle.**
 *
 * Bewusst **getrennt von der Ampel** (grün = Anfang/Ende · orange = im Prozess ·
 * rot = Problem): ein Modul ist kein Zustand und darf nicht wie einer aussehen
 * (PROCESS_CORE.md §5.3). Darum kühle und warme Neutraltöne statt Signalfarben.
 *
 * Kein Farbwert steht in einer Komponente – wer eine Modulfarbe braucht, fragt hier.
 */
export const MODULE_TONE: Record<string, { bg: string; fg: string; border: string }> = {
  slate: { bg: 'var(--accent-soft)', fg: 'var(--accent-ink)', border: '#BFD6E2' },
  sand: { bg: '#F4EBDD', fg: '#9A7238', border: '#E4D2B8' },
  moss: { bg: '#E9EFE6', fg: '#5A7048', border: '#CBD9C2' },
  clay: { bg: '#F3E7E4', fg: '#8C5A50', border: '#E2CBC5' },
  // Beschaffen: gedämpftes Violett. Die vier älteren Familien waren vergeben, und ein
  // Modul, das sich eine teilt, ist im Fluss von seinem Nachbarn nicht zu unterscheiden.
  // **Gemessen, nicht geraten**: der erste Anlauf (kühles Graublau) stand neben der
  // Datenerfassung und war von ihr nicht zu trennen; Blaugrün rückt nur näher an
  // Bewegen, und ein warmes Grau liest sich neben vier farbigen Karten wie deaktiviert.
  // Slate=Blau · Clay=Rotbraun · Moss=Grün · Sand=Gelbbraun – Violett schliesst den Kreis.
  plum: { bg: '#EFEAF2', fg: '#6B5A78', border: '#DCD2E2' },
  // Verkauf: gedämpftes Blaugrün. Es ist die **Nachbarfamilie von Plum** über die kalte
  // Seite – und das ist Absicht: Ein- und Verkauf sind derselbe Vorgang in zwei
  // Richtungen, also sollen sie verwandt aussehen und trotzdem unterscheidbar sein.
  // Beim Beschaffen war Blaugrün einmal verworfen, weil es an **Moss** (Bewegen)
  // heranrückte; hier trägt es, weil der Ton deutlich kühler und dunkler sitzt als das
  // grünliche Moss – und weil die beiden Handelsmodule ohnehin selten nebeneinander in
  // einer Kette stehen, Moss dagegen oft neben beiden.
  teal: { bg: '#E4EEEE', fg: '#4A6E70', border: '#C8DCDC' },
  // Zahlung: gedämpftes Altrosa. Die sechs übrigen Familien sind vergeben (Slate=Blau ·
  // Sand=Gelbbraun · Moss=Grün · Clay=Rotbraun · Plum=Violett · Teal=Blaugrün), und ein
  // Modul, das sich eine teilt, ist im Fluss von seinem Nachbarn nicht zu unterscheiden.
  // Magenta/Rosa ist die einzige unbesetzte Familie – und sie sitzt deutlich pinker als
  // das orange-braune Clay, mit dem sie sich sonst die Helligkeit teilte.
  rose: { bg: '#F7E9EE', fg: '#8A4F66', border: '#EBD3DC' },
};

/**
 * **Eine unbekannte Farbfamilie ist ein Fehler und sieht auch so aus.**
 *
 * Hier stand ein stiller Rückfall auf `slate` – und `slate` ist die Farbe der
 * Datenerfassung. Wo die Farbe nicht ankam (im freigegebenen Auftrag: sie wurde aus dem
 * Modul-Katalog geholt, und den lädt nur der Editor), trug **jedes** Modul plötzlich die
 * Farbe eines echten anderen Moduls. Der Fehler war damit nicht zu sehen, sondern zu
 * verwechseln – die schlimmste Form.
 *
 * Die Ursache ist strukturell behoben: die Farbe reist als Feld mit dem Schritt
 * (`ModuleFacts.tone`), ein Aufrufer kann sie nicht mehr vergessen. Bleibt der Fall, dass
 * ein **neueres Backend** eine Familie nennt, die diese Oberfläche nicht kennt – und der
 * gehört gemeldet, nicht überspielt.
 */
/**
 * **Das Symbol eines Moduls — und was ein unbekanntes zeigt.**
 *
 * Dieselbe Regel wie bei `moduleTone`: Unbekanntes sieht **unbekannt** aus. Es borgt
 * nicht das Symbol eines anderen Moduls – vorher gab es drei Rückfälle, und jeder log
 * etwas anderes: `Blocks` ist der **Verbrauch**, `PackageX` das **Aussondern**, und
 * `CAPTURE_ICON.text` ist der Erfassungspunkt «Text» – ein schlichtes **T**, das
 * gemeldete Symbol. Ein Modul, dessen Typ die Oberfläche nicht kennt (alter Browser-
 * Stand nach einem Deploy), gab sich damit als ein anderes aus.
 */
export function moduleIcon(type: string | undefined | null): LucideIcon {
  return MODULE_ICON[type ?? ''] ?? CircleHelp;
}

export function moduleTone(tone: string | undefined | null): { bg: string; fg: string; border: string } {
  return MODULE_TONE[tone ?? ''] ?? UNKNOWN_TONE;
}

/** Sichtbar kaputt: keine Modulfarbe, sondern die Warnfarbe des Hauses. */
const UNKNOWN_TONE = { bg: 'var(--danger-bg)', fg: 'var(--danger)', border: 'var(--danger)' };

/** Typen, die in der Definition einen **Sollwert** brauchen (`Measure.clean`). */
/**
 * **Der Schlüssel des Bewegen-Moduls.** Er steht hier, weil Modul-Wissen hier wohnt –
 * eine Oberfläche, die ihn selbst hinschreibt, kennt einen Modultyp, den sie nicht
 * kennen müsste. Gebraucht wird er an genau einer Stelle: ein «Holen lassen» **baut**
 * ein Bewegen-Modul, es fragt nicht danach.
 */
export const MOVE_MODULE = 'bewegen';

export const NEEDS_TARGET = 'measure';

/**
 * **Hinter einem Ausgang kann kein Modul mehr stehen.**
 *
 * Dieselbe Regel wie serverseitig (`domain/chain.assert_closes`), nur früher: dort weist
 * sie die Freigabe ab, hier sagt sie es, während man modelliert. Sie steht **hier** und
 * nicht im Diagramm, weil sie eine Aussage über Modultypen ist – das Bild rendert nur,
 * was es bekommt.
 *
 * Der Normalfall braucht sie gar nicht: die Palette verschwindet hinter einem terminalen
 * Modul, es lässt sich also keines dahinter setzen. Übrig bleibt das **Umsortieren** –
 * ein Modul, das hinter den Ausgang gezogen wurde. Es bleibt sichtbar (sonst liesse es
 * sich nicht mehr löschen), aber das Bild sagt, dass so nichts läuft.
 */
export function chainProblems(steps: { label: string; terminal: boolean }[]): string[] {
  const exit = steps.findIndex((s) => s.terminal);
  if (exit < 0 || exit === steps.length - 1) return [];
  return [`Hinter «${steps[exit].label}» kann kein Modul mehr stehen: was hier ankommt, `
    + `verlässt den Auftrag – Schritt ${exit + 2} bekäme nie ein Stück.`];
}

/**
 * **Die Stichprobe ist EINE Zahl: der Anteil an allem, was am Modul wartet.**
 *
 * Nicht je Instanz – ein Modul sieht die Summe der Einzelinstanzen vor sich, und «10 %
 * von drei Chargen» hiesse sonst dreimal eine eigene Ziehung, deren keine mit der Zahl
 * auf dem Bildschirm übereinstimmt (`domain/sampling.py`).
 *
 * Die Kurzwege sind darum **keine eigenen Modi**, sondern Werte derselben Zahl: alle =
 * 100 %, Hälfte = 50 %, Viertel = 25 %. Frei getippt wird nur, wer etwas anderes will.
 *
 * `value` ist bewusst ein **String**: es ist ein Eingabefeld, und ein halb getipptes Feld
 * hat keine Zahl. Geprüft wird sie serverseitig (`sampling.clean`), die Antwort kommt als
 * Satz durch `validate` zurück – hier steht keine zweite Regel.
 */
export interface SampleDraft {
  /** Der gewählte Kurzweg – oder `free`, dann zählt `value`. */
  mode: SampleMode;
  value: string;
}

export type SampleMode = 'all' | 'half' | 'quarter' | 'free';

/** Kurzweg → Anteil. Die eine Zuordnung; `free` hat keinen festen Wert. */
export const SAMPLE_PRESETS: { value: SampleMode; label: string; percent?: number }[] = [
  { value: 'all', label: 'Alle', percent: 100 },
  { value: 'half', label: 'Hälfte', percent: 50 },
  { value: 'quarter', label: 'Viertel', percent: 25 },
  { value: 'free', label: 'Anteil' },
];

/** Was ohne Angabe gilt – **alle**, wie im Backend (`sampling.DEFAULT`). */
export const SAMPLE_ALL: SampleDraft = { mode: 'all', value: '' };

/**
 * Entwurfsform → das eine Feld, das der Server kennt. Ein frei getippter Anteil geht
 * **unverändert** hinaus, auch halb getippt: ihn hier in etwas umzudeuten wäre eine
 * stille Änderung der Konfiguration – der Server sagt stattdessen, dass die Zahl fehlt.
 */
export function samplePayload(s: SampleDraft): { percent: string | number } {
  const preset = SAMPLE_PRESETS.find((p) => p.value === s.mode)?.percent;
  return { percent: preset ?? s.value };
}

/**
 * Ein Erfassungspunkt im Entwurf. `key` fehlt: er wird serverseitig aus der Bezeichnung
 * abgeleitet — ihn hier zu vergeben hiesse, zwei Stellen für dieselbe Regel zu haben.
 *
 * Ein `required` gibt es **nicht**: alles, was angelegt ist, ist Pflicht.
 */
export interface PointDraft {
  label: string;
  type: string;
  target?: string;
  tolerance?: string;
  /**
   * **Worin gemessen wird** – nur beim Soll-Ist-Vergleich (mm · kg · °C …).
   *
   * Ein freies, kurzes Wort. Bewusst **keine Liste**: die Mengeneinheiten des Artikels
   * (`Stk · mm · m2 · m3 · kg · l`) beantworten eine andere Frage – worin die **Menge**
   * geführt wird – und kennen weder °C noch bar noch Nm; sie hier wiederzuverwenden
   * hiesse, genau die Einheit nicht anbieten zu können, die der Anlass war. Eine zweite
   * Liste wäre endlos, und das System rechnet nie mit der Einheit: es zeigt sie an.
   */
  unit?: string;
}

/**
 * Ein Modul im Entwurf — dieselbe Form am Artikel wie im Auftrag.
 *
 * **Keinen Namen** (Testnotiz #682): wie ein Modul heisst, sagt sein Typ. Ein Feld
 * daneben hatte genau eine richtige Antwort und war trotzdem Pflicht – und war damit
 * die Quelle der Meldung «String should have at least 1 character» (#686).
 *
 * Die **Identität** vergibt der Server beim Anlegen (#687); `id` hier ist nur eine
 * lokale Nummer, denn den Datensatz gibt es noch nicht.
 */
export interface ModuleDraft {
  id: number;
  moduleType: string;
  points: PointDraft[];
  /** **Wie viele der wartenden Stücke erfasst werden** – je Instanz. Pflichtfeld der
   *  Entwurfsform, damit jede Anlagestelle sie aussprechen muss; ihr Vorgabewert ist
   *  `SAMPLE_ALL`, nicht ein stillschweigend fehlendes Feld. */
  sample: SampleDraft;
  /** Nur «Aussondern»: verschrotten (endgültig) oder sperren (aufhebbar). */
  mode: DisposalMode;
  /**
   * Nur «Aussondern»: **warum** hier ausgesondert wird. Pflicht – aber beim
   * **Modellieren**, nicht am Band: der Anlass gehört zum Ablauf und lautet bei jedem
   * Stück gleich. Ohne ihn ist das Modul nicht anlegbar (`Aussondern.clean_config`).
   */
  reason: string;
  /**
   * Nur «Verbrauch»: die **Stückliste** – je Zeile Artikel und Menge **pro Einzelinstanz**.
   *
   * Artikel und nicht Definitionszeilen – dasselbe Modul wird auch in der
   * **Artikel-Vorlage** definiert (der Erzeugungsprozess IST der Montageplan), und dort
   * gibt es noch gar keine Zeilen. Eine Vorlage kann «4× Schraube M6» meinen, aber nicht
   * «Zeile 2».
   *
   * Es ist **dieselbe Zeile** wie im Bedarf eines Auftrags (`DefinitionLine`), nur mit
   * zwei Fragen weniger: die Herkunft entfällt (eine Stückliste erzeugt nichts) und die
   * konkreten Stücke ebenso – die wählt der Lagerist beim Ausführen, wo es eine echte
   * Wahl ist.
   */
  lines: DefinitionLine[];
  /**
   * Nur «Bewegen»: **wohin** die Stücke gebracht werden – die Objektnummer eines Halters
   * (Regal, Behälter, Person, Unternehmen).
   *
   * **Optional, und das ist eine Aussage**: leer heisst «wird beim Ausführen gewählt»,
   * nicht «vergessen». Beim Modellieren steht oft noch nicht fest, wo Platz sein wird –
   * eine Vorlage, die das behauptet, ist beim zweiten Durchlauf falsch. Damit die beiden
   * Fälle unterscheidbar bleiben, sagt die Karte im Fluss ausdrücklich, welcher gilt.
   *
   * Ein **String**, weil es ein Eingabefeld ist: ein halb getipptes Feld hat keine Zahl.
   */
  target: string;
  /**
   * Nur «Zahlung»: **kommt Geld herein oder geht es hinaus?** (`in` ↔ `out`).
   *
   * Das eine Feld, aus dem jedes Wort dieses Moduls folgt – wie die Stufen heissen, wie
   * die Gegenpartei heisst, wer die Rechnung stellt. Es steht in der Konfiguration und
   * nicht als zweiter Modul-Schlüssel: es ist EIN Modul, und die Richtung ist seine
   * Einstellung. Zwei Kacheln in der Palette wären wieder die Trennung, die dieses Modul
   * gerade aufhebt.
   */
  direction: string;
  /**
   * Nur «Zahlung»: die **zugelassenen Gegenparteien** – je Zeile Nummer und
   * **Bestellangabe** (seine Artikelnummer, sein Shop-Link).
   *
   * **Leer heisst frei**, nicht «niemand»: dann wird beim Ausführen gesucht.
   *
   * Die Bestellangabe gehört der **Paarung** Modul × Gegenpartei – derselbe Lieferant
   * führt je Teil eine andere Nummer –, und es gibt sie nur, wo **wir** bestellen
   * (`DEAL_DIRECTION[…].ref`; beim Verkauf liefern wir).
   */
  parties: { party: number; ref: string }[];
  /**
   * Nur «Zahlung»: **erst weiter, wenn bezahlt.** Der einzige Schalter dieses Moduls –
   * und er schreibt keine Reihenfolge vor, er hält nur an.
   */
  prepaid: boolean;
}

/**
 * **Die Ausprägungen des Aussonderns.** Zwei Fälle, ein Modul – sie tun dasselbe, nur
 * der Zielzustand unterscheidet sie. Welcher das ist, sagt das Backend
 * (`Aussondern.MODES`); hier stehen nur Wort und Erklärung.
 */
export type DisposalMode = 'scrap' | 'block';

export const DISPOSAL_MODES: { value: DisposalMode; label: string; hint: string }[] = [
  { value: 'scrap', label: 'Verschrotten', hint: 'Physisch entsorgt – endgültig, kein Weg zurück' },
  { value: 'block', label: 'Sperren', hint: 'Bleibt vorhanden, ist aber nicht mehr einplanbar' },
];

/**
 * **Was ein Modultyp im Entwurf ausmacht — je Typ ein Eintrag, nicht je Stelle ein `if`.**
 *
 * Eine Frage hängt am Typ und sonst an nichts: *was schickt er als Konfiguration*.
 * Verteilt über `toModulePayload` und den Editor wären es Ketten, die beim dritten
 * Modultyp auseinanderlaufen.
 *
 * **«Wann ist er vollständig» steht hier NICHT** (Aufräumrunde August 2026). Es stand
 * einmal daneben (`incomplete` je Typ + `moduleIncomplete`) und hatte **keinen einzigen
 * Aufrufer** – die freundliche Hälfte lief längst über den Server: beide Entwürfe fragen
 * `POST …/validate`, und dessen `missing` steht im Hinweis des Freigabe-Knopfes.
 * Gemessen, nicht vermutet: der Server antwortet dort «Lieferant 100000001 braucht eine
 * Bestellangabe – seine Artikelnummer oder den Link…», wo hier «Bestellangabe fehlt»
 * stand. Die zweite Fassung war also nicht nur doppelt, sondern **schlechter** – und
 * beim nächsten Feld wäre sie die mildere von zweien gewesen.
 *
 * Es ist bewusst **kein** Spiegel des Backends: die Regel gilt dort (`Module.clean_config`),
 * hier steht nur die Form der Eingabe. `test_frontend_mirrors` hält die Schlüssel deckungsgleich.
 */
export const MODULE_FORM: Record<string, {
  config: (m: ModuleDraft) => Record<string, unknown>;
  /**
   * **Die Umkehrform — gespeicherte Konfiguration → Entwurf** (Testnotiz #771).
   *
   * Sie steht **neben** ihrem Gegenstück und trägt denselben Namensstamm: zwei Formen
   * einer Regel sind in Ordnung, zwei Regeln nicht. Gebraucht wird sie, damit ein
   * **freigegebener** Prozess dieselben Felder zeigt wie ein Entwurf – nur gesperrt.
   * Vorher rendete der Editor dort **gar nichts**: wer ein Modul anklickte, sah, dass es
   * aufklappt, und darin war nichts. Ein zweiter, nur-lesender Feldsatz wäre die
   * Alternative gewesen – und die (n+1)-te Angabe hätte darin gefehlt.
   */
  draft: (config: Record<string, unknown>) => Partial<ModuleDraft>;
}> = {
  datenerfassung: {
    draft: (c) => ({
      points: asRows(c.points).map((p) => ({
        label: String(p.label ?? ''),
        type: String(p.type ?? 'text'),
        target: p.target == null ? '' : String(p.target),
        tolerance: p.tolerance == null ? '' : String(p.tolerance),
        unit: p.unit == null ? '' : String(p.unit),
      })),
      sample: sampleDraft(c.sample),
    }),
    config: (m) => ({
      points: m.points.map((p) => ({
        label: p.label,
        type: p.type,
        target: p.type === NEEDS_TARGET && p.target !== '' ? Number(p.target) : null,
        tolerance: p.type === NEEDS_TARGET && p.tolerance !== '' ? Number(p.tolerance) : null,
        // Die Einheit gehört zum Sollwert – ohne ihn gäbe es nichts, worauf sie sich
        // bezieht (der Server verwirft sie bei jedem anderen Typ ohnehin).
        unit: p.type === NEEDS_TARGET ? (p.unit ?? '').trim() : null,
      })),
      sample: samplePayload(m.sample),
    }),
  },
  aussondern: {
    draft: (c) => ({
      mode: (c.mode === 'block' ? 'block' : 'scrap') as DisposalMode,
      reason: String(c.reason ?? ''),
    }),
    // Zwei Angaben, beide Pflicht: **was** passiert (verschrotten ↔ sperren) und
    // **warum**. Erfassungspunkte gibt es keine – was ankommt, wird ausgesondert, und
    // der Grund steht bereits hier statt bei jedem Stück noch einmal.
    config: (m) => ({ mode: m.mode, reason: m.reason }),
  },
  bewegen: {
    draft: (c) => ({ target: c.target == null ? '' : String(c.target) }),
    // **Eine Angabe, und die ist optional.** Leer geht als `null` hinaus – nicht als
    // fehlendes Feld: der Server unterscheidet «kein Ziel definiert» von «Feld nicht
    // geschickt» nicht, aber die Absicht ist hier eindeutig, und sie soll es bleiben.
    config: (m) => ({ target: m.target.trim() === '' ? null : Number(m.target) }),
  },
  zahlung: {
    draft: (c) => ({
      // Tolerant gelesen: eine fehlende Richtung ist eine **Ausgabe**, wie im Backend
      // (`deal.of`) – ein freigegebener Prozess ist eingefroren, und eine alte Zeile
      // darf keine Anzeige zerlegen. (Die Vorgabe eines **neuen** Moduls ist dagegen die
      // Einnahme, #791 – das ist eine andere Frage: was gilt, wenn nichts dasteht,
      // gegenüber was vorgeschlagen wird, bevor jemand wählt.)
      direction: c.direction === 'in' ? 'in' : 'out',
      // Tolerant gelesen wie im Backend (`modules.parties_of`): die alte Form war die
      // blosse Objektnummer, und ein freigegebener Prozess ist eingefroren – sie steht
      // also in laufenden Aufträgen und wird sie überleben.
      parties: asRows(c.parties).map((r) => ({
        party: Number(r.party ?? r), ref: String(r.ref ?? ''),
      })).filter((r) => Number.isFinite(r.party)),
      prepaid: Boolean(c.prepaid),
    }),
    // ►►► **Drei Angaben – und KEIN Steuersatz** (Testnotiz #851). ◄◄◄
    //
    // Er hing hier als Vorgabe und war damit eine Eigenschaft des **Moduls**: eine
    // Vorlage, die für jeden Auftrag denselben Satz behauptet. Er hängt aber an der
    // **Sache**, und die steht erst fest, wenn ein Auftrag läuft – dort wird er je
    // Position gefragt (`OurOffer`), und der Katalog reist mit dem Vorgang.
    // Keine Erfassungspunkte und keine Stichprobe: Geld ist keine Messung am Stück.
    config: (m) => ({
      direction: m.direction,
      parties: m.parties.map((r) => ({ party: r.party, ref: r.ref.trim() })),
      prepaid: m.prepaid,
    }),
  },
  verbrauch: {
    draft: (c) => ({
      lines: asRows(c.lines).map((r, i) => ({
        ...emptyLine(i + 1),
        articleObjectId: Number(r.article),
        quantity: Number(r.quantity ?? 1),
      })).filter((l) => Number.isFinite(l.articleObjectId as number)),
    }),
    // Zwei Angaben je Zeile, beide Pflicht: **welcher Artikel** und **wie viele je
    // Einzelinstanz**. Ohne Zeile wäre das Modul ein Durchgang, der aussieht wie eine
    // Montage; ohne Menge wäre «Schraube» keine Stückliste.
    config: (m) => ({
      lines: m.lines
        .filter((l) => l.articleObjectId !== null)
        .map((l) => ({ article: l.articleObjectId as number, quantity: l.quantity })),
    }),
  },
};

/** Eine gespeicherte Liste als Zeilen lesen – tolerant, denn sie kommt aus JSONB. */
function asRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.map((v) => (v && typeof v === 'object' ? v as Record<string, unknown> : { party: v }));
}

/**
 * **Der gespeicherte Anteil zurück in seine Eingabeform.** Die Kurzwege sind Werte
 * derselben Zahl (`SAMPLE_PRESETS`) – trifft die Zahl einen, steht der Regler dort;
 * sonst ist es ein frei getippter Anteil.
 */
function sampleDraft(value: unknown): SampleDraft {
  const percent = Number((value as { percent?: unknown } | null)?.percent ?? NaN);
  if (!Number.isFinite(percent)) return { ...SAMPLE_ALL };
  const preset = SAMPLE_PRESETS.find((p) => p.percent === percent);
  return preset ? { mode: preset.value, value: '' } : { mode: 'free', value: String(percent) };
}

/**
 * **Ein gespeichertes Modul als Entwurf** – dieselbe Form, aus der die Oberfläche auch
 * ein neues baut. Damit zeigt ein **freigegebener** Prozess seine Felder mit demselben
 * Bauteil wie ein Entwurf, nur gesperrt (Testnotiz #771): eine Ansicht, ein Feldsatz.
 *
 * Ein Typ, den diese Oberfläche nicht kennt, liefert den leeren Entwurf – die Karte sagt
 * dann, dass sie ihn nicht kennt, statt Felder zu erfinden.
 */
export function moduleFromConfig(id: number, moduleType: string,
                                 config: Record<string, unknown> | null | undefined): ModuleDraft {
  return { ...blankModule(id, moduleType),
           ...(MODULE_FORM[moduleType]?.draft(config ?? {}) ?? {}) };
}

/** Ein frischer Entwurf dieses Modultyps – mit den Vorgaben, die das Backend kennt. */
export function blankModule(id: number, moduleType: string): ModuleDraft {
  return {
    id, moduleType, points: [], sample: { ...SAMPLE_ALL }, mode: 'scrap', reason: '',
    lines: [], target: '',
    // **Die Vorgabe ist die EINNAHME** (#791): der häufigere Fall im Haus ist, dass wir
    // etwas verkaufen. Die Richtung bleibt trotzdem eine ausdrückliche Angabe – der
    // Server verlangt sie (`Zahlung.clean_config`), damit kein Wert stillschweigend gilt.
    direction: 'in', parties: [], prepaid: false,
  };
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). */
export function toModulePayload(m: ModuleDraft) {
  return { module_type: m.moduleType, config: MODULE_FORM[m.moduleType]?.config(m) ?? {} };
}
