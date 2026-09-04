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
  Banknote, Landmark,
  ArrowDownLeft, ArrowUpRight, Blocks, Camera, CircleHelp, ClipboardCheck, Hand,
  HandCoins, Handshake, MoveRight, PackageX, PenLine, Ruler, ShoppingCart, ThumbsUp,
  Type, type LucideIcon,
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

/**
 * ►►► **Die Handels-Vorgänge — Name, Farbe, Symbol, je Richtung.** ◄◄◄
 *
 * Ein Beleg gehört **keinem Modul** (`domain/procurement`): ein Einkauf sieht überall
 * gleich aus, ob ihn ein Beschaffen-Modul auslöst (dort ist er der Zweck) oder ein
 * Bewegen-Modul (dort war er eine Wahl). Darum steht die Identität hier und nicht als
 * Eintrag «des Moduls beschaffen» – die Karte des Moduls liest sie ebenso, und beide
 * können nicht auseinanderlaufen.
 *
 * **Und dieselbe Maschine trägt den Verkauf** – nur in die andere Richtung. Was sie
 * unterscheidet, sind Wörter, Farbe und Symbol; alles andere (Stufen, Verben, Zustände)
 * reist fertig mit dem Beleg (`PurchaseEmbed`), damit die Oberfläche für keine einzige
 * Zeile wissen muss, in welche Richtung sie gerade zeichnet.
 *
 * Gespiegelt von `backend/app/domain/procurement.py`; `test_frontend_mirrors` hält Wort
 * und Farbfamilie beider Richtungen deckungsgleich. Das **Symbol** kann eine Antwort
 * nicht transportieren – es steht wie bei den Modulen nur hier.
 */
export const FLOW: Record<string, { label: string; tone: string; icon: LucideIcon }> = {
  buy: {
    label: 'Beschaffen',
    tone: 'plum',
    // Ein Einkaufswagen – bewusst **kein** Lastwagen und kein Paket: der Vorgang kauft,
    // er liefert nicht. Womit die Ware kommt, entscheidet der Lieferant.
    icon: ShoppingCart,
  },
  sell: {
    label: 'Verkauf',
    tone: 'teal',
    // Ein Handschlag – **kein** Geldschein und kein Preisschild: was den Verkauf
    // ausmacht, ist die Zusage zwischen zwei Parteien, nicht der Betrag. (Ein zweiter
    // Einkaufswagen wäre ohnehin falsch herum.)
    icon: Handshake,
  },
};

/** Der Vorgang zu einer Richtung. Unbekannt → der Einkauf, wie im Backend (`of`). */
export function flowOf(direction: string | undefined | null) {
  return FLOW[direction ?? ''] ?? FLOW.buy;
}

/**
 * **Die Stufen eines Belegs — als Schlüssel, nicht als Wort.**
 *
 * Wie sie *heissen*, sagt der Server (`PurchaseEmbed.stages[].label`) – und das ist gut
 * so, denn es hängt an der Richtung. Was die Oberfläche trotzdem braucht, ist die
 * **Identität** einer Stufe: an welcher der Angebotsspiegel steht, an welcher der Scan.
 *
 * Sie stehen darum hier als Konstanten und nicht dreimal als Zeichenkette im Rumpf –
 * `test_frontend_mirrors` hält sie mit `domain/procurement.STAGES` deckungsgleich. Vorher
 * standen dort die deutschen Einkaufs-Wörter (`'anfrage'`, `'wareneingang'`), und ein
 * Verkaufs-Beleg hätte an **keiner** Stufe etwas gezeigt: die Vergleiche wären alle
 * falsch gewesen, still und ohne Fehlermeldung.
 */
/**
 * ►►► **Was ein MENSCH als Zahlweg eintragen darf** – der Spiegel von
 * `money.MANUAL_METHODS`. ◄◄◄
 *
 * Die Karte fehlt mit Absicht (#782): eine Kartenzahlung entsteht beim Zahlungsdienst und
 * kommt über den Webhook. Sie hier anzubieten wäre eine zweite Quelle für dieselbe
 * Buchung – die eine aus der Wirklichkeit, die andere aus einer Erinnerung. Durchgesetzt
 * wird es im **Dienst** (`purchase._pay`), nicht hier; diese Liste ist die freundliche
 * Hälfte. Ein Wächter hält sie mit `domain/money` deckungsgleich.
 */
export type Method = 'transfer' | 'cash';

