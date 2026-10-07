/**
 * Fahrzeugtechnik – Bereichsseite und drei Unterseiten (STRATEGIE.md).
 * Der Trommeltausch ist das erste eigene Produkt – er steht auf der Fahrmischer-Seite neben
 * der Revision (Rückmeldung 07.10.2026: keine eigene Seite, keine Doppelspurigkeit). Service
 * und Teile für alle gängigen Marken – Verschleissteile werden NICHT «ab Lager» beworben (es
 * gibt kein Lager, die Teile sind individuell). Keine Neuaufbauten.
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
  title: 'Fahrmischer und Aufbauten',
  description:
    'Trommeltausch statt neuer Fahrmischer, Trommel-Revision, Service und Reparatur von Fahrmischern und Aufbauten – für alle gängigen Marken. Tuttwil-Wängi TG.',
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
      title: 'Trommel: überholen oder tauschen',
      text: 'Revision, solange die Trommel zu retten ist – sonst eine neue Trommel auf das bewährte Fahrgestell. Am liebsten im Winter, wenn der Bau ruht.',
      links: [
        { href: '/fahrzeugtechnik/fahrmischer#trommel', label: 'Revision oder Tausch' },
        { href: '/fahrzeugtechnik/fahrmischer#winter-revision', label: 'Im Winter planen' },
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
      a: 'Wir setzen eine neue Mischtrommel auf Ihr bestehendes Fahrgestell. Ist das Fahrzeug noch gut, sparen Sie so den neuen Fahrmischer. Mehr dazu unter [Fahrmischer](/fahrzeugtechnik/fahrmischer#trommel).',
    },
    faqBrands,
    faqSpeed,
    {
      q: 'Liefern Sie auch Verschleissteile ohne Montage?',
      a: 'Ja. Rinnen, Schurren, Trichter und Spiralschutz können Sie auch als Teil anfragen.',
    },
  ],
  service: { name: 'Fahrzeugtechnik', serviceType: 'Trommeltausch, Service und Reparatur von Fahrmischern und Aufbauten' },
  keywords: ['Trommeltausch Fahrmischer', 'Fahrmischer Service', 'Fahrmischer Reparatur', 'Trommel Revision'],
};

/* ------------------------------------------------------------------ Fahrmischer */
export const fahrmischer: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/fahrmischer',
  crumb: 'Fahrmischer',
  title: 'Fahrmischer und Mischtrommel',
  description:
    'Fahrmischer-Service, Reparatur, Trommel-Revision und Trommeltausch für alle gängigen Marken – neue Trommel statt neuer Fahrmischer. Jetzt anfragen.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Fahrmischer',
    h1: 'Fahrmischer: Service, Revision und ==Trommeltausch==',
    lead:
      'Trommel, Antrieb, Hydraulik, Rinnen und Aufbau: Wir warten und reparieren Fahrmischer aller gängigen Marken. Ist die Trommel am Ende, das Fahrgestell aber gut, setzen wir eine neue Trommel auf – statt eines neuen Fahrmischers.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Service anfragen'),
  },
  summary:
    '{{brand.full}} wartet und repariert Fahrmischer der Marken {{marks.mixerList}}: Trommel, Antrieb, Hydraulik, Rinnen und Aufbau. Eine verschlissene Trommel überholen wir (Trommel-Revision) oder ersetzen sie durch eine neue auf dem bestehenden Fahrgestell (Trommeltausch). Beides planen wir am liebsten im Winter – in der Werkstatt in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Fuhrpark- und Werkstattleiter in Betonwerken, Bau- und Transportunternehmen.',
    what: 'Service nach Herstellervorgabe, Fehlersuche, Reparatur, Trommel-Revision und Trommeltausch, Ersatz von Verschleissteilen.',
    deliverables: 'Einen Fahrmischer, der wieder läuft – ohne neues Fahrzeug – und einen Rapport mit Arbeiten und Teilen.',
  },
  scope: {
    title: 'Leistungsumfang',
    lead: 'Für alle gängigen Marken.',
    items: [
      { title: 'Trommel', text: 'Revision – Lager, Dichtungen, Laufring, Rollen, Mischspiralen – oder Tausch gegen eine neue Trommel.' },
      { title: 'Antrieb', text: 'Trommelgetriebe, Hydraulikmotor und Pumpe – Fehlersuche, Reparatur, Ersatz.' },
      { title: 'Hydraulik', text: 'Schläuche, Leitungen, Ventile und Ölkühler; Lecks finden und beheben.' },
      { title: 'Rinnen und Schurren', text: 'Auslauf- und Verlängerungsrinnen, Schurren und Trichter instand stellen oder ersetzen.' },
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
      a: 'Das hängt von Trommel, Fahrzeug und Zustand ab. Nach der ersten Kontrolle erhalten Sie eine Offerte.',
    },
    faqSpeed,
    {
      q: 'Sind Sie Vertragshändler einer Marke?',
      a: 'Nein. {{marks.mixerNotice}}',
    },
  ],
  related: [
    { href: '/fahrzeugtechnik/verschleiss-ersatzteile', label: 'Verschleiss- und Ersatzteile', text: 'Rinnen, Schurren und Spiralschutz für alle gängigen Marken.' },
    { href: '/fahrzeugtechnik/aufbauten-reparatur', label: 'Aufbauten', text: 'Mulden, Kipper und Hydraulik.' },
    ratgeberTeile,
  ],
  service: { name: 'Fahrmischer-Service, Trommel-Revision und Trommeltausch', serviceType: 'Service, Reparatur und Trommeltausch von Fahrmischern' },
  keywords: ['Fahrmischer Service', 'Fahrmischer Reparatur', 'Trommel Revision', 'Trommeltausch', 'Fahrmischer Trommel ersetzen'],
};

