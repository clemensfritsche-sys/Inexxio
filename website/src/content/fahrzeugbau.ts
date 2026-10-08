/**
 * Fahrzeugbau – Bereichsseite und EINE Unterseite (Testnotiz #1205): Fahrmischer mit
 * Trommeltausch, Revision und Verschleissteilen. Der zweite Punkt im Untermenü –
 * Sonderaufbauten und die Reparatur von Aufbauten – führt auf die Sonderlösungen.
 * Verschleissteile werden NICHT «ab Lager» beworben (es gibt kein Lager, die Teile sind
 * individuell). Versprechen hier: INEXXIO Zufriedenheitsgarantie (der Gratis-Erstservice gilt
 * nur für Krane).
 */
import type { AreaPage, Faq, SubPage } from './types';
import { promiseFaq } from './promises';

const anfrage = (label: string) => ({ label, href: '#anfrage' });

const faqBrands: Faq = {
  q: 'Welche Marken betreuen Sie?',
  a: '{{marks.mixerList}} – und weitere auf Anfrage. {{marks.mixerNotice}}',
};
const faqSpeed: Faq = {
  q: 'Wie schnell ist mein Fahrzeug wieder auf der Strasse?',
  a: 'Das hängt vom Schaden und von den Teilen ab. Nennen Sie uns Marke und Typ – dann beschaffen wir die Teile vorab und planen den Termin.',
};
const ratgeberTeile = { href: '/ratgeber/verschleissteile-fahrmischer', label: 'Verschleissteile am Fahrmischer', text: 'Wann Rinne, Schurre und Spiralschutz ersetzen?', kind: 'ratgeber' as const };

/* ------------------------------------------------------------------ Bereich */
export const fahrzeugbau: AreaPage = {
  id: 'fahrzeugbau',
  path: '/fahrzeugbau',
  title: 'Fahrmischer und Aufbauten',
  description:
    'Trommeltausch statt neuer Fahrmischer – nicht zufrieden, zahlen Sie nur die Hälfte. Dazu Revision, Verschleissteile und Sonderaufbauten nach Mass.',
  hero: {
    eyebrow: 'Fahrzeugbau',
    h1: 'Neue Trommel statt neuer ==Fahrmischer==',
    lead:
      'Ist die Trommel am Ende, das Fahrgestell aber gut, setzen wir eine neue Trommel auf – zum Fixpreis, und sind Sie nicht zufrieden, zahlen Sie nur die Hälfte. Dazu warten und reparieren wir Fahrmischer aller gängigen Marken und bauen Sonderaufbauten nach Mass.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle (Trommeltausch) und wartet und repariert Fahrmischer der Marken {{marks.mixerList}} – mit Verschleissteilen für alle gängigen Marken. Dazu kommen Sonderaufbauten und die Reparatur von LKW-Aufbauten, Mulden und Kippern. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  steps: [
    { title: 'Anfrage', text: 'Sie nennen Marke, Typ und Anliegen – per Formular oder am Telefon.' },
    { title: 'Abklärung', text: 'Wir klären, was es braucht, nennen einen Fixpreis und planen den Termin.' },
    { title: 'Umsetzung', text: 'Wir warten oder reparieren in der Werkstatt und ersetzen verschlissene Teile.' },
    { title: 'Bericht', text: 'Sie erhalten einen Rapport mit Arbeiten und Teilen.' },
  ],
  faq: [
    {
      q: 'Was ist ein Trommeltausch?',
      a: 'Wir setzen eine neue Mischtrommel auf Ihr bestehendes Fahrgestell. Ist das Fahrzeug noch gut, sparen Sie so den neuen Fahrmischer. Mehr dazu unter [Fahrmischer](/fahrzeugbau/fahrmischer#trommel).',
    },
    promiseFaq.garantie,
    faqBrands,
    faqSpeed,
    {
      q: 'Liefern Sie auch Verschleissteile ohne Montage?',
      a: 'Ja. Rinnen, Schurren, Trichter und Spiralschutz können Sie auch als Teil anfragen.',
    },
    {
      q: 'Bauen Sie auch Aufbauten?',
      a: 'Ja – Sonderaufbauten nach Mass, und wir reparieren bestehende. Mehr dazu unter [Sonderlösungen](/sonderloesungen#fahrzeugbau).',
    },
  ],
  promises: ['garantie'],
  service: { name: 'Fahrzeugbau', serviceType: 'Trommeltausch, Service und Reparatur von Fahrmischern, Sonderaufbauten' },
  keywords: ['Trommeltausch Fahrmischer', 'Fahrmischer Service', 'Fahrmischer Reparatur', 'Trommel Revision'],
};

