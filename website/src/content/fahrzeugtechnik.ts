/**
 * Fahrzeugtechnik – Bereichsseite und zwei Unterseiten: Trommeltausch (das stärkste Angebot,
 * zuerst) und Verschleissteile. Reparatur und Aufbauten sind die dritte Karte der Bereichsseite
 * (Anker #reparatur), ohne eigene Unterseite. Verschleissteile werden NICHT «ab Lager»
 * beworben – sie werden bestellt und schnell beschafft. Beide Garantien und die Gratis-
 * Inspektion gelten auch hier (content/promises.ts).
 *
 * Die drei Seiten haben ein eigenes Layout (Muster Speziallösungen, Oktober 2026); die
 * `AreaPage`-/`SubPage`-Objekte liefern Titel, Beschreibung, Zusammenfassung, Leistungsumfang
 * und FAQ für Sitemap, llms.txt und JSON-LD. Was auf der Seite als Weg steht, ist dort die
 * Quelle – Ablauf (`steps`) und Leistungsumfang (`scope`) werden daraus abgeleitet.
 * Bildsprache: Grau ist das Fahrzeug, Rot ist, was wir tun.
 */
import type { IconName } from '../components/Icon.astro';
import type { AreaPage, Faq, SubPage } from './types';
import { promiseFaq } from './promises';

const anfrage = (label: string) => ({ label, href: '#anfrage' });

const faqBrands: Faq = {
  q: 'Welche Marken betreuen Sie?',
  a: '{{marks.mixerList}} – und weitere auf Anfrage. {{marks.mixerNotice}}',
};
const faqSpeed: Faq = {
  q: 'Wie schnell ist mein Fahrmischer wieder im Einsatz?',
  a: 'Das hängt von Trommel und Teilen ab. Nennen Sie uns Marke und Typ – dann beschaffen wir die Teile vorab und planen den Termin.',
};
const ratgeberTeile = { href: '/ratgeber/verschleissteile-fahrmischer', label: 'Verschleissteile am Fahrmischer', text: 'Wann Rinne, Schurre und Spiralschutz ersetzen?', kind: 'ratgeber' as const };

/** Eine Station auf dem Weg (components/spezial/SolutionPath.astro). */
interface Station { icon: IconName; who: string; title: string; text: string; tags?: string[]; check?: string }
const facts = (items: Station[]) => items.map(({ title, text }) => ({ title, text }));

/* ------------------------------------------------------------------ Bereich */
/** Der Weg auf der Bereichsseite – zugleich der Ablauf in vier Schritten (`steps`). */
export const vehiclePath = {
  title: 'So läuft es ab',
  start: 'Ihr Fahrmischer',
  end: 'Wieder im Einsatz',
  items: [
    { icon: 'phone', who: 'Sie', title: 'Anfrage', text: 'Sie nennen Marke, Typ und Anliegen – per Formular oder am Telefon.', tags: ['Foto', 'Marke', 'Typ'] },
    { icon: 'search', who: 'Gemeinsam', title: 'Kontrolle', text: 'Wir prüfen Trommel und Fahrgestell und sagen offen, was sich lohnt.', check: 'Verbindliche Offerte' },
    { icon: 'wrench', who: 'Wir', title: 'Umsetzung', text: 'Neue Trommel, Teile oder Reparatur – bei uns in {{address.city}}.', tags: ['Trommel', 'Teile', 'Hydraulik'] },
    { icon: 'truck', who: 'Gemeinsam', title: 'Übergabe', text: 'Probelauf bestanden – Ihr Fahrmischer fährt wieder.', check: 'Jede Arbeit dokumentiert' },
  ] satisfies Station[],
};

