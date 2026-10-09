/**
 * Startseite – Texte, in der Reihenfolge der Sektionen (src/pages/index.astro).
 * Werte aus der Konfiguration mit {{…}}.
 */
import type { Faq } from './types';
import { handoverLead, heiriQuote } from './uebergabe';
import { promiseFaq } from './promises';

export const start = {
  title: '{{brand.name}}: Krane, Fahrmischer, Spezialmaschinen',
  description:
    'Krane nach Mass und INEXXIO 365, Trommeltausch für Fahrmischer, Spezialmaschinen für den Bau – mit Fixpreis und Garantie. Aus Tuttwil-Wängi TG.',

  hero: {
    eyebrow: 'Krane · Fahrmischer · Spezialmaschinen · seit {{history.founded}}',
    h1: 'Krane, Fahrmischer und Spezialmaschinen mit ==Zufriedenheitsgarantie==.',
    subtitle: 'Ihr Problem. Unsere Lösung.',
    lead: 'Sie sagen uns, was nicht läuft – wir bauen, warten und reparieren, bis es läuft. Mit Fixpreis vor jeder Arbeit.',
    handover: {
      label: 'Nachfolge geregelt',
      title: 'Aus HS Steiner wird {{brand.name}}.',
      text: 'Gleiche Werkstatt, gleiche Nummer – gleicher Handschlag.',
      href: '#uebergabe',
    },
  },

  /** Ein Satz je Bereich – das Versprechen, das ihn trägt. Drei gleichwertige Karten. */
  entries: {
    krantechnik: 'Ihr Kran ist einsatzbereit. Ausfälle übernehmen wir.',
    fahrzeugtechnik: 'Neue Trommel statt neuer Fahrmischer.',
    spezialloesungen: 'Was kein Hersteller liefert, bauen wir.',
  } as Record<string, string>,

  summary:
    '{{brand.full}} arbeitet in drei Bereichen. Krantechnik: Krane nach Mass, Kranservice und Heukrananlagen. Fahrzeugtechnik: Trommeltausch und Verschleissteile für Fahrmischer. Speziallösungen: Spezialmaschinen und Anbauten nach Mass. Zwei Garantien gelten für alles: Die Zufriedenheitsgarantie – nicht zufrieden, übernehmen wir 50 % – und INEXXIO 365 – Ihre Maschine ist einsatzbereit, Ausfälle übernehmen wir. Die erste Inspektion ist gratis, vor jeder Arbeit gibt es einen Fixpreis. Die Werkstatt steht in Tuttwil-Wängi TG.',

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
    h2: 'Entwicklung, Produktion und Service aus einer Hand.',
    items: [
      { icon: 'lightbulb', title: 'Entwicklung mit Know-how.', text: 'Maschinenbauingenieur – mit Erfahrung aus der Entwicklung von Liebherr-Bohrgeräten und mit vernetzten Maschinen (IoT).' },
      { icon: 'wrench', title: 'Selbst gebaut, darum gut betreut.', text: 'Krane bauen wir seit {{history.cranesSince}} selbst. Wir kennen jedes Bauteil.' },
      { icon: 'phone', title: 'Ein Ansprechpartner für alles.', text: 'Für Krane, Fahrmischer und Spezialmaschinen.' },
      { icon: 'clipboard-check', title: 'Jeder Einsatz dokumentiert.', text: 'Mit Protokoll – für Versicherung, Suva und den nächsten Service.' },
    ],
    quote: 'Ich führe weiter, was Heiri Steiner in {{history.experienceDative}} aufgebaut hat – und ergänze es dort, wo es Ihnen nützt.',
    link: 'Mehr über uns',
  },

  ratgeber: {
    eyebrow: 'Ratgeber',
    h2: 'Kurz erklärt: Prüfpflicht, Heukran planen, Verschleiss',
    slugs: ['kranpruefung-schweiz', 'heukrananlage-planen', 'verschleissteile-fahrmischer'],
    all: 'Alle Ratgeber-Artikel',
  },

  /** Kompakt: die Fragen, die vor einer Anfrage wirklich auftauchen. */
  faq: [
    promiseFaq.price,
    promiseFaq.garantie,
    promiseFaq.inexxio365,
    {
      q: 'Unsere Maschine steht still – was tun?',
      a: 'Rufen Sie direkt an: {{phone.link}}. Wir kümmern uns darum.',
    },
    {
      q: 'Ich bin Kunde von HS Steiner – was ändert sich?',
      a: 'Das Bewährte bleibt: dieselbe Werkstatt und dieselbe Telefonnummer. Ihre HS-Krananlage betreuen wir ohne Unterbruch weiter – ergänzt um Ingenieurwissen, wo es Ihnen nützt.',
    },
  ] satisfies Faq[],

};
