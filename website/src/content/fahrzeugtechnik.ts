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
    { icon: 'clipboard-check', who: 'Wir', title: 'Protokoll', text: 'Sie erhalten ein Protokoll mit Arbeiten und Teilen.', check: 'Fahrmischer zurück' },
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
    h1: 'Fahrmischer, die weiterfahren',
    lead: 'Neue Trommel aufs gute Fahrgestell, Verschleissteile schnell beschafft – und repariert, was auf der Baustelle bricht.',
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
    {
      q: 'Reparieren Sie auch Aufbauten?',
      a: 'Ja – Mulden, Kipper, Hydraulik und Aufbauten von Baufahrzeugen. Fragen Sie an.',
    },
  ],
  promises: ['garantie', 'inexxio365', 'erstservice'],
  service: { name: 'Fahrzeugtechnik', serviceType: 'Trommeltausch und Verschleissteile für Fahrmischer' },
  keywords: ['Trommeltausch Fahrmischer', 'Fahrmischer Trommel', 'Fahrmischer Verschleissteile', 'Fahrmischer Reparatur'],
};

/**
 * Drei Wege, ein Ziel – die Karten der Bereichsseite (components/spezial/FieldCards.astro), je mit
 * der Zeichnung aus dem Menü. Reparatur und Aufbauten haben keine Unterseite (Anker #reparatur).
 */
export const vehicleOffers = {
  title: 'Drei Wege, ein Ziel',
  lead: 'Wir prüfen zuerst und tun nur, was sich lohnt.',
  items: [
    {
      id: 'trommel',
      illo: 'menu/trommeltausch',
      alt: 'Zeichnung: Fahrmischer mit neuer Trommel, die alte liegt daneben',
      title: 'Trommeltausch',
      tags: ['Neue Trommel', 'Revision'],
      text: 'Trommel am Ende, Fahrgestell gut? Dann kommt nur die Trommel neu.',
      examples: ['Kontrolle vorab, offene Empfehlung', 'Neue Trommel oder Revision', 'Antrieb und Hydraulik angeschlossen'],
      link: { href: '/fahrzeugtechnik/trommeltausch', label: 'Zum Trommeltausch' },
    },
    {
      id: 'teile',
      illo: 'menu/verschleissteile',
      alt: 'Zeichnung: Fahrmischer, Rinne, Schurre und Trichter in Rot',
      title: 'Verschleissteile',
      tags: ['Auf Bestellung', 'Mit Einbau'],
      text: 'Sie nennen Marke und Typ, wir beschaffen das Teil.',
      examples: ['Auslauf- und Verlängerungsrinnen', 'Einfülltrichter und Auslaufschurren', 'Spiralschutz'],
      link: { href: '/fahrzeugtechnik/verschleissteile', label: 'Zu den Verschleissteilen' },
    },
    {
      id: 'reparatur',
      illo: 'menu/kranservice',
      alt: 'Zeichnung: roter Werkzeugkasten und Prüfprotokoll',
      title: 'Reparatur',
      tags: ['Fahrmischer', 'Aufbauten'],
      text: 'Was auf der Baustelle bricht, setzen wir instand.',
      examples: ['Mulden, Kipper, Bordwände', 'Hydraulik: Zylinder, Pumpen, Ventile', 'Antrieb, Rahmen und Befestigung'],
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
    faqSpeed,
    promiseFaq.secondOpinion,
  ],
  related: [
    { href: '/fahrzeugtechnik/verschleissteile', label: 'Verschleissteile', text: 'Auf Bestellung, schnell beschafft.' },
    ratgeberTeile,
  ],
  service: { name: 'Trommeltausch für Fahrmischer', serviceType: 'Trommeltausch und Trommel-Revision für Fahrmischer' },
  keywords: ['Trommeltausch', 'Fahrmischer Trommel', 'Mischtrommel', 'Trommel Revision', 'Fahrmischer Reparatur'],
};

/**
 * Tauschen, überholen oder neu kaufen (Anker #wahl) – drei Wege nebeneinander, qualitativ, ohne
 * erfundene Zahlen. Der Trommeltausch ist das eigene Produkt (`own`, die eine dunkle Karte);
 * der neue Fahrmischer ist nicht unser Angebot (`other`, nur umrandet).
 */
export const drumOptions = {
  title: 'Tauschen, überholen – oder neu?',
  lead: 'Was zu Ihrem Fahrzeug passt, sagen wir nach der Kontrolle. Offen – auch wenn es ein neuer Fahrmischer ist.',
  topics: ['Wann', 'Was wir tun', 'Fahrgestell', 'Zeitpunkt'],
  options: [
    { name: 'Trommeltausch', own: true, values: ['Die Trommel ist am Ende, das Fahrgestell gut.', 'Neue Trommel aufs bestehende Fahrgestell, Antrieb und Hydraulik anschliessen.', 'Bleibt.', 'Planbar, am besten im Winter.'] },
    { name: 'Trommel-Revision', values: ['Die Trommel ist verschlissen, aber zu retten.', 'Lager, Dichtungen, Laufring, Rollen und Mischspiralen erneuern.', 'Bleibt.', 'Planbar, am besten im Winter.'] },
    { name: 'Neuer Fahrmischer', other: true, values: ['Auch das Fahrgestell ist am Ende.', 'Nicht unser Angebot – wir sagen es Ihnen, wenn es so weit ist.', 'Wird mit ersetzt.', 'Je nach Lieferzeit.'] },
  ],
  cta: 'Trommel prüfen lassen',
};

/**
 * Der Winter als Zeitpunkt (Anker #winter, Ziel der Saison-Aktion in config/site.mjs): ein Band
 * über zwölf Monate ab September, damit der Winter am Stück steht. `months`: die Tauschmonate.
 */
export const winterSlot = {
  title: 'Im Winter, wenn der Bau ruht',
  text: 'Dann fährt der Fahrmischer wenig – der beste Moment für den Tausch. Wer früh plant, startet im Frühling mit einer neuen Trommel.',
  band: ['S', 'O', 'N', 'D', 'J', 'F', 'M', 'A', 'M', 'J', 'J', 'A'],
  months: [2, 3, 4, 5],
  swap: 'Tausch',
  label: 'Tausch von November bis Februar, ab März Saison',
  ready: 'Saison',
  items: ['Trommel prüfen und tauschen', 'Mischspiralen und Spiralschutz', 'Antrieb und Hydraulik', 'Rinnen, Schurren und Aufbau'],
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

/** Bestellen in drei Schritten – eine Zeile unter dem Katalog. */
export const partsOrder = {
  title: 'Bestellt in drei Schritten',
  items: [
    { title: 'Foto schicken', text: 'Vom Teil, dazu Marke und Typ. Mehr braucht es nicht.' },
    { title: 'Preis erhalten', text: 'Wir beschaffen das Teil und nennen vorher den Preis.' },
    { title: 'Holen oder einbauen', text: 'Abholen in {{address.city}} – oder wir bauen es gleich ein.' },
  ],
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const fahrzeugtechnikPages = [trommeltausch, verschleissteile];
