/**
 * Startseite – Texte. Reihenfolge der Sektionen ist verbindlich (Auftrag Kap. 7.3):
 * Hero → drei Bereiche → Übergabe → Warum → Ausgewählte Arbeiten (abgeschaltet) →
 * Wo wir arbeiten → Ratgeber → Fragen → Anfrage.
 * Werte aus der Konfiguration mit {{…}}, offene Punkte mit [[…]].
 */
import type { Faq } from './types';
import { handoverLead, heiriQuote, news, sharedFaq, stays } from './uebergabe';

export const start = {
  title: 'Krantechnik Schweiz | {{brand.full}}',
  description:
    'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus Tuttwil-Wängi TG: Heukrananlagen, Kranservice, Fahrmischer-Reparatur. Seit 1982. Jetzt Anfrage stellen.',

  hero: {
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus der ==Schweiz==',
    lead:
      'Wir planen und bauen Krananlagen, warten und reparieren Fahrmischer und Aufbauten aller Marken und konstruieren Lösungen, die es nicht von der Stange gibt. Mit Ingenieurwissen und kurzen Wegen.',
    /** Vertrauensleiste – nur belegte Fakten. */
    trust: [
      'Seit {{history.founded}}',
      'Eigene Krananlagen seit {{history.cranesSince}}',
      'Alle Marken im Service',
      'Ersatzteillager vor Ort',
    ],
  },

  summary:
    '{{brand.full}} plant und baut Krananlagen, wartet und repariert Fahrmischer und Aufbauten aller Marken und konstruiert Sonderlösungen. Werkstatt und Ersatzteillager stehen in Tuttwil-Wängi TG.',

  areas: {
    h2: 'Drei Bereiche. Ein Ansprechpartner.',
    more: 'Zum Bereich',
  },

  handover: {
    eyebrow: 'Nachfolge geregelt',
    h2: 'Aus HS Steiner wird {{brand.name}}.',
    lead: handoverLead,
    quote: heiriQuote,
    stays,
    news,
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
        title: 'Alle Marken, kurze Wege.',
        text: 'Ein Ansprechpartner für Krane, Fahrmischer und Aufbauten. Ersatzteillager vor Ort und eine Nummer für alles – auch wenn etwas stillsteht.',
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

  /** Ausgewählte Arbeiten – abgeschaltet (features.projects), bis echte Projekte mit Fotos vorliegen. */
  projects: {
    eyebrow: 'Ausgewählte Arbeiten',
    h2: 'Drei Arbeiten aus der Werkstatt',
    items: [
      { area: 'Krantechnik', title: '[[PLATZHALTER: Projekt 1 – Titel]]', text: '[[PLATZHALTER: ein Satz Ergebnis, nur mit Freigabe des Kunden]]', photo: 'heukran-einsatz' },
      { area: 'Fahrzeugtechnik', title: '[[PLATZHALTER: Projekt 2 – Titel]]', text: '[[PLATZHALTER: ein Satz Ergebnis, nur mit Freigabe des Kunden]]', photo: 'fahrmischer-werkstatt' },
      { area: 'Sonderlösungen', title: '[[PLATZHALTER: Projekt 3 – Titel]]', text: '[[PLATZHALTER: ein Satz Ergebnis, nur mit Freigabe des Kunden]]', photo: 'arbeit-werkstatt' },
    ],
  },

  area: {
    eyebrow: 'Wo wir arbeiten',
    h2: 'Aus Tuttwil-Wängi in die ==ganze Welt==',
    text: 'Zuhause sind wir in Tuttwil-Wängi: Hier stehen Werkstatt und Ersatzteillager, und in der Nähe sind wir am schnellsten bei Ihnen. Im Einsatz sind wir {{area.summary}} – für Krananlagen, Service und Sonderlösungen.',
    note: 'Nicht jeder Einsatz ist innert Stunden möglich, aber jeder lässt sich planen. Fragen Sie an.',
    link: 'Mehr über uns',
  },

  ratgeber: {
    eyebrow: 'Ratgeber',
    h2: 'Kurz erklärt: Prüfpflicht, Heukran planen, Verschleiss',
    slugs: ['kranpruefung-schweiz', 'heukrananlage-planen', 'verschleissteile-fahrmischer'],
    all: 'Alle Ratgeber-Artikel',
  },

  faq: [
    sharedFaq.whoCares,
    sharedFaq.newCranes,
    sharedFaq.phone,
    sharedFaq.contracts,
    {
      q: 'Welche Marken betreuen Sie?',
      a: 'Bei Fahrmischern: {{marks.mixerList}} – weitere Marken auf Anfrage.',
    },
    {
      q: 'Wie schnell sind Sie bei einem Stillstand vor Ort?',
      a: '{{promises.reactionTime}} Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
    },
  ] satisfies Faq[],

  cta: {
    h2: 'Wie können wir Ihnen helfen?',
    lead: 'Beschreiben Sie Ihr Anliegen in zwei Minuten. Wir melden uns innert {{promises.responseTime}}.',
  },
};