export const fahrzeugtechnik: AreaPage = {
  id: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik',
  title: 'Fahrzeugtechnik: Fahrmischer',
  description:
    'Neue Trommel statt neuer Fahrmischer – mit verbindlicher Offerte und Zufriedenheitsgarantie. Dazu Verschleissteile, schnell beschafft. Aus {{address.home}}.',
  hero: {
    eyebrow: 'Fahrzeugtechnik',
    h1: 'Länger fahren statt neu kaufen',
    lead: 'Trommeltausch, Verschleissteile und Reparatur für Fahrmischer aller gängigen Marken.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Fahrmischer anfragen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle (Trommeltausch) – mit verbindlicher Offerte und mit Zufriedenheitsgarantie: Nicht zufrieden, übernehmen wir 50 %. Mit INEXXIO 365 ist der Fahrmischer einsatzbereit – Ausfälle übernehmen wir. Verschleissteile wie Rinnen, Schurren, Trichter und Spiralschutz beschaffen wir auf Bestellung. Der Standort ist in {{address.home}}; im Einsatz sind wir {{area.summary}}.',
  steps: facts(vehiclePath.items),
  faq: [
    {
      q: 'Was ist ein Trommeltausch?',
      a: 'Wir setzen eine neue Mischtrommel auf Ihr bestehendes Fahrgestell. Ist das Fahrzeug noch gut, sparen Sie so den neuen Fahrmischer. Mehr dazu unter [Trommeltausch](/fahrzeugtechnik/trommeltausch).',
    },
    promiseFaq.garantie,
    faqBrands,
    faqSpeed,
    {
      q: 'Liefern Sie auch Verschleissteile ohne Montage?',
      a: 'Ja. Rinnen, Schurren, Trichter und Spiralschutz bestellen Sie auch als Teil. Mehr dazu unter [Verschleissteile](/fahrzeugtechnik/verschleissteile).',
    },
  ],
  promises: ['garantie', 'inexxio365', 'erstservice'],
  service: { name: 'Fahrzeugtechnik', serviceType: 'Trommeltausch und Verschleissteile für Fahrmischer' },
  keywords: ['Trommeltausch Fahrmischer', 'Fahrmischer Trommel', 'Fahrmischer Verschleissteile', 'Fahrmischer Reparatur'],
};

/**
 * Alles für Ihren Fahrmischer – die Karten der Bereichsseite (components/spezial/FieldCards.astro), je mit
 * der Zeichnung aus dem Menü. Reparatur und Aufbauten haben keine Unterseite (Anker #reparatur).
 */
export const vehicleOffers = {
  title: 'Alles für Ihren Fahrmischer',
  lead: 'Von der Rinne bis zur neuen Trommel.',
  items: [
    {
      id: 'trommel',
      illo: 'menu/trommeltausch',
      alt: 'Zeichnung: Fahrmischer mit neuer Trommel, die alte liegt daneben',
      title: 'Trommeltausch',
      text: 'Trommel am Ende, Fahrgestell gut? Dann kommt nur die Trommel neu.',
      href: '/fahrzeugtechnik/trommeltausch',
    },
    {
      id: 'teile',
      illo: 'menu/verschleissteile',
      alt: 'Zeichnung: Fahrmischer, Rinne, Schurre und Trichter in Rot',
      title: 'Verschleissteile',
      text: 'Rinnen, Schurren, Trichter: schnell beschafft, auf Wunsch eingebaut.',
      href: '/fahrzeugtechnik/verschleissteile',
    },
    {
      id: 'reparatur',
      illo: 'menu/kranservice',
      alt: 'Zeichnung: roter Werkzeugkasten und Prüfprotokoll',
      title: 'Reparatur',
      text: 'Hydraulik, Antrieb, Aufbau: Was auf der Baustelle bricht, setzen wir instand.',
    },
  ],
};

/* ------------------------------------------------------------------ Trommeltausch */
/** Was zum Trommeltausch gehört – als Weg auf der Seite, zugleich der Leistungsumfang (`scope`). */
export const drumPath = {
  title: 'Was zum Tausch gehört',
  start: 'Trommel am Ende',
  end: 'Wieder im Einsatz',
  items: [
    { icon: 'search', who: 'Gemeinsam', title: 'Kontrolle vorab', text: 'Trommel, Fahrgestell, Antrieb und Aufbau – Sie erfahren offen, ob sich der Tausch lohnt.', check: 'Verbindliche Offerte' },
    { icon: 'truck', who: 'Wir', title: 'Neue Trommel', text: 'Passend zu Fahrgestell und Einsatz, aufgesetzt bei uns in {{address.city}}.' },
    { icon: 'wrench', who: 'Wir', title: 'Antrieb und Hydraulik', text: 'Anschliessen, prüfen und, wo nötig, ersetzen.', tags: ['Getriebe', 'Hydraulikmotor', 'Pumpe', 'Ölkühler'] },
    { icon: 'drafting-compass', who: 'Wir', title: 'Aufbau', text: 'Rahmen und Befestigung, dazu alles, was an der Trommel hängt.', tags: ['Wassersystem', 'Leiter', 'Beleuchtung'] },
    { icon: 'flag', who: 'Wir', title: 'Inbetriebnahme', text: 'Probelauf und Protokoll – dann fährt der Fahrmischer wieder.', tags: ['Probelauf', 'Protokoll'] },
  ] satisfies Station[],
};

export const trommeltausch: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/trommeltausch',
  crumb: 'Trommeltausch',
  title: 'Trommeltausch für Fahrmischer',
  description:
    'Neue Trommel auf das bestehende Fahrgestell statt neuer Fahrmischer – mit verbindlicher Offerte. Nicht zufrieden? Die Hälfte übernehmen wir.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Trommeltausch',
    h1: 'Neue Trommel. Gleicher Fahrmischer.',
    lead: 'Ist nur die Trommel am Ende, setzen wir eine neue auf Ihr Fahrgestell – mit verbindlicher Offerte. Nicht zufrieden? Die Hälfte übernehmen wir.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Trommeltausch anfragen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle – etwa für {{marks.mixerList}}. Verbindliche Offerte vor jeder Arbeit, und mit der Zufriedenheitsgarantie übernehmen wir 50 %, wenn Sie nicht zufrieden sind. Ist die Trommel noch zu retten, überholen wir sie (Trommel-Revision). Am besten im Winter – bei uns in {{address.home}}.',
  glance: {
    forWhom: 'Fuhrparkleiter in Betonwerken, Bau- und Transportunternehmen mit eigenen Fahrmischern.',
    what: 'Trommel und Fahrgestell prüfen, neue Trommel aufsetzen, Antrieb und Hydraulik anschliessen, in Betrieb nehmen.',
    deliverables: 'Einen Fahrmischer, der wieder einsatzbereit ist – ohne neues Fahrzeug – und ein Protokoll mit Arbeiten und Teilen.',
  },
  promises: ['garantie', 'inexxio365', 'erstservice'],
  scope: { title: drumPath.title, items: facts(drumPath.items) },
  faq: [
    {
      q: 'Wann lohnt sich ein Trommeltausch?',
      a: 'Wenn die Trommel verschlissen ist, Fahrgestell, Antrieb und Aufbau aber noch gut sind. Das prüfen wir vorher und sagen es Ihnen offen – auch, wenn ein neuer Fahrmischer die bessere Lösung ist.',
    },
    {
      q: 'Revision oder Trommeltausch – was ist der Unterschied?',
      a: 'Bei der Revision überholen wir die bestehende Trommel: Lager, Dichtungen, Laufring, Rollen und Mischspiralen. Beim Tausch kommt eine neue Trommel auf das bestehende Fahrgestell.',
    },
    {
      q: 'Was kostet ein Trommeltausch?',
      a: 'Das hängt von Trommel, Fahrzeug und Zustand ab. Nach der Kontrolle erhalten Sie eine verbindliche Offerte.',
    },
    promiseFaq.garantie,
    faqBrands,
  ],
  related: [
    { href: '/fahrzeugtechnik/verschleissteile', label: 'Verschleissteile', text: 'Auf Bestellung, schnell beschafft.' },
    ratgeberTeile,
  ],
  service: { name: 'Trommeltausch für Fahrmischer', serviceType: 'Trommeltausch und Trommel-Revision für Fahrmischer' },
  keywords: ['Trommeltausch', 'Fahrmischer Trommel', 'Mischtrommel', 'Trommel Revision', 'Fahrmischer Reparatur'],
};