/* ------------------------------------------------------------------ Fahrmischer */
export const fahrmischer: SubPage = {
  area: 'fahrzeugbau',
  path: '/fahrzeugbau/fahrmischer',
  crumb: 'Fahrmischer',
  title: 'Fahrmischer und Mischtrommel',
  description:
    'Trommeltausch statt neuer Fahrmischer, mit Zufriedenheitsgarantie. Dazu Revision, Service und Verschleissteile für alle gängigen Marken – zum Fixpreis.',
  hero: {
    eyebrow: 'Fahrzeugbau · Fahrmischer',
    h1: 'Fahrmischer: ==Trommeltausch==, Revision und Verschleissteile',
    lead:
      'Ist die Trommel am Ende, das Fahrgestell aber gut, setzen wir eine neue Trommel auf – statt eines neuen Fahrmischers. Wir warten und reparieren Trommel, Antrieb, Hydraulik, Rinnen und Aufbau aller gängigen Marken und liefern die Verschleissteile dazu.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Trommeltausch anfragen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle (Trommeltausch) – zum Fixpreis, und sind Sie nicht zufrieden, zahlen Sie nur die Hälfte. Eine verschlissene Trommel überholen wir auch (Trommel-Revision), und wir warten und reparieren Fahrmischer der Marken {{marks.mixerList}}. Am liebsten im Winter – in der Werkstatt in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Fuhrpark- und Werkstattleiter in Betonwerken, Bau- und Transportunternehmen.',
    what: 'Trommeltausch und Trommel-Revision, Service nach Herstellervorgabe, Fehlersuche, Reparatur – und Verschleissteile, mit oder ohne Einbau.',
    deliverables: 'Einen Fahrmischer, der wieder läuft – ohne neues Fahrzeug – und einen Rapport mit Arbeiten und Teilen.',
  },
  promises: ['garantie'],
  scope: {
    title: 'Leistungsumfang',
    lead: 'Für alle gängigen Marken.',
    items: [
      { title: 'Trommel', text: 'Tausch gegen eine neue Trommel – oder Revision: Lager, Dichtungen, Laufring, Rollen, Mischspiralen.' },
      { title: 'Antrieb', text: 'Trommelgetriebe, Hydraulikmotor und Pumpe – Fehlersuche, Reparatur, Ersatz.' },
      { title: 'Hydraulik', text: 'Schläuche, Leitungen, Ventile und Ölkühler; Lecks finden und beheben.' },
      { title: 'Verschleissteile', text: 'Rinnen, Schurren, Trichter und Spiralschutz – als Teil oder mit Einbau, der Katalog steht unten.' },
      { title: 'Aufbau', text: 'Rahmen und Befestigung, Wassersystem, Leiter, Bedienelemente und Beleuchtung.' },
      { title: 'Service', text: 'Ölwechsel, Schmierung und Kontrolle nach Vorgabe des Herstellers.' },
    ],
  },
  faq: [
    faqBrands,
    {
      q: 'Revision oder Trommeltausch – was ist der Unterschied?',
      a: 'Bei der Revision überholen wir die bestehende Trommel: Lager, Dichtungen, Laufring, Rollen und Mischspiralen. Beim Tausch kommt eine neue Trommel auf das bestehende Fahrgestell – wenn die alte nicht mehr zu retten ist.',
    },
    {
      q: 'Wann lohnt sich ein Trommeltausch?',
      a: 'Wenn die Trommel verschlissen ist, Fahrgestell, Antrieb und Aufbau aber noch gut sind. Das prüfen wir vorher und sagen es Ihnen offen – auch, wenn ein neuer Fahrmischer die bessere Lösung ist.',
    },
    {
      q: 'Was kostet eine Revision oder ein Trommeltausch?',
      a: 'Das hängt von Trommel, Fahrzeug und Zustand ab. Nach der ersten Kontrolle erhalten Sie einen Fixpreis.',
    },
    promiseFaq.garantie,
    faqSpeed,
    {
      q: 'Kann ich ein Verschleissteil abholen?',
      a: 'Ja, in Tuttwil – am besten vorher kurz anrufen: {{phone.link}}. Preise nennen wir auf Anfrage; sie hängen von Ausführung und Typ ab.',
    },
    {
      q: 'Sind Sie Vertragshändler einer Marke?',
      a: 'Nein. {{marks.mixerNotice}}',
    },
  ],
  related: [
    { href: '/sonderloesungen#fahrzeugbau', label: 'Sonderaufbauten', text: 'Aufbauten nach Mass, Mulden, Kipper und Hydraulik.' },
    ratgeberTeile,
  ],
  service: { name: 'Fahrmischer-Service, Trommel-Revision und Trommeltausch', serviceType: 'Service, Reparatur und Trommeltausch von Fahrmischern' },
  keywords: ['Fahrmischer Service', 'Fahrmischer Reparatur', 'Trommel Revision', 'Trommeltausch', 'Fahrmischer Verschleissteile', 'Fahrmischer Rinne'],
};

