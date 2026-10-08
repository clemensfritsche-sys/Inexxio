/**
 * Fahrzeugtechnik – Bereichsseite und zwei Unterseiten: Trommeltausch (das stärkste Angebot,
 * zuerst) und Verschleissteile. Reparatur und Aufbauten stehen zurückhaltend als Abschnitt
 * auf der Bereichsseite (`repair`, Anker #reparatur). Verschleissteile werden NICHT «ab Lager»
 * beworben – sie werden bestellt und schnell beschafft. Hier gilt Versprechen ② (Kaufen mit
 * Garantie); der Gratis-Erstservice gilt nur für Krane.
 */
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

/* ------------------------------------------------------------------ Bereich */
export const fahrzeugtechnik: AreaPage = {
  id: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik',
  title: 'Fahrzeugtechnik: Fahrmischer',
  description:
    'Neue Trommel statt neuer Fahrmischer – für alle Marken, zum Fixpreis, mit Garantie. Dazu Verschleissteile, schnell beschafft. Aus Tuttwil-Wängi TG.',
  hero: {
    eyebrow: 'Fahrzeugtechnik',
    h1: 'Neue Trommel statt neuer ==Fahrmischer==',
    lead:
      'Ist die Trommel am Ende, das Fahrgestell aber gut, setzen wir eine neue Trommel auf – für alle Marken, zum Fixpreis. Nicht zufrieden? Sie zahlen nur die Hälfte. Die Verschleissteile beschaffen wir schnell.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Trommeltausch anfragen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle (Trommeltausch) – für Fahrmischer aller Marken, zum Fixpreis und mit Garantie: Nicht zufrieden, zahlen Sie nur die Hälfte. Verschleissteile wie Rinnen, Schurren, Trichter und Spiralschutz beschaffen wir auf Bestellung für alle Marken. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  steps: [
    { title: 'Anfrage', text: 'Sie nennen Marke, Typ und Anliegen – per Formular oder am Telefon.' },
    { title: 'Kontrolle', text: 'Wir prüfen Trommel und Fahrgestell und nennen einen Fixpreis.' },
    { title: 'Umsetzung', text: 'Neue Trommel aufsetzen, Antrieb und Hydraulik anschliessen, Teile ersetzen.' },
    { title: 'Bericht', text: 'Sie erhalten einen Rapport mit Arbeiten und Teilen.' },
  ],
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
  promises: ['garantie'],
  service: { name: 'Fahrzeugtechnik', serviceType: 'Trommeltausch und Verschleissteile für Fahrmischer' },
  keywords: ['Trommeltausch Fahrmischer', 'Fahrmischer Trommel', 'Fahrmischer Verschleissteile', 'Fahrmischer Reparatur'],
};

/** Reparatur und Aufbauten – zurückhaltend, ein Abschnitt auf der Bereichsseite (#reparatur). */
export const repair = {
  title: 'Reparatur und Aufbauten',
  text: 'Was auf der Baustelle zu Bruch geht, setzen wir instand – an Fahrmischern und an Aufbauten von Baufahrzeugen.',
  items: ['Mulden, Kipper, Bordwände', 'Hydraulik: Zylinder, Pumpen, Ventile, Leitungen', 'Antrieb und Getriebe der Trommel', 'Rahmen und Befestigung'],
};

/* ------------------------------------------------------------------ Trommeltausch */
export const trommeltausch: SubPage = {
  area: 'fahrzeugtechnik',
  path: '/fahrzeugtechnik/trommeltausch',
  crumb: 'Trommeltausch',
  title: 'Trommeltausch für Fahrmischer',
  description:
    'Neue Trommel auf das bestehende Fahrgestell statt neuer Fahrmischer – für alle Marken, zum Fixpreis. Nicht zufrieden, zahlen Sie nur die Hälfte.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Trommeltausch',
    h1: 'Neue Trommel statt neuer ==Fahrmischer==',
    lead:
      'Das Fahrgestell bleibt, die neue Trommel kommt drauf – für Fahrmischer aller Marken. Sie erhalten vorher einen Fixpreis. Nicht zufrieden? Sie zahlen nur die Hälfte.',
    photo: 'fahrmischer-werkstatt',
    primary: anfrage('Trommeltausch anfragen'),
  },
  summary:
    '{{brand.full}} setzt neue Mischtrommeln auf bestehende Fahrgestelle – für Fahrmischer aller Marken, darunter {{marks.mixerList}}. Fixpreis vor jeder Arbeit, und mit der Garantie zahlen Sie nur die Hälfte, wenn Sie nicht zufrieden sind. Ist die Trommel noch zu retten, überholen wir sie (Trommel-Revision). Am besten im Winter – in der Werkstatt in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Fuhrpark- und Werkstattleiter in Betonwerken, Bau- und Transportunternehmen mit eigenen Fahrmischern.',
    what: 'Trommel und Fahrgestell prüfen, neue Trommel aufsetzen, Antrieb und Hydraulik anschliessen, in Betrieb nehmen.',
    deliverables: 'Einen Fahrmischer, der wieder läuft – ohne neues Fahrzeug – und einen Rapport mit Arbeiten und Teilen.',
  },
  promises: ['garantie'],
  scope: {
    title: 'Was zum Trommeltausch gehört',
    lead: 'Für alle Marken.',
    items: [
      { title: 'Kontrolle vorab', text: 'Trommel, Fahrgestell, Antrieb und Aufbau – Sie erfahren offen, ob sich der Tausch lohnt.' },
      { title: 'Neue Trommel', text: 'Passend zu Fahrgestell und Einsatz, aufgesetzt in unserer Werkstatt.' },
      { title: 'Antrieb', text: 'Trommelgetriebe, Hydraulikmotor und Pumpe anschliessen – prüfen und, wo nötig, ersetzen.' },
      { title: 'Hydraulik', text: 'Schläuche, Leitungen, Ventile und Ölkühler.' },
      { title: 'Aufbau', text: 'Rahmen und Befestigung, Wassersystem, Leiter, Bedienelemente und Beleuchtung.' },
      { title: 'Inbetriebnahme', text: 'Probelauf, Rapport, und der Fahrmischer ist wieder im Einsatz.' },
    ],
  },
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
      a: 'Das hängt von Trommel, Fahrzeug und Zustand ab. Nach der Kontrolle erhalten Sie einen Fixpreis.',
    },
    promiseFaq.garantie,
    faqBrands,
    faqSpeed,
    promiseFaq.secondOpinion,
  ],
  related: [
    { href: '/fahrzeugtechnik/verschleissteile', label: 'Verschleissteile', text: 'Für alle Marken, schnell beschafft.' },
    ratgeberTeile,
  ],
  service: { name: 'Trommeltausch für Fahrmischer', serviceType: 'Trommeltausch und Trommel-Revision für Fahrmischer' },
  keywords: ['Trommeltausch', 'Fahrmischer Trommel', 'Mischtrommel', 'Trommel Revision', 'Fahrmischer Reparatur'],
};

