/**
 * Fahrzeugtechnik – Bereichsseite und vier Unterseiten (STRATEGIE.md, 6.10.2026).
 * Der Trommeltausch ist das erste eigene Produkt und steht vorn. Service und Teile für alle
 * gängigen Marken – Verschleissteile werden NICHT «ab Lager» beworben (es gibt kein Lager,
 * die Teile sind individuell). Keine Neuaufbauten.
 */
import { site } from '../config/site.mjs';
import type { AreaPage, Faq, SubPage } from './types';

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
export const fahrzeugtechnik: AreaPage = {
  id: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik',
  title: 'Trommeltausch & Fahrmischer',
  description:
    'Trommeltausch statt neuer Fahrmischer: neue Trommel auf dem bestehenden Fahrgestell. Dazu Service, Reparatur und Verschleissteile für alle gängigen Marken.',
  hero: {
    eyebrow: 'Fahrzeugtechnik',
    h1: 'Neue Trommel statt neuer ==Fahrmischer==',
    lead:
      'Ist die Trommel am Ende, das Fahrgestell aber gut, setzen wir eine neue Trommel auf Ihr Fahrzeug. Dazu warten und reparieren wir Fahrmischer und Aufbauten aller gängigen Marken. Neuaufbauten machen wir nicht.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle (Trommeltausch) und wartet und repariert Fahrmischer der Marken {{marks.mixerList}}. Dazu kommen die Reparatur von LKW-Aufbauten, Mulden und Kippern und Verschleissteile für alle gängigen Marken. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  levels: [
    {
      title: 'Trommeltausch',
      text: 'Neue Trommel, bewährtes Fahrgestell: Sie sparen den neuen Fahrmischer. Am liebsten im Winter, wenn der Bau ruht.',
      links: [
        { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch' },
        { href: '/fahrzeugtechnik/fahrmischer#winter-revision', label: 'Winter-Revision' },
      ],
    },
    {
      title: 'Service & Reparatur',
      text: 'Service nach Herstellervorgabe, Fehlersuche und Reparatur – alle gängigen Marken an einem Ort.',
      links: [
        { href: '/fahrzeugtechnik/fahrmischer', label: 'Fahrmischer-Service' },
        { href: '/fahrzeugtechnik/aufbauten-reparatur#leistungen', label: 'Hydraulik und Aufbau' },
        { href: '/service/notfall', label: 'Notfall-Service' },
      ],
    },
    {
      title: 'Ersatz- und Verschleissteile',
      text: 'Rinnen, Schurren, Trichter und Spiralschutz für alle gängigen Marken – passend zu Ihrem Typ beschafft, auf Wunsch mit Einbau.',
      links: [
        { href: '/fahrzeugtechnik/verschleiss-ersatzteile', label: 'Teilekatalog' },
        { href: '/kontakt', label: 'Teil anfragen' },
      ],
    },
  ],
  steps: [
    { title: 'Anfrage', text: 'Sie nennen Marke, Typ und Anliegen – per Formular oder am Telefon.' },
    { title: 'Abklärung', text: 'Wir klären, was es braucht, halten die Teile bereit und planen den Termin.' },
    { title: 'Umsetzung', text: 'Wir warten oder reparieren in der Werkstatt und ersetzen verschlissene Teile.' },
    { title: 'Bericht', text: 'Sie erhalten einen Rapport mit Arbeiten und Teilen.' },
  ],
  faq: [
    {
      q: 'Was ist ein Trommeltausch?',
      a: 'Wir setzen eine neue Mischtrommel auf Ihr bestehendes Fahrgestell. Ist das Fahrzeug noch gut, sparen Sie so den neuen Fahrmischer. Mehr dazu auf der Seite [Trommeltausch](/fahrzeugtechnik/trommeltausch).',
    },
    faqBrands,
    faqSpeed,
    {
      q: 'Bauen Sie auch neue Aufbauten?',
      a: 'Nein. Wir reparieren und setzen instand, was auf Ihrem Fahrzeug ist – Neuaufbauten und Fahrzeughandel gehören nicht mehr zu unserem Angebot.',
    },
    {
      q: 'Wann ist der beste Zeitpunkt für eine Trommel-Revision?',
      a: 'Im Winter, wenn der Bau ruht und der Fahrmischer ohnehin weniger fährt. Dann fehlt er nicht, wenn es auf der Baustelle eilt.',
    },
    {
      q: 'Liefern Sie auch Verschleissteile ohne Montage?',
      a: 'Ja. Rinnen, Schurren, Trichter und Spiralschutz können Sie auch als Teil anfragen.',
    },
  ],
  service: { name: 'Fahrzeugtechnik', serviceType: 'Trommeltausch, Service und Reparatur von Fahrmischern und Aufbauten' },
  keywords: ['Trommeltausch Fahrmischer', 'Fahrmischer Service', 'Fahrmischer Reparatur', 'Trommel Revision'],
};

/* ------------------------------------------------------------------ Trommeltausch */
export const trommeltausch: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/trommeltausch',
  crumb: 'Trommeltausch',
  title: 'Trommeltausch für Fahrmischer',
  description:
    'Trommeltausch statt neuer Fahrmischer: neue Mischtrommel auf dem bestehenden Fahrgestell, für alle gängigen Marken. Werkstatt in Tuttwil-Wängi TG.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Trommeltausch',
    h1: 'Neue ==Trommel==, bewährtes Fahrgestell',
    lead:
      'Ist die Trommel verschlissen, das Fahrgestell aber gut, braucht es keinen neuen Fahrmischer. Wir setzen eine neue Trommel auf Ihr bestehendes Fahrzeug – für alle gängigen Marken.',
    photo: 'trommeltausch',
    primary: anfrage('Trommeltausch anfragen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle – für Fahrmischer der Marken {{marks.mixerList}}. Vorher prüfen wir, ob sich der Tausch lohnt. Der Umbau geschieht in der Werkstatt in Tuttwil-Wängi TG, am liebsten im Winter.',
  glance: {
    forWhom: 'Betonwerke, Bau- und Transportunternehmen mit Fahrmischern, deren Trommel am Ende ist.',
    what: 'Zustand prüfen, neue Trommel beschaffen, alte ab- und neue aufbauen, Antrieb und Hydraulik anschliessen, in Betrieb nehmen.',
    deliverables: 'Einen Fahrmischer mit neuer Trommel – ohne die Investition in ein neues Fahrzeug – und einen Rapport.',
  },
  scope: {
    title: 'Was zum Trommeltausch gehört',
    lead: 'Von der ehrlichen Einschätzung bis zur ersten Fahrt.',
    items: [
      { title: 'Bestandsaufnahme', text: 'Fahrgestell, Antrieb und Aufbau anschauen: Lohnt sich der Tausch? Wir sagen es offen.' },
      { title: 'Neue Trommel', text: 'Passend zu Fahrgestell, Marke und Volumen beschafft.' },
      { title: 'Ab- und Aufbau', text: 'Alte Trommel abbauen, neue setzen und befestigen – in unserer Werkstatt.' },
      { title: 'Antrieb und Hydraulik', text: 'Getriebe, Motor und Pumpe prüfen und anschliessen; was verschlissen ist, ersetzen wir mit.' },
      { title: 'Rinnen und Verschleissteile', text: 'Rinnen, Schurren und Trichter auf Wunsch gleich mit erneuern.' },
      { title: 'Inbetriebnahme', text: 'Probelauf, Kontrolle und ein Rapport mit allen Arbeiten und Teilen.' },
    ],
  },
  faq: [
    {
      q: 'Wann lohnt sich ein Trommeltausch?',
      a: 'Wenn die Trommel verschlissen ist, Fahrgestell, Antrieb und Aufbau aber noch gut sind. Das prüfen wir vorher und sagen es Ihnen offen – auch, wenn ein neuer Fahrmischer die bessere Lösung ist.',
    },
    {
      q: 'Für welche Marken machen Sie einen Trommeltausch?',
      a: 'Für alle gängigen Marken wie {{marks.mixerList}}. {{marks.mixerNotice}}',
    },
    {
      q: 'Was kostet ein Trommeltausch?',
      a: 'Das hängt von Trommel, Fahrzeug und Zustand ab. Nach der Bestandsaufnahme erhalten Sie eine Offerte.',
    },
    {
      q: 'Wann ist der beste Zeitpunkt?',
      a: 'Im Winter, wenn der Bau ruht. Dann fehlt der Fahrmischer nicht, wenn es auf der Baustelle eilt.',
    },
    {
      q: 'Was ist der Unterschied zur Trommel-Revision?',
      a: 'Bei der Revision überholen wir die bestehende Trommel: Lager, Dichtungen, Laufring, Mischspiralen. Beim Tausch kommt eine neue Trommel auf das Fahrzeug – wenn die alte nicht mehr zu retten ist.',
    },
  ],
  related: [
    { href: '/fahrzeugtechnik/fahrmischer', label: 'Fahrmischer-Service', text: 'Service, Reparatur und Trommel-Revision.' },
    { href: '/fahrzeugtechnik/verschleiss-ersatzteile', label: 'Verschleiss- und Ersatzteile', text: 'Rinnen, Schurren und Spiralschutz.' },
    ratgeberTeile,
  ],
  service: { name: 'Trommeltausch für Fahrmischer', serviceType: 'Austausch der Mischtrommel auf dem bestehenden Fahrgestell' },
  keywords: ['Trommeltausch', 'Fahrmischer Trommel ersetzen', 'Mischtrommel neu', 'Fahrmischer Trommel'],
};

/** Modul: Trommeltausch oder neuer Fahrmischer – qualitativ, ohne erfundene Zahlen. */
export const drumCompare = {
  title: 'Trommeltausch oder neuer Fahrmischer?',
  lead: 'Ohne Investition in ein neues Fahrzeug: Sie erneuern nur, was verschlissen ist.',
  rows: [
    { topic: 'Was Sie kaufen', swap: 'Eine neue Trommel', buy: 'Ein ganzes Fahrzeug' },
    { topic: 'Fahrgestell', swap: 'Bleibt – wenn es noch gut ist', buy: 'Wird mit ersetzt' },
    { topic: 'Zeitpunkt', swap: 'Planbar, am liebsten im Winter', buy: 'Abhängig von der Lieferzeit' },
    { topic: 'Wer prüft vorher', swap: 'Wir – und sagen offen, ob es sich lohnt', buy: '–' },
  ],
};

/* ------------------------------------------------------------------ Fahrmischer */
export const fahrmischer: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/fahrmischer',
  crumb: 'Fahrmischer',
  title: 'Fahrmischer-Reparatur',
  description:
    'Fahrmischer-Service und Reparatur: Trommel, Antrieb, Hydraulik, Rinnen und Aufbau für alle gängigen Marken. Trommel-Revision im Winter. Jetzt anfragen.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Fahrmischer',
    h1: 'Fahrmischer-Service, Reparatur und Trommel-Revision',
    lead:
      'Trommel, Antrieb, Hydraulik, Rinnen und Aufbau: Wir warten und reparieren Fahrmischer aller gängigen Marken – und überholen die Trommel, solange der Bau ruht.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Service anfragen'),
  },
  summary:
    '{{brand.full}} wartet und repariert Fahrmischer der Marken {{marks.mixerList}}: Trommel, Antrieb, Hydraulik, Rinnen und Aufbau. Trommel-Revisionen planen wir am liebsten im Winter – in der Werkstatt in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Fuhrpark- und Werkstattleiter in Betonwerken, Bau- und Transportunternehmen.',
    what: 'Service nach Herstellervorgabe, Fehlersuche, Reparatur, Trommel-Revision, Ersatz von Verschleissteilen.',
    deliverables: 'Einen Rapport mit Arbeiten, Teilen und Hinweisen für den nächsten Service.',
  },
  scope: {
    title: 'Leistungsumfang',
    lead: 'Für alle gängigen Marken.',
    items: [
      { title: 'Trommel', text: 'Trommel-Revision: Lager, Dichtungen, Laufring und Rollen; Mischspiralen prüfen und aufbauen.' },
      { title: 'Antrieb', text: 'Trommelgetriebe, Hydraulikmotor und Pumpe – Fehlersuche, Reparatur, Ersatz.' },
      { title: 'Hydraulik', text: 'Schläuche, Leitungen, Ventile und Ölkühler; Lecks finden und beheben.' },
      { title: 'Rinnen und Schurren', text: 'Auslauf- und Verlängerungsrinnen, Schurren und Trichter instand stellen oder ersetzen.' },
      { title: 'Aufbau', text: 'Rahmen und Befestigung, Wassersystem, Leiter, Bedienelemente und Beleuchtung.' },
      { title: 'Service', text: 'Ölwechsel, Schmierung und Kontrolle nach Vorgabe des Herstellers.' },
    ],
  },
  faq: [
    faqBrands,
    faqSpeed,
    {
      q: 'Was gehört zu einer Trommel-Revision?',
      a: 'Wir prüfen Lager, Dichtungen, Laufring und Rollen sowie die Mischspiralen und ersetzen, was verschlissen ist. Den genauen Umfang besprechen wir nach der ersten Kontrolle.',
    },
    {
      q: 'Sind Sie Vertragshändler einer Marke?',
      a: 'Nein. {{marks.mixerNotice}}',
    },
  ],
  related: [
    { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch', text: 'Neue Trommel statt neuer Fahrmischer.' },
    { href: '/fahrzeugtechnik/verschleiss-ersatzteile', label: 'Verschleiss- und Ersatzteile', text: 'Rinnen, Schurren und Spiralschutz für alle gängigen Marken.' },
    ratgeberTeile,
  ],
  service: { name: 'Fahrmischer-Service und Reparatur', serviceType: 'Service und Reparatur von Fahrmischern' },
  keywords: ['Fahrmischer Service', 'Fahrmischer Reparatur', 'Trommel Revision'],
};

