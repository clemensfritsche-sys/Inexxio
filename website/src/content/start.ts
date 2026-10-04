/**
 * Startseite – Texte. Reihenfolge der Sektionen ist verbindlich (Auftrag Kap. 7.3):
 * Hero → drei Bereiche → Übergabe → Warum → Ausgewählte Arbeiten (abgeschaltet) →
 * Einsatzgebiet → Ratgeber → Fragen → Anfrage.
 * Werte aus der Konfiguration mit {{…}}, offene Punkte mit [[…]].
 */
import type { Faq } from './types';
import { heiriQuote, news, stays } from './uebergabe';

export const start = {
  title: 'Krantechnik Ostschweiz | {{brand.full}}',
  description:
    'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus Tuttwil-Wängi TG: Heukrananlagen, Kranservice, Fahrmischer-Reparatur. Seit 1982. Jetzt Anfrage stellen.',

  hero: {
    index: '01',
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    h1: 'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus der ==Ostschweiz==',
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
    '{{brand.full}} plant und baut Krananlagen, wartet und repariert Fahrmischer und Aufbauten aller Marken und konstruiert Sonderlösungen. Werkstatt und Ersatzteillager stehen in Tuttwil-Wängi TG; im Einsatz sind wir in der {{area.summary}}.',

  areas: {
    h2: 'Drei Bereiche. Ein Ansprechpartner.',
    more: 'Zum Bereich',
  },

  handover: {
    eyebrow: 'Nachfolge geregelt',
    h2: 'Aus HS Steiner wird {{brand.name}}.',
    lead:
      'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Gleiches Team, gleiche Telefonnummer, gleicher Standort – und neue Möglichkeiten. [[PRÜFEN: Aussage «gleiches Team» und Wortlaut freigeben]]',
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
        text: 'Clemens Fritsche hat bei Liebherr Baumaschinen entwickelt. Wir verstehen, wie eine Maschine gebaut ist – nicht nur, wo sie klemmt.',
      },
      {
        title: 'Eigene Krananlagen seit {{history.cranesSince}}.',
        text: 'Wir planen, bauen und montieren Krananlagen selbst. Dieses Wissen steckt auch in jedem Service.',
      },
      {
        title: 'Alle Marken, kurze Wege.',
        text: 'Ein Ansprechpartner für Krane, Fahrmischer und Aufbauten. Ersatzteillager vor Ort, Notfallnummer für Stillstände.',
      },
      {
        title: 'Sauber dokumentiert.',
        text: 'Jede Arbeit mit Bericht. Das zählt bei Versicherung und Suva – und ab 2027 auch bei Umbauten. [[PRÜFEN: fachlich – Hinweis auf die EU-Maschinenverordnung]]',
      },
    ],
    portrait: {
      text: 'Ich führe weiter, was Heiri Steiner in {{history.experienceDative}} aufgebaut hat – und ergänze es dort, wo es Ihnen nützt. [[PRÜFEN: von Clemens freigeben]]',
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
    eyebrow: 'Einsatzgebiet',
    h2: 'Aus Tuttwil-Wängi in die ganze Ostschweiz',
    text: 'Im Einsatz sind wir im Thurgau, im Kanton St. Gallen, im Raum Winterthur und Zürich und in Schaffhausen. {{area.review}}',
    abroad: '{{area.abroad}} {{area.abroadReview}}',
    link: 'Mehr zum Einsatzgebiet',
  },

  ratgeber: {
    eyebrow: 'Ratgeber',
    h2: 'Kurz erklärt: Prüfpflicht, Heukran planen, Verschleiss',
    slugs: ['kranpruefung-schweiz', 'heukrananlage-planen', 'verschleissteile-fahrmischer'],
    all: 'Alle Ratgeber-Artikel',
  },

  faq: [
    {
      q: 'Wer betreut meine HS-Krananlage in Zukunft?',
      a: 'Wir. Service und Ersatzteile führen wir weiter, mit demselben Wissen und denselben Teilen ab Lager.',
    },
    {
      q: 'Bauen Sie weiterhin neue Krananlagen?',
      a: 'Ja. Heukrananlagen und Industriekrane planen und bauen wir nach Mass.',
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
      a: 'Krane aller Hersteller. Bei Fahrmischern: {{marks.mixerList}}.',
    },
    {
      q: 'Wie schnell sind Sie bei einem Stillstand vor Ort?',
      a: '{{promises.reactionTime}} Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
    },
    {
      q: 'Führen Sie noch Garten- und Motorgeräte oder Reifen?',
      a: 'Nein. Wir konzentrieren uns auf Krantechnik, Fahrzeugtechnik und Sonderlösungen. Was nicht mehr zu unserem Angebot gehört, steht auf der Seite [Aus HS Steiner wird {{brand.name}}](/uebergabe#nicht-mehr-im-angebot).',
    },
  ] satisfies Faq[],

  cta: {
    h2: 'Was steht bei Ihnen an?',
    lead: 'Beschreiben Sie Ihr Anliegen in zwei Minuten. Wir melden uns innert {{promises.responseTime}}.',
  },
};
