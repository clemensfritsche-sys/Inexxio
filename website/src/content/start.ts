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
    'Hebetechnik mit Handschlagqualität aus Tuttwil-Wängi TG: Kranservice zum Fixpreis, Heukrananlagen, Trommeltausch für Fahrmischer. Seit 1982. Anfragen.',

  hero: {
    eyebrow: 'Tuttwil-Wängi TG · seit {{history.founded}}',
    /** Der Claim (STRATEGIE.md). Weiches Trennzeichen im langen Wort – sonst läuft es auf dem
     *  Telefon bei 40 px Schrift über den Rand. */
    h1: '==Hebetechnik== mit Handschlag\u00ADqualität.',
    lead:
      '{{brand.promise}} Wir betreuen Krane zum festen Preis pro Kran und Jahr – in Industrie, Häfen und Landwirtschaft –, setzen neue Trommeln auf bestehende Fahrmischer und konstruieren, was es nicht zu kaufen gibt.',
    /** Vertrauensleiste – nur belegte Fakten, je eine Zahl (oder ein Wort) und was sie sagt. */
    trust: [
      { value: '{{history.founded}}', label: 'Gegründet in Tuttwil-Wängi' },
      { value: '{{history.cranesSince}}', label: 'Eigene Krananlagen' },
      { value: 'Fixpreis', label: 'Kranservice pro Kran und Jahr' },
      { value: 'Alle Marken', label: 'Fahrmischer und Trommeltausch' },
    ],
  },

  summary:
    '{{brand.full}} ist ein Servicebetrieb mit eigenen Produkten: Kranservice zum festen Preis pro Kran und Jahr für Industrie, Häfen und Landwirtschaft, Heukrananlagen nach Mass, Trommeltausch und Service für Fahrmischer aller gängigen Marken, dazu Sonderlösungen. Die Werkstatt steht in Tuttwil-Wängi TG.',

  /** Die drei Pfeiler (STRATEGIE.md) – was Sie von uns bekommen, in drei Wörtern. */
  pillars: {
    eyebrow: 'Was Sie bekommen',
    h2: 'Passt. Läuft. Ohne ==Investition==.',
    items: [
      { title: 'Passt', text: 'Eine Lösung nach Ihrem Bedarf – nicht nach unserem Katalog. Wir schauen zuerst an, was Sie haben und was Sie brauchen.' },
      { title: 'Läuft', text: 'Zuverlässig und verfügbar: Fristen im Blick, Wartung geplant, und wenn etwas stillsteht, sind wir erreichbar.' },
      { title: 'Ohne Investition', text: 'Service statt Neukauf, modernisieren statt ersetzen: eine neue Steuerung auf dem guten Stahlbau, eine neue Trommel auf dem guten Fahrgestell.' },
    ],
  },

  /** Kernangebot der Krantechnik – Teaser mit den drei Stufen (Seite: /krantechnik/service-vertrag). */
  contract: {
    eyebrow: 'Neu: Service-Vertrag',
    h2: 'Ein Preis pro Kran und Jahr',
    lead: 'Sie wissen im Voraus, was Ihr Kran kostet – wir kümmern uns um Prüfung, Fristen und Kranbuch. Für Industriekrane, Boots- und Mastkrane und Heukrananlagen.',
    link: 'Mehr zum Service-Vertrag',
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


  area: {
    eyebrow: 'Wo wir arbeiten',
    h2: 'Aus Tuttwil-Wängi in die ==ganze Welt==',
    text: 'Zuhause sind wir in {{erp.city}}: Hier steht unsere Werkstatt, und in der Nähe sind wir am schnellsten bei Ihnen. Im Einsatz sind wir {{area.summary}} – für Krananlagen, Service und Sonderlösungen.',
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
      a: 'Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
    },
  ] satisfies Faq[],

};