/** Modul: Winter-Revision (Anker #winter-revision) und Markenliste. */
export const winterRevision = {
  title: 'Winter-Revision: die Trommel überholen, solange der Bau ruht',
  text: 'Im Winter fährt ein Fahrmischer weniger – der beste Moment, Trommel und Aufbau gründlich zu überholen. Wer früh plant, hat den Fahrmischer im Frühling bereit, wenn die Saison anzieht.',
  items: ['Trommel, Lager und Dichtungen', 'Mischspiralen und Spiralschutz', 'Antrieb und Hydraulik', 'Rinnen, Schurren und Aufbau'],
  cta: 'Winter-Revision planen',
};

/* ------------------------------------------------------------------ Aufbauten */
export const aufbauten: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/aufbauten-reparatur',
  crumb: 'Aufbauten',
  title: 'LKW-Aufbauten reparieren',
  description:
    'Reparatur und Service von LKW-Aufbauten, Mulden, Kippern, Hydraulik und Baustellenfahrzeugen in Tuttwil-Wängi TG. Instandsetzung statt Neuaufbau. Anfragen.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Aufbauten',
    h1: 'Reparatur und Service von LKW-Aufbauten',
    lead:
      'Mulden, Kipper, Hydraulik und Aufbauten von Baustellenfahrzeugen: Wir reparieren und setzen instand, was auf Ihrem Fahrzeug ist. Reparatur und Instandsetzung, keine Neuaufbauten.',
    photo: 'aufbau-reparatur',
    primary: anfrage('Reparatur anfragen'),
  },
  summary:
    '{{brand.full}} repariert LKW-Aufbauten, Mulden und Kipper, Hydraulik und Aufbauten von Baustellenfahrzeugen in der Werkstatt in Tuttwil-Wängi TG. Reparatur und Instandsetzung, keine Neuaufbauten.',
  glance: {
    forWhom: 'Bau- und Transportunternehmen, Kies- und Betonwerke mit Kippern, Mulden und Baustellenfahrzeugen.',
    what: 'Fehlersuche, Reparatur und Instandsetzung von Aufbau, Hydraulik und Stahlbau – keine Neuaufbauten.',
    deliverables: 'Einen Rapport mit Arbeiten und Teilen.',
  },
  scope: {
    title: 'Woran wir arbeiten',
    lead: 'Reparatur und Instandsetzung.',
    items: [
      { title: 'Mulden und Kipper', text: 'Kippbrücken, Mulden, Bordwände und Verschlüsse instand stellen.' },
      { title: 'Hydraulik', text: 'Kippzylinder, Pumpen, Ventile, Schläuche und Leitungen – Lecks finden und beheben.' },
      { title: 'Stahlbau am Aufbau', text: 'Risse, Verformungen und Verschleiss am Aufbau schweissen und verstärken.' },
      { title: 'Baustellenfahrzeuge', text: 'Aufbauten und Anbauteile von Fahrzeugen, die auf der Baustelle arbeiten.' },
    ],
  },
  faq: [
    {
      q: 'Bauen Sie auch neue Aufbauten?',
      a: 'Nein. Wir reparieren und setzen instand – Neuaufbauten gehören nicht zu unserem Angebot.',
    },
    {
      q: 'Welche Aufbauten reparieren Sie?',
      a: 'Mulden, Kipper, Hydraulik und Aufbauten von Baustellenfahrzeugen. Fragen Sie an, wenn Ihr Aufbau nicht dabei ist.',
    },
    faqSpeed,
  ],
  related: [
    { href: '/sonderloesungen/schweiss-stahlbau', label: 'Schweiss- und Stahlbau', text: 'Wenn ein Teil neu angefertigt werden muss.' },
    { href: '/fahrzeugtechnik/fahrmischer', label: 'Fahrmischer', text: 'Service, Reparatur und Trommel-Revision.' },
    ratgeberTeile,
  ],
  service: { name: 'Reparatur von LKW-Aufbauten', serviceType: 'Reparatur und Instandsetzung von Aufbauten' },
  keywords: ['LKW Aufbau Reparatur', 'Mulde Kipper Reparatur'],
};

