// @ts-check
/**
 * ►►► DIE EINE QUELLE der Website. ◄◄◄
 *
 * Alles, was mehr als einmal vorkommt – Name, Telefon, Adresse, Öffnungszeiten, die drei
 * Bereiche mit ihren Unterseiten, Schalter –, steht hier und nur hier. Header, Footer,
 * Kontaktseite, JSON-LD, llms.txt, Sitemap, robots.txt, die E-Mail-Vorlagen des Formulars
 * und Kopf/Fuss des Konto- und ERP-Bereichs lesen ausschliesslich daraus (die beiden
 * letzten über `scripts/export-contact.mjs`).
 *
 * Ein Namenswechsel (z. B. «HS Steiner – Teil von INEXXIO») ist eine Änderung in
 * `brand` – Texte setzen den Namen über `{{brand.name}}` bzw. `{{brand.full}}` ein.
 *
 * Bewusst .mjs statt .ts: die Node-Skripte (Prüfung, Export für Formular und Konto-Kopf)
 * lesen dieselbe Datei ohne Übersetzungsschritt.
 */

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * ►►► Telefon und E-Mail kommen aus dem ERP (Testnotiz #1094). ◄◄◄ `scripts/erp-contact.mjs`
 * holt beim Build die Angaben des Betreibers (`GET /api/v1/public/contact?country=`) und
 * legt sie hier ab; zur Laufzeit tauscht `src/scripts/contact.ts` sie gegen die des
 * Besucherlandes. Ohne ERP (lokal, CI-Prüfung) gelten die Vorgaben unten.
 * @type {{ phone?: string | null, phone_e164?: string | null, email?: string | null }}
 */
const erp = (() => {
  const file = resolve(process.cwd(), 'src/config/erp-contact.json');
  try {
    return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : {};
  } catch {
    return {};
  }
})();

/** Werdegang von Clemens Fritsche – als Liste (Über uns) und als Satz (JSON-LD, llms.txt). */
const ownerCareer = [
  'Maschinenbauingenieur',
  'Entwicklung von Bohrgeräten bei Liebherr',
  'Produkt- und Plattformmanagement im IoT-Umfeld',
  'Weiterbildung in Betriebswirtschaft',
];

/**
 * @typedef {{ label: string, href: string, text: string, photo: string }} SubPage
 * @typedef {{
 *   id: 'krantechnik' | 'fahrzeugtechnik' | 'spezialloesungen',
 *   label: string, href: string, overview: string, ddText?: string, text: string, photo: string,
 *   ogTitle: string,
 *   industries: string,
 *   children: SubPage[],
 * }} Area
 */

/**
 * ►►► Die drei Bereiche – gleichwertig: gleich viel Platz, gleiche Gliederung, gleich starke
 * Texte. ◄◄◄ Kopf, Mobil-Menü, Fuss, Bereichskarten, JSON-LD (hasOfferCatalog) und llms.txt
 * entstehen daraus. Je Untermenü-Text höchstens eine Zeile (#1203). `industries` ist die
 * EINE Branchen-Zeile des Bereichs: auf der Startseite stehen alle drei, auf der
 * Bereichsseite nur ihre eigene.
 * @type {Area[]}
 */
const areas = [
  {
    id: 'krantechnik',
    label: 'Krantechnik',
    href: '/krantechnik',
    overview: 'Alle Leistungen Krantechnik',
    ddText: 'Übersicht des Bereichs',
    text: 'Krane nach Mass, Kranservice und Heukrananlagen.',
    photo: 'heukran-einsatz',
    ogTitle: 'Ihr Kran ist einsatzbereit. Ausfälle übernehmen wir.',
    industries: 'Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau, Betonwerke, Häfen und Clubs.',
    children: [
      { label: 'Krane nach Mass', href: '/krantechnik/krane-nach-mass', text: 'Für Ihre Halle, Ihren Hafen, Ihren Ablauf', photo: 'reparatur-vor-ort' },
      { label: 'Kranservice', href: '/krantechnik/kranservice', text: 'Inspektion, Modernisierung, INEXXIO 365', photo: 'pruefung-hallenkran' },
      { label: 'Heukrananlagen', href: '/krantechnik/heukrananlagen', text: 'Bestehende Anlagen betreuen, neue planen', photo: 'heukran-einsatz' },
    ],
  },
  {
    id: 'fahrzeugtechnik',
    label: 'Fahrzeugtechnik',
    href: '/fahrzeugtechnik',
    overview: 'Alle Leistungen Fahrzeugtechnik',
    ddText: 'Übersicht des Bereichs',
    text: 'Trommeltausch und Verschleissteile für Fahrmischer.',
    photo: 'fahrmischer-werkstatt',
    ogTitle: 'Neue Trommel statt neuer Fahrmischer.',
    industries: 'Betonwerke, Bau- und Transportunternehmen mit eigenen Fahrmischern.',
    children: [
      { label: 'Trommeltausch', href: '/fahrzeugtechnik/trommeltausch', text: 'Neue Trommel auf das bestehende Fahrgestell', photo: 'fahrmischer-werkstatt' },
      { label: 'Verschleissteile', href: '/fahrzeugtechnik/verschleissteile', text: 'Auf Bestellung, schnell beschafft', photo: 'teil-auslaufrinne' },
    ],
  },
  {
    id: 'spezialloesungen',
    label: 'Speziallösungen',
    href: '/spezialloesungen',
    overview: 'Speziallösungen',
    text: 'Spezialmaschinen, Anbauten und Vorrichtungen nach Mass – für Krane, Fahrzeuge und Baumaschinen.',
    photo: 'arbeit-werkstatt',
    ogTitle: 'Ihre Aufgabe. Unsere Maschine.',
    industries: 'Bauunternehmen und Spezialtiefbau mit eigener Geräteflotte, Vermieter und Händler von Baugeräten – und alle, deren Aufgabe kein Hersteller löst.',
    children: [],
  },
];

export const site = {
  brand: {
    name: 'INEXXIO',
    formerly: 'ehemals HS Steiner',
    /** Erste Nennung auf jeder Seite. */
    full: '{{brand.name}} ({{brand.formerly}})',
    /** Logo: das gestapelte Zeichen mit «ehemals HS Steiner» (public/logo/, Lockup.astro). */
    legalName: 'INEXXIO AG',
    formerLegalName: 'HS Steiner Fahrzeug- und Kranbau GmbH',
    alternateNames: ['HS Steiner', 'HS Steiner Fahrzeug- und Kranbau GmbH', 'HS Krananlagen'],
    /** Abgrenzung für Suchmaschinen und KI-Assistenten. */
    notToConfuse: 'Nicht zu verwechseln mit inexio (Telekommunikation, Deutschland).',
    /** Wer wir sind, in einem Satz – JSON-LD (description) und llms.txt lesen ihn. */
    summary:
      'Krantechnik, Fahrzeugtechnik und Speziallösungen aus Tuttwil-Wängi TG: Krane nach Mass, Kranservice mit INEXXIO 365 und Heukrananlagen, Trommeltausch und Verschleissteile für Fahrmischer, Spezialmaschinen nach Mass für die Baustelle. Seit {{history.founded}}.',
    /** Claim – OG-Bild und llms.txt. */
    claim: 'Krane, Fahrmischer und Spezialmaschinen mit Zufriedenheitsgarantie. Ihr Problem. Unsere Lösung.',
  },

  history: {
    founded: 1982,
    foundedText: 'Heiri Steiner baut die Reparaturwerkstätte in Tuttwil-Wängi und macht sich selbstständig.',
    cranesSince: 1985,
    cranesText: 'Die erste eigene Krananlage entsteht – für Landwirtschaft und Industrie, vorwiegend Sonderanfertigungen.',
    gmbhYear: 1993,
    /** Formulierung statt einer Zahl, die jedes Jahr nachgeführt werden müsste. */
    experience: 'über 40 Jahre',
    /** Dieselbe Angabe im Dativ («nach über 40 Jahren»). */
    experienceDative: 'über 40 Jahren',
    markets: 'in der Schweiz, in Deutschland, Österreich und im Südtirol',
  },

  people: {
    owner: {
      name: 'Clemens Fritsche',
      role: 'Geschäftsführer',
      career: ownerCareer,
      short: `${ownerCareer.join(', ')}.`,
    },
    founder: {
      name: 'Heiri Steiner',
      role: 'Gründer',
      /** Nur solange `features.heiriAdvisory` an ist – danach verschwindet der Satz überall. */
      advisory:
        'Heiri Steiner bleibt in der Übergangszeit beratend dabei.',
    },
  },

  /** Vorgabe – das ERP gewinnt (siehe oben). Eine Nummer für alles, auch bei Stillstand. */
  phone: erp.phone && erp.phone_e164
    ? { display: erp.phone, intl: erp.phone_e164, e164: erp.phone_e164 }
    : { display: '052 378 22 47', intl: '+41 52 378 22 47', e164: '+41523782247' },
  email: {
    /** Aus dem ERP; ohne Angabe dort bleibt die bisherige erreichbar. */
    primary: erp.email || '',
    legacy: 'fahrzeug-kranbau@hs-steiner.ch',
  },

  address: {
    street: 'Waldweg 1',
    zip: '9546',
    city: 'Tuttwil',
    municipality: 'Wängi',
    canton: 'TG',
    country: 'CH',
    countryName: 'Schweiz',
  },
  geo: { lat: 47.4836, lng: 8.9357 },

  /**
   * Wo wir arbeiten: zuhause in Tuttwil-Wängi, im Einsatz überall (Rückmeldung 04.10.2026:
   * «uns nicht limitieren, ich will ja wachsen»). Keine Regionenliste, keine Grenzen.
   */
  area: {
    home: 'Tuttwil-Wängi TG',
    summary: 'in der Schweiz, in Deutschland und Österreich – und darüber hinaus, wo Sie uns brauchen',
  },

  promises: {
    /** «Wir melden uns innert …» */
    responseTime: 'kurzer Zeit',
  },

  marks: {
    mixers: ['Intermix', 'Putzmeister', 'Cifa', 'Stetter', 'Liebherr', 'Belmix', 'Peter'],
    mixerNotice:
      'Markennamen gehören ihren Inhabern. Wir sind unabhängig und kein Vertragshändler.',
  },

  /** Elemente, die sich per Schalter abschalten lassen. */
  features: {
    /** Heiri Steiner bleibt in der Übergangszeit beratend dabei – alles dazu hängt hier. */
    heiriAdvisory: true,
    /** Ohne echten Inhalt aus: */
    team: false,
  },

  /** Saison-Hinweise: von/bis als MM-TT, über den Jahreswechsel erlaubt. */
  seasons: [
    {
      id: 'winter-revision',
      from: '11-01',
      to: '02-28',
      text: 'Trommeltausch im Winter: Der Fahrmischer ist im Frühling bereit, wenn die Saison anzieht.',
      href: '/fahrzeugtechnik/trommeltausch#winter',
      label: 'Termin planen',
      pages: ['/', '/fahrzeugtechnik', '/fahrzeugtechnik/trommeltausch', '/service'],
    },
    {
      id: 'heukran-planung',
      from: '01-01',
      to: '04-30',
      text: 'Saison-Check für Ihre Heukrananlage: jetzt planen, damit sie beim ersten Schnitt läuft.',
      href: '/krantechnik/heukrananlagen#saison-check',
      label: 'Saison-Check planen',
      pages: ['/', '/krantechnik', '/krantechnik/heukrananlagen'],
    },
  ],

  areas,

  /** Service: Einstieg nach Anliegen und Notfall auf EINER Seite – im Kopf ein einfacher Link. */
  service: {
    label: 'Service',
    href: '/service',
    overview: 'Service und Notfall',
    text: 'Einstieg nach Anliegen – wenn etwas still steht, geprüft oder repariert werden muss.',
    photo: 'servicefahrzeug',
    children: [],
  },

  /**
   * Unternehmen – im Kopf als Menü «Über uns» mit Bild je Unterpunkt, im Fuss als Spalte.
   * Testnotiz #1154: Ratgeber und Karriere waren vorher nur im Fuss und im
   * Mobil-Menü zu finden. Jede Seite muss über den Kopf erreichbar sein – geprüft beim Bauen
   * (scripts/check-site.mjs, «über das Menü erreichbar»).
   */
  about: {
    id: 'unternehmen',
    label: 'Über uns',
    href: '/ueber-uns',
    overview: 'Mehr über uns',
    ddText: 'Werkstatt, Team, Geschichte',
    text: 'Werkstatt, Team, Geschichte und die Übergabe von HS Steiner.',
    photo: 'werkstatt-aussen',
    children: [
      { label: 'Ratgeber', href: '/ratgeber', text: 'Prüfpflicht, Heukran planen, Verschleiss', photo: 'pruefung-hallenkran' },
      { label: 'Karriere', href: '/karriere', text: 'Arbeiten in unserer Werkstatt', photo: 'team' },
    ],
  },

  /** Übrige Punkte der Hauptzeile (Auftrag Kap. 7.1). */
  menu: [
    { label: 'Kontakt', href: '/kontakt' },
  ],

  /** Hauptaktion überall: Anfrage. */
  cta: { label: 'Anfrage stellen', href: '/kontakt' },

  footer: {
    claim:
      '{{brand.legalName}} (ehemals {{brand.formerLegalName}}) – Krantechnik, Fahrzeugtechnik und Speziallösungen aus Tuttwil-Wängi TG. Seit {{history.founded}}.',
  },

  /**
   * Konto, Profil und ERP – bestehende Next-Anwendung auf derselben Domain (Auftrag Kap. 6).
   * Die Website führt nur dorthin und zeigt den Anmeldezustand an (scripts/account.ts).
   */
  account: {
    login: { label: 'Anmelden', href: '/login' },
    profile: { label: 'Profil', href: '/konto' },
    logout: { label: 'Abmelden', href: '/abmelden' },
    /**
     * ERP – ein ganz gewöhnlicher Link neben «Über uns» und «Kontakt», sichtbar nur für
     * Personal (Admin, Mitarbeiter). Kein Untermenü (Testnotiz #1106): wer ins ERP geht,
     * wählt dort, was er braucht.
     */
    erp: { label: 'ERP', href: '/erp' },
  },
  /**
   * Pfade, die nicht zur Website gehören – robots.txt sperrt sie in jedem Modus. `/shop` ist
   * reserviert (Kap. 6.4): kein Link, keine Seite, nur hier.
   */
  privatePaths: ['/erp', '/konto', '/login', '/abmelden', '/shop', '/api/'],

  seo: {
    /**
     * Stand der Seiteninhalte (JJJJ-MM-TT) – `lastmod` in der Sitemap für jede Seite ohne
     * eigenes Datum. Ratgeber und Rechtstexte tragen ihr eigenes (`updated`). Wer eine Seite
     * inhaltlich überarbeitet, zieht dieses Datum nach.
     */
    contentUpdated: '2026-10-08',
    /** Bisherige Domain – wird später auf die neue weitergeleitet. */
    oldDomain: 'hs-steiner.ch',
    sameAs: [],
    /** robots.txt im Modus «live»: diese Crawler ausdrücklich zugelassen. */
    bots: [
      'Googlebot', 'Bingbot', 'Google-Extended', 'GPTBot', 'OAI-SearchBot', 'ChatGPT-User',
      'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'PerplexityBot', 'Perplexity-User',
      'Applebot', 'Applebot-Extended', 'CCBot',
    ],
    knowsAbout: [
      'Krane nach Mass', 'Sonderkrane', 'Kranservice', 'INEXXIO 365', 'Kranmodernisierung', 'Heukrananlagen',
      'Brückenkrane', 'Hängekrane', 'Schwenkkrane', 'Bootskrane', 'Mastkrane', 'Bootslifte',
      'Kranprüfung', 'Kranwartung', 'Funkfernsteuerung', 'Frequenzumrichter', 'Fahrmischer', 'Trommeltausch',
      'Verschleissteile für Fahrmischer', 'Spezialmaschinenbau', 'Anbaugeräte für Baumaschinen', 'Baumaschinen',
    ],
  },

  analytics: {
    /** null = aus. Mögliche Werte später: 'plausible'. */
    provider: null,
  },
};

/**
 * ►►► Die Navigation – EINE Liste für Kopf, Mobil-Menü und Fuss (Testnotiz #1209). ◄◄◄
 * Der Fuss zeigt genau die Punkte des Kopfs, in derselben Reihenfolge – weil er dieselbe
 * Liste liest, nicht weil jemand zwei Listen gleich hält. `scripts/check-site.mjs` prüft es
 * zusätzlich am gebauten HTML.
 * @typedef {{ id: string, label: string, href: string, overview: string, ddText?: string, text: string, photo: string, children: SubPage[] }} NavGroup
 * @type {NavGroup[]}
 */
export const navigation = [
  ...site.areas.map(({ id, label, href, overview, ddText, text, photo, children }) => ({ id, label, href, overview, ddText, text, photo, children })),
  { id: 'service', ...site.service },
  site.about,
];

/**
 * Fehlt diese Angabe?
 * @param {unknown} value
 */
export function isMissing(value) {
  return typeof value !== 'string' || value.trim() === '';
}

/** Die E-Mail-Adresse, die heute funktioniert. */
export function contactEmail() {
  return isMissing(site.email.primary) ? site.email.legacy : site.email.primary;
}

/** Der Bereich zu einer ID – bricht den Build, wenn es ihn nicht gibt. */
export function areaOf(/** @type {string} */ id) {
  const a = site.areas.find((x) => x.id === id);
  if (!a) throw new Error(`Bereich «${id}» gibt es nicht in site.areas.`);
  return a;
}
