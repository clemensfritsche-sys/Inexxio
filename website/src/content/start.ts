/**
 * Startseite – Texte, in der Reihenfolge der Sektionen (src/pages/index.astro).
 * Werte aus der Konfiguration mit {{…}}.
 */
import type { Faq } from './types';
import { handoverLead, heiriQuote, sharedFaq } from './uebergabe';

export const start = {
  title: 'Krantechnik Schweiz | {{brand.full}}',
  description:
    'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus Tuttwil-Wängi TG: Kranservice, Heukrananlagen, Fahrmischer und Trommeltausch. Seit 1982. Anfragen.',

  hero: {
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus der ==Schweiz==',
    lead:
      'Wir planen, bauen und betreuen Krananlagen, warten und reparieren Fahrmischer und Aufbauten aller gängigen Marken und konstruieren Lösungen, die es nicht von der Stange gibt. Mit Ingenieurwissen und kurzen Wegen.',
    /** Vertrauensleiste – nur belegte Fakten, je eine Zahl (oder ein Wort) und was sie sagt. */
    trust: [
      { value: '{{history.founded}}', label: 'Gegründet in Tuttwil-Wängi' },
      { value: '{{history.cranesSince}}', label: 'Eigene Krananlagen' },
      { value: 'Jahrespreis', label: 'Kranservice auf Wunsch zum Fixpreis' },
      { value: 'Alle Marken', label: 'Fahrmischer und Aufbauten' },
    ],
  },

  summary:
    '{{brand.full}} plant, baut und betreut Krananlagen – mit Kranservice einzeln oder zum Jahrespreis für Industrie, Häfen und Landwirtschaft –, wartet und repariert Fahrmischer und Aufbauten aller gängigen Marken, überholt und tauscht Mischtrommeln und konstruiert Sonderlösungen. Die Werkstatt steht in Tuttwil-Wängi TG.',

  /** Der Kranservice als Teaser – die Paket-Tabelle steht EINMAL, auf /krantechnik/kranservice. */
  plans: {
    eyebrow: 'Erweitertes Angebot',
    h2: 'Kranservice: einzeln oder zum ==Jahrespreis==',
    lead: 'Prüfung, Wartung und Reparatur für Industriekrane, Boots- und Mastkrane und Heukrananlagen – auf Abruf oder in einem von drei Paketen zum festen Preis pro Kran und Jahr.',
    link: 'Die Pakete im Detail',
  },

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
        text: 'Ein Ansprechpartner für Krane, Fahrmischer und Aufbauten – und eine Nummer für alles, auch wenn etwas stillsteht.',
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
    sharedFaq.whoCares,
    sharedFaq.newCranes,
    sharedFaq.phone,
    sharedFaq.contracts,
    {
      q: 'Welche Marken betreuen Sie?',
      a: 'Bei Fahrmischern: {{marks.mixerList}} – weitere Marken auf Anfrage.',
    },
    sharedFaq.speed,
  ] satisfies Faq[],

};
