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
    'Kranservice mit Gratis-Erstservice und INEXXIO 365, Trommeltausch für Fahrmischer, Sonderlösungen – mit Zufriedenheitsgarantie. Aus Tuttwil-Wängi TG.',

  hero: {
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Krane und Fahrmischer mit ==Handschlagqualität==.',
    /** Was wir tun, für wen, und warum ohne Risiko – in zwei Sätzen. */
    lead:
      'Wir bauen, warten und reparieren Krane und Fahrmischer aller Marken. Sie erhalten vor jeder Arbeit einen Fixpreis – und einen Ansprechpartner, der erreichbar ist, wenn etwas stillsteht.',
    /** Vertrauensleiste – nur belegbare Tatsachen. Die Versprechen stehen gleich darunter. */
    trust: [
      { value: '{{history.founded}}', label: 'Gegründet in Tuttwil-Wängi' },
      { value: '{{history.cranesSince}}', label: 'Erste eigene Krananlage' },
      { value: 'Alle Marken', label: 'Krane und Fahrmischer' },
      { value: 'Eine Nummer', label: 'Auch wenn etwas stillsteht' },
    ],
  },

  /** Ein Satz je Bereich – das Versprechen, das ihn trägt. Drei gleichwertige Karten. */
  entries: {
    krantechnik: 'Ihr Kran läuft – oder Sie zahlen nicht.',
    fahrzeugtechnik: 'Neue Trommel statt neuer Fahrmischer.',
    sonderloesungen: 'Was es nicht zu kaufen gibt, bauen wir.',
  } as Record<string, string>,

  summary:
    '{{brand.full}} baut, wartet und repariert Krane und Fahrmischer aller Marken: Kranservice für Industrie, Häfen und Landwirtschaft – der erste Service ist gratis, mit INEXXIO 365 läuft der Kran, oder Sie zahlen nicht –, neue Industriekrane, Heukrananlagen und Bootslifte, Trommeltausch und Revision für Fahrmischer sowie Sonderlösungen im Stahlbau. Vor jeder Arbeit gibt es einen Fixpreis, und mit der INEXXIO Zufriedenheitsgarantie zahlen Sie nur die Hälfte, wenn Sie nicht zufrieden sind. Die Werkstatt steht in Tuttwil-Wängi TG.',

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
    eyebrow: 'Warum wir',
    h2: 'Vier Gründe, die Sie nachprüfen können',
    items: [
      {
        title: 'Ingenieurwissen statt Rätselraten.',
        text: 'Clemens Fritsche ist Maschinenbauingenieur und hat bei Liebherr Baumaschinen entwickelt. Wir finden die Ursache – nicht nur das Symptom.',
      },
      {
        title: 'Krane bauen wir seit {{history.cranesSince}} selbst.',
        text: 'Wer Krane plant, baut und montiert, kennt jedes Bauteil. Das macht den Service schneller und die Reparatur gründlicher.',
      },
      {
        title: 'Ein Ansprechpartner, eine Nummer.',
        text: 'Für Krane, Fahrmischer und Sonderlösungen. Steht etwas still, rufen Sie an – und sprechen mit jemandem, der entscheidet.',
      },
      {
        title: 'Jede Arbeit dokumentiert.',
        text: 'Sie erhalten zu jeder Arbeit einen Bericht für das Kranbuch. Das zählt bei Versicherung und Suva.',
      },
    ],
    portrait: {
      text: 'Ich führe weiter, was Heiri Steiner in {{history.experienceDative}} aufgebaut hat – mit demselben Handschlag und neuen Angeboten, die Ihnen das Risiko abnehmen.',
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