/**
 * Tauschen, überholen oder neu kaufen (Anker #wahl) – die Bühne der Startseite
 * (components/home/SpecialStage.astro): ein Umschalter, die Zeichnung blendet über. Bildregel: rot ist,
 * was wir erneuern; der neue Fahrmischer steht hell da – er ist nicht unser Angebot.
 */
export const drumOptions = {
  title: 'Tauschen, überholen – oder neu?',
  lead: 'Was zu Ihrem Fahrzeug passt, sagen wir nach der Kontrolle. Offen.',
  legend: { grey: 'Grau: was bleibt', red: 'Rot: was wir erneuern' },
  items: [
    { title: 'Tauschen', text: 'Die Trommel ist am Ende, das Fahrgestell gut: Eine neue Trommel kommt auf Ihr Fahrgestell.', illo: 'menu/trommeltausch', alt: 'Zeichnung: Fahrmischer mit neuer roter Trommel, die alte liegt daneben' },
    { title: 'Überholen', text: 'Die Trommel ist verschlissen, aber zu retten: Wir erneuern Lager, Dichtungen, Laufring, Rollen und Mischspiralen.', illo: 'trommel-revision', alt: 'Zeichnung: Fahrmischer mit der bestehenden Trommel, die Mischspiralen rot' },
    { title: 'Neu kaufen', text: 'Ist auch das Fahrgestell am Ende, lohnt sich nur ein neuer Fahrmischer. Das sagen wir Ihnen offen.', illo: 'trommel-neu', alt: 'Zeichnung: ein neuer Fahrmischer, ganz hell' },
  ],
  cta: { label: 'Trommel prüfen lassen', href: '#anfrage' },
};