/**
 * Modul (Anker #trommel): tauschen, überholen oder neu kaufen – drei Wege nebeneinander,
 * qualitativ, ohne erfundene Zahlen. Der Trommeltausch ist das eigene Produkt (`own`).
 */
export const drumOptions = {
  title: 'Die Trommel: tauschen oder überholen?',
  lead: 'Was zu Ihrem Fahrzeug passt, sagen wir nach der ersten Kontrolle – offen, auch wenn ein neuer Fahrmischer die bessere Lösung ist.',
  topics: ['Wann sinnvoll', 'Was wir tun', 'Fahrgestell', 'Zeitpunkt'],
  options: [
    { name: 'Trommeltausch', own: true, values: ['Die Trommel ist am Ende, das Fahrgestell gut.', 'Eine neue Trommel auf das bestehende Fahrgestell setzen, Antrieb und Hydraulik anschliessen.', 'Bleibt.', 'Planbar, am liebsten im Winter.'] },
    { name: 'Trommel-Revision', values: ['Die Trommel ist verschlissen, aber zu retten.', 'Lager, Dichtungen, Laufring, Rollen und Mischspiralen erneuern.', 'Bleibt.', 'Planbar, am liebsten im Winter.'] },
    { name: 'Neuer Fahrmischer', values: ['Auch das Fahrgestell ist am Ende.', 'Nicht unser Angebot – wir sagen es Ihnen, wenn es so weit ist.', 'Wird mit ersetzt.', 'Abhängig von der Lieferzeit.'] },
  ],
};

/** Modul: Winter (Anker #winter-revision) und Markenliste. */
export const winterRevision = {
  title: 'Im Winter, wenn der Bau ruht',
  text: 'Im Winter fährt ein Fahrmischer weniger – der beste Moment für Revision oder Trommeltausch. Wer früh plant, hat den Fahrmischer im Frühling bereit, wenn die Saison anzieht.',
  items: ['Trommel, Lager und Dichtungen', 'Mischspiralen und Spiralschutz', 'Antrieb und Hydraulik', 'Rinnen, Schurren und Aufbau'],
  cta: 'Winter-Termin planen',
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const fahrzeugbauPages = [fahrmischer];
