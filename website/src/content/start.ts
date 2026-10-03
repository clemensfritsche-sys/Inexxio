/**
 * Startseite – Texte. Reihenfolge der Sektionen ist verbindlich (Auftrag Kap. 7.2).
 * Werte aus der Konfiguration mit {{…}}, offene Punkte mit [[…]].
 */
import type { Entry, Faq } from './types';
import { heiriQuote, news, stays } from './uebergabe';

export const start = {
  title: 'Kranservice Ostschweiz | {{brand.full}}',
  description:
    'Kranprüfung, Wartung und Reparatur für Krananlagen und Fahrmischer aller Marken in der Ostschweiz. Seit 1982 in Tuttwil-Wängi TG. Jetzt Service anfragen.',

  hero: {
    index: '01',
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Kranservice und Fahrmischer-Reparatur für die ==Ostschweiz==',
    lead:
      'Prüfung, Wartung, Reparatur und Modernisierung für Krananlagen und Fahrmischer aller Marken. Aus der Region, mit Bericht zu jeder Arbeit. [[PRÜFEN: Ersatz für den Claim «Schnell vor Ort. Sauber dokumentiert.» freigeben]]',
    note: 'Notfall? Pikett: {{pikett.link}} {{pikett.review}}',
    /** Nur belegte Fakten. */
    stats: [
      { value: '{{history.founded}}', label: 'gegründet in Tuttwil-Wängi' },
      { value: 'Alle', label: 'Marken – Krane und Fahrmischer' },
      { value: 'rund 1 h', label: 'Einsatzradius ab Tuttwil [[PRÜFEN: Einsatzradius bestätigen]]' },
    ],
  },

  summary:
    '{{brand.full}} prüft, wartet, repariert und modernisiert Krananlagen und Fahrmischer aller Marken. Werkstatt und Ersatzteillager stehen in Tuttwil-Wängi TG; unterwegs sind wir rund eine Stunde im Umkreis – Thurgau, St. Gallen, Raum Winterthur/Zürich und Schaffhausen.',

  entries: [
    { title: 'Kran prüfen lassen', text: 'Jährliche Kontrolle mit Prüfbericht', href: '/krane/pruefung-wartung', icon: 'calendar-check' },
    { title: 'Kran steht still', text: 'Reparatur und Pikett', href: '/krane/reparatur', icon: 'wrench' },
    { title: 'Fahrmischer-Service', text: 'Alle Marken, Teile ab Lager', href: '/fahrmischer/service-reparatur', icon: 'truck' },
    { title: 'Verschleissteile', text: 'Rinnen, Schurren, Spiralschutz', href: '/fahrmischer/verschleissteile', icon: 'package' },
  ] satisfies Entry[],


  handover: {
    eyebrow: 'Nachfolge geregelt',
    h2: 'Aus HS Steiner wird {{brand.name}}.',
    lead:
      'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Gleiches Team, gleiche Telefonnummer, gleicher Standort – und mehr Service. [[PRÜFEN: Aussage «gleiches Team» und Wortlaut freigeben]]',
    quote: heiriQuote,
    stays,
    news,
  },

  pillars: {
    h2: 'Zwei Bereiche. Volle Konzentration.',
    krane: {
      title: 'Krane',
      text: 'Brücken-, Hänge- und Drehkrane aller Marken sowie HS-Krananlagen: Prüfung, Wartung, Reparatur und Modernisierung.',
      photo: 'reparatur-vor-ort',
      more: 'Alle Kranleistungen',
    },
    fahrmischer: {
      title: 'Fahrmischer',
      text: 'Service, Reparatur und Trommel-Revision für Intermix, Putzmeister, Cifa, Stetter, Liebherr und weitere Marken. Verschleissteile ab Lager.',
      photo: 'fahrmischer-werkstatt',
      more: 'Alles zu Fahrmischern',
    },
  },

  abo: {
    eyebrow: 'Service-Abo und digitales Kranbuch',
    h2: 'Ein Abo. Ein Preis. Kein Termin vergessen.',
    lead:
      'Wir übernehmen Prüfung und Wartung Ihrer Krane zum Fixpreis pro Jahr. Jede Kontrolle landet im digitalen Kranbuch – abrufbar per QR-Code direkt am Kran. [[PRÜFEN: Abo und Kranbuch ab Start verfügbar oder «in Vorbereitung»?]]',
    cta: 'Abo-Stufen ansehen',
  },

  why: {
    eyebrow: 'Vier Belege',
    h2: 'Warum {{brand.name}}',
    items: [
      {
        title: 'Ingenieurwissen statt Rätselraten.',
        text: 'Clemens Fritsche hat bei Liebherr Baumaschinen entwickelt. Wir verstehen, wie ein Kran oder Fahrmischer gebaut ist – nicht nur, wo er klemmt.',
      },
      {
        title: 'Alle Marken.',
        text: 'HS-Kran, Hallenkran eines anderen Herstellers oder Fahrmischer: ein Ansprechpartner für Ihren ganzen Bestand.',
      },
      {
        title: 'Kurze Wege.',
        text: 'Rund eine Stunde Einsatzradius ab Tuttwil-Wängi, Ersatzteillager vor Ort, Pikett für Notfälle.',
      },
      {
        title: 'Sauber dokumentiert.',
        text: 'Jede Arbeit mit Bericht, jede Prüfung im Kranbuch. Das zählt bei Versicherung und Suva – und ab 2027 auch bei Umbauten. [[PRÜFEN: fachlich – Hinweis auf die EU-Maschinenverordnung]]',
      },
    ],
    portrait: {
      text: 'Ich führe weiter, was Heiri Steiner in {{history.experienceDative}} aufgebaut hat – und ergänze es dort, wo es Ihnen nützt. [[PRÜFEN: von Clemens freigeben]]',
      link: 'Mehr über Clemens Fritsche und das Unternehmen',
    },
  },

  ratgeber: {
    eyebrow: 'Ratgeber',
    h2: 'Kurz erklärt: Prüfpflicht, Saison-Check, Verschleiss',
    slugs: ['kranpruefung-schweiz', 'heukran-saison-check', 'verschleissteile-fahrmischer'],
    all: 'Alle Ratgeber-Artikel',
  },

  faq: [
    {
      q: 'Wer betreut meinen HS-Kran in Zukunft?',
      a: 'Wir. Service und Ersatzteile für HS-Krananlagen führen wir weiter, mit demselben Wissen und denselben Teilen ab Lager.',
    },
    {
      q: 'Bleibt die Telefonnummer gleich?',
      a: 'Ja, {{phone.display}}. Auch die bisherigen E-Mail-Adressen erreichen uns weiterhin. [[PRÜFEN: Weiterleitung der E-Mail-Adressen bestätigen]]',
    },
    {
      q: 'Gelten bestehende Verträge weiter?',
      a: 'Ja. Das Unternehmen bleibt dasselbe, nur der Name ändert sich. [[PRÜFEN: rechtlich – Aussage zu laufenden Verträgen]]',
    },
    {
      q: 'Welche Marken betreuen Sie?',
      a: 'Krane aller Hersteller – vom Brücken- oder Hängekran bis zur HS-Krananlage. Bei Fahrmischern: {{marks.mixerList}}.',
    },
    {
      q: 'Wie schnell sind Sie vor Ort?',
      a: '{{promises.reactionTime}} Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
    },
  ] satisfies Faq[],

  cta: {
    h2: 'Was steht bei Ihnen an?',
    lead: 'Beschreiben Sie Ihr Anliegen in zwei Minuten. Wir melden uns innert {{promises.responseTime}}.',
  },
};