/**
 * Der Winter als Zeitpunkt (Anker #winter, Ziel der Saison-Aktion in config/site.mjs): ein Wandkalender
 * Januar bis Dezember – die Wintermonate dunkel mit Schneeflocke («Tausch»), die übrigen hell mit dem
 * Fahrmischer («Einsatz»). Wer draufschaut, sieht: im Winter steht er, dann ist Zeit für den Tausch.
 */
export const winterSlot = {
  title: 'Im Winter, wenn der Bau ruht',
  text: 'Dann brauchen Sie den Fahrmischer kaum – der beste Moment für Tausch oder Revision. Im Frühling ist er bereit.',
  months: ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'],
  /** Die Monate (Index ab Januar), in denen der Bau ruht. */
  winter: [0, 1, 10, 11],
  cold: { icon: 'snowflake' as IconName, word: 'Tausch', legend: 'Bau ruht – Zeit für den Tausch' },
  warm: { icon: 'truck' as IconName, word: 'Einsatz', legend: 'Bausaison – Ihr Fahrmischer fährt' },
  cta: 'Winter-Termin planen',
};

/* ------------------------------------------------------------------ Verschleissteile */
export const verschleissteile: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/verschleissteile',
  crumb: 'Verschleissteile',
  title: 'Fahrmischer-Verschleissteile',
  description:
    'Rinnen, Schurren, Trichter und Spiralschutz für Fahrmischer – auf Bestellung, schnell beschafft. Mit oder ohne Einbau, mit verbindlicher Offerte. Jetzt anfragen.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Verschleissteile',
    h1: 'Verschleissteile. Schnell beschafft.',
    lead: 'Rinnen, Schurren, Trichter und Spiralschutz. Nennen Sie Marke und Typ – wir beschaffen das Teil, mit oder ohne Einbau.',
    photo: 'teil-auslaufrinne',
    primary: anfrage('Teil anfragen'),
  },
  summary:
    '{{brand.full}} beschafft Verschleissteile für Fahrmischer auf Bestellung: Auslauf- und Verlängerungsrinnen, Einfülltrichter, Auslaufschurren und Spiralschutz – als Teil oder mit Einbau bei uns in {{address.home}}.',
  glance: {
    forWhom: 'Fuhrparkleiter in Betonwerken, Bau- und Transportunternehmen mit eigenen Fahrmischern.',
    what: 'Teile nach Marke und Typ bestellen und schnell beschaffen – auf Wunsch mit Einbau.',
    deliverables: 'Das passende Teil, rasch bei Ihnen oder eingebaut, mit einer verbindlichen Offerte vorab.',
  },
  scope: {
    title: 'Welche Teile wir beschaffen',
    items: [
      { title: 'Rinnen', text: 'Auslauf- und Verlängerungsrinnen.' },
      { title: 'Trichter und Schurren', text: 'Einfülltrichter und Auslaufschurren.' },
      { title: 'Spiralschutz', text: 'Schutz der Mischspiralen gegen Abrieb.' },
      { title: 'Einbau', text: 'Auf Wunsch bei uns in {{address.city}}, zusammen mit Service oder Trommeltausch.' },
    ],
  },
  faq: [
    {
      q: 'Wie bestelle ich ein Teil?',
      a: 'Nennen Sie uns Marke, Typ und das Teil – am einfachsten mit einem Foto. Wir beschaffen es schnell und nennen vorher den Preis.',
    },
    {
      q: 'Kann ich ein Teil abholen?',
      a: 'Ja, in {{address.city}} – am besten vorher kurz anrufen: {{phone.link}}.',
    },
    faqBrands,
    {
      q: 'Sind Sie Vertragshändler einer Marke?',
      a: 'Nein. {{marks.mixerNotice}}',
    },
  ],
  related: [
    { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch', text: 'Neue Trommel statt neuer Fahrmischer.' },
    ratgeberTeile,
  ],
  service: { name: 'Verschleissteile für Fahrmischer', serviceType: 'Beschaffung und Einbau von Verschleissteilen für Fahrmischer' },
  keywords: ['Fahrmischer Verschleissteile', 'Fahrmischer Rinne', 'Auslaufschurre', 'Spiralschutz', 'Einfülltrichter'],
};

/** Kopf des Katalogs. */
export const partsCatalog = {
  title: 'Katalog',
  lead: 'Auf Bestellung beschafft, auf Wunsch eingebaut. Den Preis erfahren Sie vorab.',
};

/** Bestellen in drei Schritten – als Weg (components/spezial/SolutionPath.astro). */
export const partsOrder = {
  title: 'Bestellt in drei Schritten',
  start: 'Ihr Teil fehlt',
  end: 'Wieder im Einsatz',
  items: [
    { icon: 'camera', who: 'Sie', title: 'Foto schicken', text: 'Vom Teil, dazu Marke und Typ. Mehr braucht es nicht.', tags: ['Foto', 'Marke', 'Typ'] },
    { icon: 'search', who: 'Wir', title: 'Preis erhalten', text: 'Wir beschaffen das Teil und nennen vorher den Preis.', check: 'Preis vorab' },
    { icon: 'package', who: 'Wir', title: 'Holen oder einbauen', text: 'Abholen in {{address.city}} – oder wir bauen es gleich ein.', tags: ['Abholen', 'Einbau'] },
  ] satisfies Station[],
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const fahrzeugtechnikPages = [trommeltausch, verschleissteile];
