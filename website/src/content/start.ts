/**
 * Startseite – Texte, in der Reihenfolge der Sektionen (src/pages/index.astro).
 * Werte aus der Konfiguration mit {{…}}.
 */
import type { Faq } from './types';
import { handoverLead, heiriQuote, sharedFaq } from './uebergabe';
import { promiseFaq } from './promises';

export const start = {
  title: '{{brand.name}}: Krane, Fahrmischer, Spezialmaschinen',
  description:
    'Krane nach Mass und INEXXIO 365, Trommeltausch für Fahrmischer, Spezialmaschinen für den Bau – mit Fixpreis und Garantie. Aus Tuttwil-Wängi TG.',

  hero: {
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Krane, Fahrmischer und Spezialmaschinen mit ==Handschlagqualität==.',
    lead: 'Ihr Bedarf, unsere passende Lösung. Zuverlässig und stets verfügbar.',
    /** Vertrauensleiste – nur belegbare Tatsachen. Die Versprechen stehen gleich darunter. */
    trust: [
      { value: '{{history.founded}}', label: 'Gegründet in Tuttwil-Wängi' },
      { value: 'Alle Marken', label: 'Krane und Fahrmischer' },
      { value: 'Fixpreis', label: 'Vor jeder Arbeit' },
      { value: '50 %', label: 'Zurück, wenn Sie nicht zufrieden sind' },
    ],
  },

  /** Ein Satz je Bereich – das Versprechen, das ihn trägt. Drei gleichwertige Karten. */
  entries: {
    krantechnik: 'Ihr Kran läuft – oder Sie zahlen nicht.',
    fahrzeugtechnik: 'Neue Trommel statt neuer Fahrmischer.',
    spezialloesungen: 'Was kein Hersteller liefert, bauen wir.',
  } as Record<string, string>,

  summary:
    '{{brand.full}} arbeitet in drei Bereichen. Krantechnik: Krane nach Mass, Kranservice für alle Marken – der erste Service ist gratis – und INEXXIO 365: Ihr Kran läuft, oder Sie zahlen nicht. Fahrzeugtechnik: Trommeltausch und Verschleissteile für Fahrmischer aller Marken. Speziallösungen: Spezialmaschinen und Anbauten nach Mass für besondere Baustellen. Vor jeder Arbeit gibt es einen Fixpreis, und was Sie kaufen, ist durch die Garantie gedeckt: Nicht zufrieden, zahlen Sie nur die Hälfte. Die Werkstatt steht in Tuttwil-Wängi TG.',

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
    eyebrow: 'Warum INEXXIO',
    h2: 'Vier Gründe, die Sie nachprüfen können',
    items: [
      {
        title: 'Ingenieurwissen statt Rätselraten.',
        text: 'Clemens Fritsche ist Maschinenbauingenieur und hat bei Liebherr Bohrgeräte mitentwickelt. Wir finden die Ursache – nicht nur das Symptom.',
      },
      {
        title: 'Krane bauen wir seit {{history.cranesSince}} selbst.',
        text: 'Wer Krane plant, baut und montiert, kennt jedes Bauteil. Das macht den Service schneller und die Reparatur gründlicher.',
      },
      {
        title: 'Ein Ansprechpartner, eine Nummer.',
        text: 'Für Krane, Fahrmischer und Spezialmaschinen. Steht etwas still, rufen Sie an – und sprechen mit jemandem, der entscheidet.',
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
      a: 'Krane und Fahrmischer aller Marken – bei Fahrmischern etwa {{marks.mixerList}}. Speziallösungen bauen wir für Geräte jeder Marke.',
    },
    promiseFaq.secondOpinion,
    sharedFaq.speed,
  ] satisfies Faq[],

};
