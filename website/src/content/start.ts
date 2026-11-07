/**
 * Startseite – Texte, in der Reihenfolge der Sektionen (src/pages/index.astro).
 * Werte aus der Konfiguration mit {{…}}. Wortlaut der abgenommenen Vorlage «Startseite v4»
 * (docs/design-system/reference/mockups/).
 */
import type { Faq } from './types';
import { handoverLead } from './uebergabe';
import { promiseFaq } from './promises';

export const start = {
  title: '{{brand.name}}: Krane, Fahrmischer, Spezialmaschinen',
  description:
    'Krane nach Mass und INEXXIO 365, Trommeltausch für Fahrmischer, Spezialmaschinen für den Bau – mit Zufriedenheitsgarantie. Aus {{address.home}}.',

  /** Bühne: Video (oder Foto), wenig Text. */
  hero: {
    eyebrow: 'Seit {{history.founded}} · {{address.town}}',
    h1: 'Krane, Fahrmischer und Spezialmaschinen.',
    sub: 'Mit Zufriedenheitsgarantie.',
    photo: 'heukran-einsatz',
  },

  /** Ein Satz je Bereich – auf seiner Karte. */
  entries: {
    krantechnik: 'Krane nach Mass, auch um Ecken und über Steigungen. Kranservice und Heukrananlagen.',
    fahrzeugtechnik: 'Neue Trommel statt neuer Fahrmischer.',
    spezialloesungen: 'Was kein Hersteller liefert, bauen wir.',
  } as Record<string, string>,

  areas: {
    h2: 'Drei Bereiche. Ein Ansprechpartner.',
    /** Reihenfolge der Karten (die Navigation beginnt mit Speziallösungen). */
    order: ['krantechnik', 'fahrzeugtechnik', 'spezialloesungen'],
    /** Knopf in der Karte (schmal). */
    go: {
      krantechnik: 'Zur Krantechnik',
      fahrzeugtechnik: 'Zur Fahrzeugtechnik',
      spezialloesungen: 'Zu den Speziallösungen',
    } as Record<string, string>,
  },

  /** Speziallösungen – die Felder kommen aus content/spezialloesungen.ts (scope). */
  special: {
    h2: 'Ihre Aufgabe. Unsere Lösung.',
    lead: 'Wenn kein Hersteller liefert, was Ihre Arbeit verlangt, bauen wir es – als Einzelstück oder Kleinserie.',
    cta: { label: 'Aufgabe schildern', href: '#anfrage' },
  },

  summary:
    '{{brand.name}} arbeitet in drei Bereichen. Krantechnik: Krane nach Mass, Kranservice und Heukrananlagen. Fahrzeugtechnik: Trommeltausch und Verschleissteile für Fahrmischer. Speziallösungen: Spezialmaschinen und Anbauten nach Mass. Zwei Garantien gelten für alles: Die Zufriedenheitsgarantie – nicht zufrieden, übernehmen wir 50 % – und INEXXIO 365 – Ihre Maschine ist einsatzbereit, Ausfälle übernehmen wir. Die erste Inspektion ist gratis. Der Standort ist in {{address.home}}.',

  why: {
    h2: 'Entwicklung, Produktion und Service aus einer Hand.',
    /** Grosse Zahlen: «Seit» darüber, Einheit daneben, ein Satz darunter. */
    figures: [
      { pre: 'Seit', figure: '{{history.founded}}', text: 'In {{address.town}} gegründet.' },
      { pre: 'Seit', figure: '{{history.cranesSince}}', text: 'bauen wir Krane selbst. Darum kennen wir jedes Bauteil.' },
      { figure: '1', unit: 'Ansprechpartner', text: 'für Krane, Fahrmischer und Spezialmaschinen.' },
      { figure: '50', unit: '%', text: 'übernehmen wir, wenn Sie mit dem Ergebnis nicht zufrieden sind – die Zufriedenheitsgarantie.' },
    ] as { pre?: string; figure: string; unit?: string; text: string }[],
    quote: 'Ich führe weiter, was Heiri Steiner in {{history.experienceDative}} aufgebaut hat – und ergänze es dort, wo es Ihnen nützt.',
    caption: '{{people.owner.name}}, Maschinenbauingenieur – Erfahrung aus der Entwicklung von Liebherr-Bohrgeräten.',
    link: 'Mehr über uns',
    href: '/ueber-uns',
  },

  handover: {
    h2: 'Aus HS Steiner wird {{brand.name}}.',
    lead: handoverLead,
    short: 'Meine Kunden sind bei ihm in guten Händen.',
    /** Collage: Standort (gross), Porträt, ein HS-Kran. */
    photos: ['clemens-heiri-quer', 'portraet-clemens', 'heukran-einsatz'],
    link: 'Die ganze Geschichte',
    href: '/ueber-uns#uebergabe',
  },

  ratgeber: {
    h2: 'Ratgeber',
    lead: 'Kurz erklärt: Prüfpflicht, Heukran planen, Verschleiss.',
    /** Karussell: beginnt beim zweiten Artikel. Satz je Karte – kürzer als «kurz» im Artikel. */
    items: [
      { slug: 'kranpruefung-schweiz', photo: 'pruefung-hallenkran', text: 'Zu jedem Kran gehört ein Kranbuch. Alle Krane werden regelmässig von Kranfachleuten überprüft – Fahrzeug- und Turmdrehkrane zusätzlich von einem Kranexperten.' },
      { slug: 'heukrananlage-planen', photo: 'heukran-einsatz', text: 'Welche Bauform passt, entscheiden das Gebäude und die Arbeit. Wer im Winter plant, hat die Anlage vor dem ersten Schnitt in Betrieb.' },
      { slug: 'verschleissteile-fahrmischer', photo: 'fahrmischer-werkstatt', text: 'Rinne, Schurre, Trichter und Mischspiralen verschleissen mit jeder Fuhre. Ersetzen Sie ein Teil, bevor das Blech durch ist.' },
    ],
    all: 'Alle Ratgeber-Artikel',
  },

  faqHead: {
    h2: 'Häufige Fragen',
    lead: 'Was vor einer Anfrage am häufigsten gefragt wird.',
  },
  /** Kompakt: die Fragen, die vor einer Anfrage wirklich auftauchen – je mit ihrem Bild. */
  faq: [
    promiseFaq.garantie,
    promiseFaq.inexxio365,
    {
      q: 'Unsere Maschine steht still – was tun?',
      a: 'Rufen Sie direkt an: {{phone.link}}. Wir kümmern uns darum.',
    },
    {
      q: 'Ich bin Kunde von HS Steiner – was ändert sich?',
      a: 'Das Bewährte bleibt: derselbe Standort und dieselbe Telefonnummer. Ihre HS-Krananlage betreuen wir ohne Unterbruch weiter – ergänzt um Ingenieurwissen, wo es Ihnen nützt.',
    },
  ] satisfies Faq[],
};
