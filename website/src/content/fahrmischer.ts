/**
 * Fahrmischer – Übersicht, Service & Reparatur, Verschleissteile (Auftrag Kap. 7.3).
 */
import { site } from '../config/site.mjs';
import type { Faq, ServicePage } from './types';

const parent = { name: 'Fahrmischer', path: '/fahrmischer' };
const anfrage = (label: string) => ({ label, href: '#anfrage' });

const faqBrands: Faq = {
  q: 'Welche Marken betreuen Sie?',
  a: '{{marks.mixerList}} – und weitere auf Anfrage. {{marks.mixerNotice}} {{marks.mixerReview}}',
};
const faqSpeed: Faq = {
  q: 'Wie schnell ist mein Fahrmischer wieder auf der Strasse?',
  a: 'Das hängt vom Schaden und von den Teilen ab. Viele Verschleiss- und Ersatzteile haben wir an Lager. [[PLATZHALTER: typische Standzeit bei Service und Reparatur]]',
};

/* ------------------------------------------------------------------ Übersicht */
export const fahrmischer: ServicePage & { services: { href: string; label: string; text: string }[] } = {
  path: '/fahrmischer',
  crumb: 'Fahrmischer',
  title: 'Fahrmischer-Service',
  description:
    'Service, Reparatur und Trommel-Revision für Fahrmischer der Marken Intermix, Putzmeister, Cifa, Stetter, Liebherr und weitere. Teile ab Lager. Anfragen.',
  og: 'fahrmischer',
  hero: {
    eyebrow: 'Fahrmischer',
    h1: 'Fahrmischer-Service für alle gängigen Marken',
    lead:
      'Damit Ihr Fahrmischer schnell wieder fährt: Service, Reparatur und Trommel-Revision an einem Ort – mit Verschleissteilen ab Lager.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Service anfragen'),
  },
  summary:
    '{{brand.full}} wartet und repariert Fahrmischer der Marken {{marks.mixerList}} in der Werkstatt in Tuttwil-Wängi TG. Dazu kommen Trommel-Revisionen – besonders im Winter – und Verschleissteile wie Rinnen, Schurren und Spiralschutz.',
  glance: {
    forWhom: 'Betonwerke, Bau- und Transportunternehmen mit Fahrmischern.',
    what: 'Service, Reparatur, Trommel-Revision, Hydraulik, Rinnen und Aufbau – dazu Verschleissteile.',
    speed: 'Viele Teile ab Lager. [[PLATZHALTER: typische Standzeit bei Service und Reparatur]]',
    deliverables: 'Rapport mit den ausgeführten Arbeiten und verbauten Teilen.',
  },
  services: [
    ...site.nav[1].children!.map((c) => ({ href: c.href, label: c.label, text: c.text })),
    { href: '/fahrmischer/service-reparatur#winter-revision', label: 'Winter-Revision', text: 'Trommel und Aufbau überholen, solange der Bau ruht' },
  ],
  scope: {
    title: 'Woran wir arbeiten',
    lead: 'Am ganzen Aufbau – vom Einfülltrichter bis zur Rinne. [[PRÜFEN: fachlich – Leistungsumfang]]',
    items: [
      { title: 'Trommel und Spiralen', text: 'Revision der Trommel, Mischspiralen prüfen und instand stellen.' },
      { title: 'Trommelantrieb', text: 'Getriebe, Hydraulikmotor und Pumpe – damit die Trommel zuverlässig dreht.' },
      { title: 'Hydraulik', text: 'Schläuche, Leitungen und Ventile prüfen, abdichten und ersetzen.' },
      { title: 'Rinnen und Schurren', text: 'Reparieren oder ersetzen – Verschleissteile ab Lager.' },
      { title: 'Aufbau', text: 'Rahmen, Wassersystem, Leiter und Bedienung am Aufbau.' },
    ],
  },
  steps: [
    { title: 'Anfrage', text: 'Sie nennen Marke, Typ und das Anliegen – per Formular oder am Telefon.' },
    { title: 'Termin', text: 'Wir planen den Werkstatttermin so, dass der Fahrmischer möglichst kurz fehlt.' },
    { title: 'Arbeit in der Werkstatt', text: 'Wir warten oder reparieren und ersetzen verschlissene Teile.' },
    { title: 'Rapport', text: 'Sie erhalten einen Rapport mit Arbeiten und Teilen.' },
  ],
  faq: [
    faqBrands,
    faqSpeed,
    {
      q: 'Wann ist der beste Zeitpunkt für eine Trommel-Revision?',
      a: 'Im Winter, wenn der Bau ruht und der Fahrmischer ohnehin weniger fährt. Dann fehlt er nicht, wenn es auf der Baustelle eilt.',
    },
    {
      q: 'Liefern Sie auch Verschleissteile ohne Montage?',
      a: 'Ja. Rinnen, Schurren, Trichter und Spiralschutz können Sie auch als Teil anfragen. [[PRÜFEN: Teileverkauf ohne Montage]]',
    },
  ],
  cta: {
    title: 'Fahrmischer-Service anfragen',
    lead: 'Nennen Sie Marke, Typ und das Anliegen. Wir melden uns innert {{promises.responseTime}}.',
    kind: 'fahrmischer',
  },
  related: [
    { href: '/krane', label: 'Krane', text: 'Prüfung, Wartung, Reparatur und Modernisierung – alle Marken.' },
    { href: '/einsatzgebiet', label: 'Einsatzgebiet', text: 'Rund eine Stunde ab Tuttwil-Wängi.' },
    { href: '/ratgeber/verschleissteile-fahrmischer', label: 'Verschleissteile am Fahrmischer', text: 'Wann Rinne, Schurre und Spiralschutz ersetzen?', kind: 'ratgeber' },
  ],
  service: { name: 'Fahrmischer-Service', serviceType: 'Service und Reparatur von Fahrmischern' },
};