export const MANUAL_METHODS: {
  value: Method; icon: LucideIcon; label: string; hint: string;
}[] = [
  { value: 'transfer', icon: Landmark, label: 'Überweisung',
    hint: 'Der B2B-Normalfall – vom Kontoauszug erfasst.' },
  { value: 'cash', icon: Banknote, label: 'Bar',
    hint: 'Bar oder am Schalter.' },
];

export const STAGE = {
  offer: 'offer',
  commitment: 'commitment',
  fulfilment: 'fulfilment',
  cancelled: 'cancelled',
} as const;

/** Prozessschrittmodule (`domain/modules.py`). */
export const MODULE_ICON: Record<string, LucideIcon> = {
  datenerfassung: ClipboardCheck,
  aussondern: PackageX,
  verbrauch: Blocks,
  // Von hier nach dort – bewusst **kein** Transportmittel (kein Lastwagen, kein
  // Gabelstapler): womit bewegt wird, entscheidet sich erst bei der Ausführung.
  bewegen: MoveRight,
  // **Aus derselben Quelle wie der Vorgang** – ein Handel sieht überall gleich aus, und
  // die beiden Module sind genau seine zwei Richtungen.
  beschaffen: FLOW.buy.icon,
  verkauf: FLOW.sell.icon,
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
 * **Und darum sind es Pfeile, kein Handschlag.** `FLOW` bleibt die Bildsprache des
 * *Handels* – Einkaufswagen ↔ Handschlag –, und genau das ist hier nicht gemeint. Ein
 * Pfeil sagt, wohin das Geld fliesst, und mehr behauptet dieses Modul nicht; zwei
 * diagonal entgegengesetzte sind auf 15 px sicher unterscheidbar (der Einwand aus #799
 * gegen Plus und Minus gilt für sie nicht).
 */
export const DEAL_DIRECTION: Record<string, {
  icon: LucideIcon; label: string; hint: string;
}> = {
  in: {
    // Ein Pfeil **herein** – Geld kommt zu uns.
    icon: ArrowDownLeft, label: 'Einnahme',
    hint: 'Einnahme – wir stellen Rechnung, Geld kommt herein.',
  },
  out: {
    // Ein Pfeil **hinaus** – Geld geht von uns weg.
    icon: ArrowUpRight, label: 'Ausgabe',
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
 * **Symbol je Transportart** (`Bewegen.TRANSPORTS`).
 *
 * Wie bei den Modulen steht die **Liste** im Backend – hier nur, was eine Antwort nicht
 * transportieren kann. Ein neuer Kanal ist damit ein Eintrag in der Registry plus ein
 * Symbol; `test_frontend_mirrors` hält beide Seiten deckungsgleich.
 */
/**
 * **Selbst gebracht ↔ eingekauft** – das eine Bit einer Bewegung.
 *
 * Die frühere Liste `manuell · paket · fracht` (mit einem `available`-Flag als Roadmap)
 * ist entfallen: *Paket* und *Fracht* sind keine zwei Arten, sondern zwei **Angebote**
 * desselben Einkaufs – das entscheidet der Tarif, nicht der Modellierer. Ein Roboter,
 * der es fährt, ist «selbst»: unser Gerät, keine Rechnung.
 *
 * Und die Antwort ist **abgeleitet**: eingekauft wurde genau dann, wenn es einen Beleg
 * gibt. Zwei Angaben könnten sich widersprechen, eine abgeleitete kann es nicht.
 */
export const HAULAGE = {
  self: { icon: Hand, label: 'Selbst',
          hint: 'Jemand von uns bringt es hin – kein Dienstleister, kein Beleg.' },
  // **Der Name ist der des Vorgangs, nicht einer des Transports** (#775): «Einkaufen»
  // war ein zweites Wort für dieselbe Sache, und im Haus heisst sie «Beschaffen». Symbol
  // und Wort kommen darum aus `FLOW.buy` – dieselbe Quelle, aus der auch die Karte des
  // Beschaffen-Moduls sie nimmt. Eine Spedition wird **gekauft**, nie verkauft; darum
  // steht hier die Richtung fest und nicht `flowOf(…)`.
  bought: { icon: FLOW.buy.icon, label: FLOW.buy.label,
            hint: 'Eine Spedition beauftragen – daraus wird ein ganz gewöhnlicher '
                + 'Beschaffungs-Vorgang: anfragen, vergleichen, bestellen.' },
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
   * Nur «Beschaffen»: die **zugelassenen Lieferanten**, mindestens einer – je Eintrag
   * seine Objektnummer und die **Bestellangabe**.
   *
   * Eine Liste, auch wenn fast immer einer drinsteht: **n statt 1**. Wer nur bei Würth
   * kauft, hat eine Liste mit Würth; wer vergleichen will, nennt drei – und der
   * Angebotsvergleich ist damit kein zweiter Mechanismus, sondern dieselbe Liste, eine
   * Zeile länger. Fachlich ist es die Lieferantenfreigabe.
   *
   * **`ref` ist «wie bestelle ich bei ihm»** – seine Artikelnummer oder der Shop-Link.
   * Sie gehört der **Paarung** Modul × Lieferant: bekannt, wenn man festlegt, wer in
   * Frage kommt, und unverändert über alle Bestellungen. Am Beleg wäre sie eine Angabe,
   * die man bei jedem Vorgang neu abschreibt.
   */
  suppliers: SupplierRule[];
  /**
   * Nur «Beschaffen»: **was der Lieferant tun soll** – ein Satz, Pflicht.
   *
   * *Was* beschafft wird, steht hier bewusst nicht: das sagen die Einzelinstanzen, die
   * vor dem Modul stehen (sie tragen ihren Artikel). Was fehlte, war der **Auftrag** –
   * die Spezifikation beschreibt die Sache, nicht was mit ihr geschehen soll («Härten
   * auf 58 HRC»). Er gehört an das Modul und nicht an den Artikel: ein Artikel hat
   * mehrere Schritte, und jeder verlangt etwas anderes.
   */
  instruction: string;
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

/** Ein zugelassener Lieferant und die Angabe, wie man bei ihm bestellt (#753). */
export interface SupplierRule {
  supplier: number;
  /** Seine Artikelnummer oder der Shop-Link – frei, weil es beides sein kann. */
  ref: string;
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
 * ►►► **Die beiden Beleg-Angaben — für jedes Modul, das handelt.** ◄◄◄
 *
 * Bei wem und was zu tun ist. Sie gehören dem **Beleg**, nicht einem Modultyp – also
 * steht der Eintrag einmal da und wird von beiden Richtungen referenziert. Zwei Kopien
 * wären am ersten Tag gleich und beim ersten neuen Feld nicht mehr.
 *
 * Kein Artikel – den sagen die Einzelinstanzen vor dem Modul; keine Menge – die steht
 * beim Modellieren nicht fest (dieselbe Regel wie beim Verbrauch); kein Modus «Webshop» –
 * wo jemand seinen Shop hat, ist eine Eigenschaft von **ihm** und nicht dieses Belegs.
 *
 * Ob die Angaben **Pflicht** sind, steht hier bewusst nicht: das sagt der Katalog des
 * Backends (`suppliers_required` / `instruction_required`), und die Freigabe ist die
 * eine Regel dazu.
 */
const TRADE_FORM = {
  draft: (c: Record<string, unknown>) => ({
    // Tolerant gelesen wie im Backend (`Module.parties_of`): die alte Form war die
    // blosse Objektnummer, und ein freigegebener Prozess ist eingefroren – sie steht
    // also in laufenden Aufträgen und wird sie überleben.
    suppliers: asRows(c.suppliers).map((r) => ({
      supplier: Number(r.supplier ?? r), ref: String(r.ref ?? ''),
    })).filter((r) => Number.isFinite(r.supplier)),
    instruction: String(c.instruction ?? ''),
  }),
  config: (m: ModuleDraft) => ({
    suppliers: m.suppliers.map((r) => ({ supplier: r.supplier, ref: r.ref.trim() })),
    instruction: m.instruction.trim(),
  }),
};

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
  // **Ein Eintrag, zwei Module** – kein zweiter daneben: Ein- und Verkauf tragen
  // denselben Beleg, also dieselben zwei Angaben. Was sie unterscheidet, ist nicht ihre
  // Form, sondern ob sie **Pflicht** sind – und das sagt der Katalog des Backends
  // (`suppliers_required` / `instruction_required`), nicht diese Datei.
  beschaffen: TRADE_FORM,
  verkauf: TRADE_FORM,
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
    // Vier Angaben, keine davon Pflicht ausser der Richtung. Keine Erfassungspunkte und
    // keine Stichprobe: Geld ist keine Messung am Stück.
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
  return value.map((v) => (v && typeof v === 'object' ? v as Record<string, unknown> : { supplier: v }));
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
    lines: [], target: '', suppliers: [], instruction: '',
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
