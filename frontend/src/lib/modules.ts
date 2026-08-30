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
  Blocks, Camera, CircleHelp, ClipboardCheck, Hand, MoveRight, PackageX,
  PenLine, Ruler, ShoppingCart, ThumbsUp, Type, type LucideIcon,
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
 * ►►► **Der Einkaufs-Vorgang — Name, Farbe, Symbol.** ◄◄◄
 *
 * Er gehört **keinem Modul** (`domain/procurement`): ein Einkauf sieht überall gleich aus,
 * ob ihn ein Beschaffen-Modul auslöst (dort ist er der Zweck) oder ein Bewegen-Modul
 * (dort war er eine Wahl). Darum steht seine Identität hier und nicht als Eintrag «des
 * Moduls beschaffen» – die Karte des Moduls liest sie ebenso, und beide können nicht
 * auseinanderlaufen.
 *
 * Gespiegelt von `backend/app/domain/procurement.py`; `test_frontend_mirrors` hält Wort
 * und Farbfamilie deckungsgleich. Das **Symbol** kann eine Antwort nicht transportieren –
 * es steht wie bei den Modulen nur hier.
 */
export const PROCUREMENT = {
  label: 'Beschaffen',
  tone: 'plum',
  // Ein Einkaufswagen – bewusst **kein** Lastwagen und kein Paket: der Vorgang kauft, er
  // liefert nicht. Womit die Ware kommt, entscheidet der Lieferant.
  icon: ShoppingCart,
} as const;

/** Prozessschrittmodule (`domain/modules.py`). */
export const MODULE_ICON: Record<string, LucideIcon> = {
  datenerfassung: ClipboardCheck,
  aussondern: PackageX,
  verbrauch: Blocks,
  // Von hier nach dort – bewusst **kein** Transportmittel (kein Lastwagen, kein
  // Gabelstapler): womit bewegt wird, entscheidet sich erst bei der Ausführung.
  bewegen: MoveRight,
  // **Aus derselben Quelle wie der Vorgang** – ein Einkauf sieht überall gleich aus.
  beschaffen: PROCUREMENT.icon,
};

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
  // und Wort kommen darum aus `PROCUREMENT` – dieselbe Quelle, aus der auch die Karte
  // des Beschaffen-Moduls sie nimmt.
  bought: { icon: PROCUREMENT.icon, label: PROCUREMENT.label,
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
  beschaffen: {
    draft: (c) => ({
      // Tolerant gelesen wie im Backend (`Beschaffen.suppliers_of`): die alte Form war
      // die blosse Objektnummer, und ein freigegebener Prozess ist eingefroren – sie
      // steht also in laufenden Aufträgen und wird sie überleben.
      suppliers: asRows(c.suppliers).map((r) => ({
        supplier: Number(r.supplier ?? r), ref: String(r.ref ?? ''),
      })).filter((r) => Number.isFinite(r.supplier)),
      instruction: String(c.instruction ?? ''),
    }),
    // **Zwei Angaben, mehr nicht**: bei wem und was zu tun ist. Kein Artikel – den sagen
    // die Einzelinstanzen vor dem Modul; keine Menge – die steht beim Modellieren nicht
    // fest (dieselbe Regel wie beim Verbrauch); kein Modus «Webshop» – wo jemand seinen
    // Shop hat, ist eine Eigenschaft des Lieferanten und nicht dieser Bestellung.
    config: (m) => ({
      suppliers: m.suppliers.map((r) => ({ supplier: r.supplier, ref: r.ref.trim() })),
      instruction: m.instruction.trim(),
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
  };
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). */
export function toModulePayload(m: ModuleDraft) {
  return { module_type: m.moduleType, config: MODULE_FORM[m.moduleType]?.config(m) ?? {} };
}