/* ------------------------------------------------------------------ Service & Reparatur */
export const serviceReparatur: ServicePage = {
  path: '/fahrmischer/service-reparatur',
  crumb: 'Service & Reparatur',
  title: 'Fahrmischer-Reparatur',
  description:
    'Fahrmischer-Reparatur und Service: Trommel, Antrieb, Hydraulik, Rinnen und Aufbau – für alle gängigen Marken. Trommel-Revision im Winter. Jetzt anfragen.',
  og: 'fahrmischer',
  parent,
  hero: {
    eyebrow: 'Fahrmischer · Service & Reparatur',
    h1: 'Fahrmischer-Reparatur und Trommel-Revision',
    lead:
      'Trommel, Antrieb, Hydraulik, Rinnen und Aufbau: Wir warten und reparieren Fahrmischer aller gängigen Marken – und überholen die Trommel, solange der Bau ruht.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Reparatur anfragen'),
  },
  summary:
    '{{brand.full}} wartet und repariert Fahrmischer der Marken {{marks.mixerList}}: Trommel, Antrieb, Hydraulik, Rinnen und Aufbau. Trommel-Revisionen planen wir am liebsten im Winter.',
  glance: {
    forWhom: 'Fuhrpark- und Werkstattleiter in Betonwerken, Bau- und Transportunternehmen.',
    what: 'Service nach Herstellervorgabe, Fehlersuche, Reparatur, Trommel-Revision, Ersatz von Verschleissteilen.',
    speed: 'Viele Teile ab Lager. [[PLATZHALTER: typische Standzeit bei Service und Reparatur]]',
    deliverables: 'Rapport mit Arbeiten, Teilen und Hinweisen für den nächsten Service.',
  },
  scope: {
    title: 'Leistungsumfang',
    lead: 'Für alle gängigen Marken. [[PRÜFEN: fachlich – Leistungsumfang]]',
    items: [
      { title: 'Trommel', text: 'Trommel-Revision: Lager, Dichtungen, Laufring und Rollen; Mischspiralen prüfen und aufbauen.' },
      { title: 'Antrieb', text: 'Trommelgetriebe, Hydraulikmotor und Pumpe – Fehlersuche, Reparatur, Ersatz.' },
      { title: 'Hydraulik', text: 'Schläuche, Leitungen, Ventile und Ölkühler; Lecks finden und beheben.' },
      { title: 'Rinnen und Schurren', text: 'Auslauf- und Verlängerungsrinnen, Schurren und Trichter instand stellen oder ersetzen.' },
      { title: 'Aufbau', text: 'Rahmen und Befestigung, Wassersystem, Leiter, Bedienelemente und Beleuchtung.' },
      { title: 'Service', text: 'Ölwechsel, Schmierung und Kontrolle nach Vorgabe des Herstellers.' },
    ],
  },
  steps: [
    { title: 'Anfrage', text: 'Sie nennen Marke, Typ und Anliegen – ein Foto vom Typenschild hilft.' },
    { title: 'Termin', text: 'Wir planen den Werkstatttermin und halten die Teile bereit.' },
    { title: 'Arbeit in der Werkstatt', text: 'Wir reparieren, ersetzen Verschleissteile und prüfen die Funktion.' },
    { title: 'Rapport', text: 'Sie erhalten einen Rapport mit Arbeiten und Teilen.' },
  ],
  faq: [
    faqBrands,
    faqSpeed,
    {
      q: 'Was gehört zu einer Trommel-Revision?',
      a: 'Wir prüfen Lager, Dichtungen, Laufring und Rollen sowie die Mischspiralen und ersetzen, was verschlissen ist. Den genauen Umfang besprechen wir nach der ersten Kontrolle. [[PRÜFEN: fachlich – Umfang Trommel-Revision]]',
    },
    {
      q: 'Kommen Sie auch auf die Baustelle oder ins Werk?',
      a: '[[PLATZHALTER: Einsätze vor Ort bei Fahrmischern – ja oder nein, in welchem Umfang]]',
    },
    {
      q: 'Sind Sie Vertragshändler einer Marke?',
      a: 'Nein. {{marks.mixerNotice}} {{marks.mixerReview}}',
    },
  ],
  cta: {
    title: 'Reparatur oder Service anfragen',
    lead: 'Nennen Sie Marke, Typ und Anliegen. Wir melden uns innert {{promises.responseTime}}.',
    kind: 'fahrmischer',
  },
  related: [
    { href: '/fahrmischer/verschleissteile', label: 'Verschleissteile', text: 'Rinnen, Schurren und Spiralschutz ab Lager.' },
    { href: '/krane/reparatur', label: 'Kranreparatur', text: 'Auch für Krane: Reparatur und Pikett.' },
    { href: '/ratgeber/verschleissteile-fahrmischer', label: 'Verschleissteile am Fahrmischer', text: 'Woran Sie erkennen, wann ein Teil ersetzt werden muss.', kind: 'ratgeber' },
  ],
  service: { name: 'Fahrmischer-Reparatur und Trommel-Revision', serviceType: 'Reparatur von Fahrmischern' },
};