/**
 * Modul (Anker #trommel): überholen, tauschen oder neu kaufen – drei Wege nebeneinander,
 * qualitativ, ohne erfundene Zahlen. Der Trommeltausch ist das eigene Produkt (`own`).
 */
export const drumOptions = {
  title: 'Die Trommel: überholen oder tauschen?',
  lead: 'Was zu Ihrem Fahrzeug passt, sagen wir nach der ersten Kontrolle – offen, auch wenn ein neuer Fahrmischer die bessere Lösung ist.',
  topics: ['Wann sinnvoll', 'Was wir tun', 'Fahrgestell', 'Zeitpunkt'],
  options: [
    { name: 'Trommel-Revision', values: ['Die Trommel ist verschlissen, aber zu retten.', 'Lager, Dichtungen, Laufring, Rollen und Mischspiralen erneuern.', 'Bleibt.', 'Planbar, am liebsten im Winter.'] },
    { name: 'Trommeltausch', own: true, values: ['Die Trommel ist am Ende, das Fahrgestell gut.', 'Eine neue Trommel auf das bestehende Fahrgestell setzen, Antrieb und Hydraulik anschliessen.', 'Bleibt.', 'Planbar, am liebsten im Winter.'] },
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
    { href: '/fahrzeugtechnik/fahrmischer', label: 'Fahrmischer', text: 'Service, Revision und Trommeltausch.' },
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
    { href: '/fahrzeugtechnik/fahrmischer#trommel', label: 'Trommel-Revision und -tausch', text: 'Wenn nicht nur die Spirale, sondern die ganze Trommel verschlissen ist.' },
    ratgeberTeile,
  ],
  service: { name: 'Verschleiss- und Ersatzteile für Fahrmischer', serviceType: 'Verschleissteile für Fahrmischer' },
  keywords: ['Fahrmischer Verschleissteile', 'Fahrmischer Rinne', 'Schurre'],
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const fahrzeugtechnikPages = [fahrmischer, aufbauten, verschleissteile];

const nav = site.areas.find((a) => a.id === 'fahrzeugtechnik')!.children.map((c) => c.href).join();
if (nav !== fahrzeugtechnikPages.map((p) => p.path).join()) throw new Error('Fahrzeugtechnik: Navigation und Seiten nennen andere Pfade.');