/* ------------------------------------------------------------------ Verschleiss- und Ersatzteile */
export const verschleissteile: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/verschleiss-ersatzteile',
  crumb: 'Verschleiss- & Ersatzteile',
  title: 'Fahrmischer-Verschleissteile',
  description:
    'Verschleissteile für Fahrmischer: Auslauf- und Verlängerungsrinnen, Schurren, Einfülltrichter und Spiralschutz, passend für gängige Marken. Teil anfragen.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Verschleiss- & Ersatzteile',
    h1: 'Verschleiss- und Ersatzteile für Fahrmischer',
    lead:
      'Rinnen, Schurren, Trichter und Spiralschutz – passend für gängige Marken. Fragen Sie das Teil direkt an; auf Wunsch bauen wir es auch ein.',
    photo: 'verschleissteile-detail',
    primary: { label: 'Zum Katalog', href: '#katalog' },
  },
  summary:
    '{{brand.full}} beschafft Verschleiss- und Ersatzteile für Fahrmischer aller gängigen Marken: Auslauf- und Verlängerungsrinnen, Auslaufschurren, Einfülltrichter und Spiralschutz. Die Passung klären wir je Typ; Preise nennen wir auf Anfrage.',
  glance: {
    forWhom: 'Werkstätten und Fuhrparks mit Fahrmischern.',
    what: 'Verschleiss- und Ersatzteile für alle gängigen Marken, passend zu Ihrem Typ beschafft – auf Wunsch mit Einbau.',
    deliverables: 'Das passende Teil – und auf Wunsch den Einbau mit Rapport.',
  },
  scope: {
    title: 'Was zum Programm gehört',
    lead: 'Gruppiert nach Teileart – die ganze Liste steht unten im Katalog.',
    items: [
      { title: 'Rinnen', text: 'Auslaufrinnen und Verlängerungsrinnen.' },
      { title: 'Schurren und Trichter', text: 'Auslaufschurren und Einfülltrichter.' },
      { title: 'Spiralschutz', text: 'Verschleissschutz für die Kanten der Mischspiralen.' },
      { title: 'Einbau', text: 'Auf Wunsch in unserer Werkstatt – zusammen mit einem Service oder einer Revision.' },
    ],
  },
  faq: [
    {
      q: 'Für welche Marken passen die Teile?',
      a: 'Für gängige Marken wie {{marks.mixerList}}. Die genaue Passung klären wir je Teil und Typ.',
    },
    {
      q: 'Gibt es Preise?',
      a: 'Preise nennen wir auf Anfrage – sie hängen von Ausführung und Typ ab.',
    },
    {
      q: 'Kann ich ein Teil abholen?',
      a: 'Ja, in Tuttwil – am besten vorher kurz anrufen: {{phone.link}}.',
    },
    {
      q: 'Bauen Sie die Teile auch ein?',
      a: 'Ja, in unserer Werkstatt – auf Wunsch zusammen mit einem Service oder einer Revision.',
    },
  ],
  related: [
    { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch', text: 'Wenn nicht nur die Spirale, sondern die ganze Trommel verschlissen ist.' },
    { href: '/fahrzeugtechnik/fahrmischer', label: 'Fahrmischer-Service', text: 'Einbau und Trommel-Revision in der Werkstatt.' },
    ratgeberTeile,
  ],
  service: { name: 'Verschleiss- und Ersatzteile für Fahrmischer', serviceType: 'Verschleissteile für Fahrmischer' },
  keywords: ['Fahrmischer Verschleissteile', 'Fahrmischer Rinne', 'Schurre'],
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const fahrzeugtechnikPages = [trommeltausch, fahrmischer, aufbauten, verschleissteile];

const nav = site.areas.find((a) => a.id === 'fahrzeugtechnik')!.children.map((c) => c.href).join();
if (nav !== fahrzeugtechnikPages.map((p) => p.path).join()) throw new Error('Fahrzeugtechnik: Navigation und Seiten nennen andere Pfade.');