/** Modul: Winter-Revision (Anker #winter-revision) und Markenliste. */
export const winterRevision = {
  title: 'Winter-Revision: die Trommel überholen, solange der Bau ruht',
  text: 'Im Winter fährt ein Fahrmischer weniger – der beste Moment, Trommel und Aufbau gründlich zu überholen. Wer früh plant, hat den Fahrmischer im Frühling bereit, wenn die Saison anzieht.',
  items: ['Trommel, Lager und Dichtungen', 'Mischspiralen und Spiralschutz', 'Antrieb und Hydraulik', 'Rinnen, Schurren und Aufbau'],
  cta: 'Winter-Revision planen',
};

/* ------------------------------------------------------------------ Verschleissteile */
export const verschleissteile: ServicePage = {
  path: '/fahrmischer/verschleissteile',
  crumb: 'Verschleissteile',
  title: 'Fahrmischer-Verschleissteile',
  description:
    'Verschleissteile für Fahrmischer: Auslauf- und Verlängerungsrinnen, Schurren, Einfülltrichter und Spiralschutz – passend für gängige Marken. Teil anfragen.',
  og: 'fahrmischer',
  parent,
  hero: {
    eyebrow: 'Fahrmischer · Verschleissteile',
    h1: 'Verschleissteile für Fahrmischer',
    lead:
      'Rinnen, Schurren, Trichter und Spiralschutz – passend für gängige Marken. Fragen Sie das Teil direkt an; auf Wunsch bauen wir es auch ein.',
    photo: 'verschleissteile-detail',
    primary: { label: 'Zum Katalog', href: '#katalog' },
  },
  summary:
    '{{brand.full}} führt Verschleissteile für Fahrmischer: Auslauf- und Verlängerungsrinnen, Auslaufschurren, Einfülltrichter und Spiralschutz. Das Programm ist im Aufbau; passende Typen klären wir je Anfrage.',
  glance: {
    forWhom: 'Werkstätten und Fuhrparks mit Fahrmischern.',
    what: 'Verschleissteile ab Lager oder auf Bestellung – auf Wunsch mit Einbau.',
    speed: '[[PLATZHALTER: Lieferzeit für Verschleissteile]]',
    deliverables: 'Das passende Teil – und auf Wunsch den Einbau mit Rapport.',
  },
  scope: {
    title: 'Was zum Programm gehört',
    lead: 'Gruppiert nach Teileart – die ganze Liste steht unten im Katalog.',
    items: [
      { title: 'Rinnen', text: 'Auslaufrinnen und Verlängerungsrinnen.' },
      { title: 'Schurren und Trichter', text: 'Auslaufschurren und Einfülltrichter.' },
      { title: 'Spiralschutz', text: 'Verschleissschutz für die Kanten der Mischspiralen.' },
    ],
  },
  steps: [
    { title: 'Teil anfragen', text: 'Sie wählen das Teil und nennen Marke und Typ des Fahrmischers.' },
    { title: 'Passung klären', text: 'Wir prüfen, welche Ausführung passt – ein Foto vom Typenschild hilft.' },
    { title: 'Liefern oder einbauen', text: 'Sie holen das Teil ab, wir schicken es – oder wir bauen es ein.' },
    { title: 'Bestätigung', text: 'Sie erhalten Lieferschein bzw. Rapport mit dem verbauten Teil.' },
  ],
  faq: [
    {
      q: 'Für welche Marken passen die Teile?',
      a: 'Für gängige Marken wie {{marks.mixerList}}. Die genaue Passung klären wir je Teil und Typ. [[PRÜFEN: passende Marken und Typen je Teil]]',
    },
    {
      q: 'Gibt es Preise?',
      a: 'Preise nennen wir auf Anfrage – sie hängen von Ausführung und Typ ab. [[PLATZHALTER: Preise für Verschleissteile]]',
    },
    {
      q: 'Kann ich ein Teil abholen?',
      a: 'Ja, in Tuttwil während der Öffnungszeiten: {{hours.text}}. [[PRÜFEN: Abholung und Versand]]',
    },
    {
      q: 'Bauen Sie die Teile auch ein?',
      a: 'Ja, in unserer Werkstatt – auf Wunsch zusammen mit einem Service oder einer Revision.',
    },
  ],
  cta: {
    title: 'Teil anfragen',
    lead: 'Welches Teil, für welchen Fahrmischer? Wir melden uns innert {{promises.responseTime}}.',
    kind: 'teile',
    messageLabel: 'Welches Teil, für welchen Fahrmischer (Marke, Typ)?',
  },
  related: [
    { href: '/fahrmischer/service-reparatur', label: 'Service und Reparatur', text: 'Einbau und Trommel-Revision in der Werkstatt.' },
    { href: '/fahrmischer', label: 'Fahrmischer', text: 'Alle Leistungen für Fahrmischer im Überblick.' },
    { href: '/ratgeber/verschleissteile-fahrmischer', label: 'Verschleissteile am Fahrmischer', text: 'Wann Rinne, Schurre und Spiralschutz ersetzen?', kind: 'ratgeber' },
  ],
  service: { name: 'Verschleissteile für Fahrmischer', serviceType: 'Verschleissteile für Fahrmischer' },
};