/**
 * Modul (Anker #trommel): tauschen, überholen oder neu kaufen – drei Wege nebeneinander,
 * qualitativ, ohne erfundene Zahlen. Der Trommeltausch ist das eigene Produkt (`own`).
 */
export const drumOptions = {
  title: 'Tauschen, überholen – oder doch neu?',
  lead: 'Was zu Ihrem Fahrzeug passt, sagen wir nach der Kontrolle – offen, auch wenn ein neuer Fahrmischer die bessere Lösung ist.',
  topics: ['Wann sinnvoll', 'Was wir tun', 'Fahrgestell', 'Zeitpunkt'],
  options: [
    { name: 'Trommeltausch', own: true, values: ['Die Trommel ist am Ende, das Fahrgestell gut.', 'Eine neue Trommel auf das bestehende Fahrgestell setzen, Antrieb und Hydraulik anschliessen.', 'Bleibt.', 'Planbar, am liebsten im Winter.'] },
    { name: 'Trommel-Revision', values: ['Die Trommel ist verschlissen, aber zu retten.', 'Lager, Dichtungen, Laufring, Rollen und Mischspiralen erneuern.', 'Bleibt.', 'Planbar, am liebsten im Winter.'] },
    { name: 'Neuer Fahrmischer', values: ['Auch das Fahrgestell ist am Ende.', 'Nicht unser Angebot – wir sagen es Ihnen, wenn es so weit ist.', 'Wird mit ersetzt.', 'Abhängig von der Lieferzeit.'] },
  ],
};

/** Modul: Winter (Anker #winter) und Markenliste. */
export const winterSlot = {
  title: 'Im Winter, wenn der Bau ruht',
  text: 'Im Winter fährt ein Fahrmischer weniger – der beste Moment für den Trommeltausch. Wer früh plant, hat den Fahrmischer im Frühling bereit, wenn die Saison anzieht.',
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
    'Rinnen, Schurren, Trichter und Spiralschutz für Fahrmischer aller Marken – auf Bestellung, schnell beschafft. Mit oder ohne Einbau. Anfragen.',
  hero: {
    eyebrow: 'Fahrzeugtechnik · Verschleissteile',
    h1: 'Verschleissteile für alle Marken – schnell ==beschafft==',
    lead:
      'Rinnen, Schurren, Trichter und Spiralschutz für Fahrmischer aller Marken. Sie bestellen, wir beschaffen schnell – mit oder ohne Einbau.',
    photo: 'teil-auslaufrinne',
    primary: anfrage('Teil anfragen'),
  },
  summary:
    '{{brand.full}} beschafft Verschleissteile für Fahrmischer aller Marken auf Bestellung: Auslauf- und Verlängerungsrinnen, Einfülltrichter, Auslaufschurren und Spiralschutz – als Teil oder mit Einbau in der Werkstatt in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Fuhrpark- und Werkstattleiter in Betonwerken, Bau- und Transportunternehmen mit eigenen Fahrmischern.',
    what: 'Teile nach Marke und Typ bestellen und schnell beschaffen – auf Wunsch mit Einbau.',
    deliverables: 'Das passende Teil, rasch bei Ihnen oder eingebaut, mit einem Fixpreis vorab.',
  },
  scope: {
    title: 'Welche Teile wir beschaffen',
    lead: 'Für alle gängigen Marken – und weitere auf Anfrage.',
    items: [
      { title: 'Rinnen', text: 'Auslauf- und Verlängerungsrinnen.' },
      { title: 'Trichter und Schurren', text: 'Einfülltrichter und Auslaufschurren.' },
      { title: 'Spiralschutz', text: 'Schutz der Mischspiralen gegen Abrieb.' },
      { title: 'Einbau', text: 'Auf Wunsch in unserer Werkstatt, zusammen mit Service oder Trommeltausch.' },
    ],
  },
  faq: [
    {
      q: 'Wie bestelle ich ein Teil?',
      a: 'Nennen Sie uns Marke, Typ und das Teil – am einfachsten mit einem Foto. Wir beschaffen es schnell und nennen vorher den Preis.',
    },
    {
      q: 'Kann ich ein Teil abholen?',
      a: 'Ja, in Tuttwil – am besten vorher kurz anrufen: {{phone.link}}.',
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

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const fahrzeugtechnikPages = [trommeltausch, verschleissteile];
