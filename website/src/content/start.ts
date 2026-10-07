/**
 * Startseite – Texte, in der Reihenfolge der Sektionen (src/pages/index.astro).
 * Werte aus der Konfiguration mit {{…}}.
 */
import type { Faq } from './types';
import { handoverLead, heiriQuote, sharedFaq } from './uebergabe';
import { industries, promiseFaq } from './promises';

export const start = {
  title: 'Krane und Fahrmischer | {{brand.full}}',
  description:
    'Krane und Fahrmischer mit Handschlagqualität: erster Kranservice gratis, INEXXIO 365, Trommeltausch mit Garantie. Aus Tuttwil-Wängi TG, seit 1982.',

  hero: {
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Krane und Fahrmischer mit ==Handschlagqualität==.',
    lead: 'Ihr Bedarf, unsere passende Lösung. Zuverlässig und stets verfügbar.',
    /** Vertrauensleiste – je eine Zahl (oder ein Wort) und was sie sagt. */
    trust: [
      { value: '{{history.founded}}', label: 'Gegründet in Tuttwil-Wängi' },
      { value: 'Alle Marken', label: 'Krane und Fahrmischer' },
      { value: 'Fixpreis', label: 'Vor jeder Arbeit' },
      { value: '50 %', label: 'Zurück, wenn Sie nicht zufrieden sind' },
    ],
  },

  /** Die zwei Einstiege – gleichwertig. Sonderlösungen steht klein darunter. */
  entries: {
    krantechnik: 'Ihr Kran läuft – oder Sie zahlen nicht.',
    fahrzeugtechnik: 'Neue Trommel statt neuer Fahrmischer.',
  } as Record<string, string>,
  more: { label: 'Sonderlösungen', text: 'Konstruktion, Stahlbau und Umbauten – wenn es die Lösung nicht zu kaufen gibt.', href: '/sonderloesungen' },

  summary:
    '{{brand.full}} betreut und baut Krane und Fahrmischer: Kranservice für Industrie, Häfen und Landwirtschaft – der erste Service ist gratis, mit INEXXIO 365 läuft der Kran, oder Sie zahlen nicht –, neue Heukrananlagen, Industriekrane und Bootslifte, Trommeltausch und Service für Fahrmischer aller gängigen Marken und Sonderlösungen. Auf alles, was Sie kaufen, gilt: nicht zufrieden, nur die Hälfte bezahlt. Die Werkstatt steht in Tuttwil-Wängi TG.',

  /** Für wen INEXXIO 365 gemacht ist – eine Zeile unter den Versprechen. */
  industries: { text: industries, link: { href: '/krantechnik/kranservice#inexxio-365', label: 'Zu INEXXIO 365' } },

  areas: {
    h2: 'Drei Bereiche. Ein Ansprechpartner.',
    more: 'Zum Bereich',
  },

  handover: {
    eyebrow: 'Nachfolge geregelt',
    h2: 'Aus HS Steiner wird {{brand.name}}.',
    lead: handoverLead,
    quote: heiriQuote,
  },

  why: {
    eyebrow: 'Vier Belege',
    h2: 'Warum {{brand.name}}',
    items: [
      {
        title: 'Ingenieurwissen statt Rätselraten.',
        text: 'Clemens Fritsche ist Maschinenbauingenieur und hat bei Liebherr Baumaschinen entwickelt. Dieses Wissen steckt in jeder Reparatur, jeder Modernisierung und jeder neuen Anlage.',
      },
      {
        title: 'Eigene Krananlagen seit {{history.cranesSince}}.',
        text: 'Wir planen, bauen und montieren Krananlagen selbst. Dieses Wissen steckt auch in jedem Service.',
      },
      {
        title: 'Kurze Wege, eine Nummer.',
        text: 'Ein Ansprechpartner für Krane, Fahrmischer und Aufbauten – eine Nummer für alles, auch wenn etwas stillsteht.',
      },
      {
        title: 'Sauber dokumentiert.',
        text: 'Jede Arbeit mit Bericht. Das zählt bei Versicherung und Suva – und ab 2027 auch bei Umbauten.',
      },
    ],
    portrait: {
      text: 'Ich führe weiter, was Heiri Steiner in {{history.experienceDative}} aufgebaut hat – und ergänze es dort, wo es Ihnen nützt.',
      link: 'Mehr über Clemens Fritsche und das Unternehmen',
    },
  },


  ratgeber: {
    eyebrow: 'Ratgeber',
    h2: 'Kurz erklärt: Prüfpflicht, Heukran planen, Verschleiss',
    slugs: ['kranpruefung-schweiz', 'heukrananlage-planen', 'verschleissteile-fahrmischer'],
    all: 'Alle Ratgeber-Artikel',
  },

  faq: [
    promiseFaq.inexxio365,
    promiseFaq.erstservice,
    promiseFaq.garantie,
    promiseFaq.binding,
    sharedFaq.whoCares,
    sharedFaq.phone,
    {
      q: 'Welche Marken betreuen Sie?',
      a: 'Bei Fahrmischern: {{marks.mixerList}} – weitere Marken auf Anfrage.',
    },
    promiseFaq.secondOpinion,
    sharedFaq.speed,
  ] satisfies Faq[],

};
