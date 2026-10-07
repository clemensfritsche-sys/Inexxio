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
  'Produktentwicklung bei Liebherr (Baumaschinen)',
  'Produkt- und Plattformmanagement im IoT-Umfeld',
  'Weiterbildung in Betriebswirtschaft',
];

/**
 * @typedef {{ label: string, href: string, text: string, photo: string }} SubPage
 * @typedef {{
 *   id: 'krantechnik' | 'fahrzeugtechnik' | 'sonderloesungen',
 *   label: string, href: string, overview: string, text: string, photo: string,
 *   ogTitle: string,
 *   children: SubPage[],
 * }} Area
 */

/**
 * ►►► Die drei Bereiche (Auftrag Kap. 3.3) – Navigation, Mega-Dropdowns, Bereichskarten,
 * Footer, JSON-LD (hasOfferCatalog) und llms.txt entstehen daraus. ◄◄◄
 * Reihenfolge = Gewichtung (WEBSITE_PLAN §7.7a): Krantechnik und Fahrzeugtechnik sind die zwei
 * Standbeine, Sonderlösungen steht darunter. In der Krantechnik zuerst der Kranservice, dann
 * die Fokusmärkte, dann die Anschlagmittel.
 * @type {Area[]}
 */
const areas = [
  {
    id: 'krantechnik',
    label: 'Krantechnik',
    href: '/krantechnik',
    overview: 'Alle Leistungen Krantechnik',
    text: 'Service für Industrie-, Boots- und Heukrane aller Marken – der erste ist gratis. Dazu neue Krananlagen und Bootslifte nach Mass.',
    photo: 'heukran-einsatz',
    ogTitle: 'Ihr Kran läuft – oder Sie zahlen nicht.',
    children: [
      { label: 'Kranservice', href: '/krantechnik/kranservice', text: 'Erster Service gratis, INEXXIO 365: Ihr Kran läuft – oder Sie zahlen nicht', photo: 'pruefung-hallenkran' },
      { label: 'Industriekrane', href: '/krantechnik/industriekrane', text: 'Brücken-, Hänge- und Schwenkkrane in KMU', photo: 'reparatur-vor-ort' },
      { label: 'Häfen & Werften', href: '/krantechnik/haefen-werften', text: 'Boots- und Mastkrane, Bootslifte – neu und Service', photo: 'hafen-bootskran' },
      { label: 'Heukrananlagen', href: '/krantechnik/heukrananlagen', text: 'Neuanlagen nach Mass, Umbau, Service', photo: 'heukran-einsatz' },
      { label: 'Anschlagmittel', href: '/krantechnik/anschlagmittel', text: 'Ketten, Hebebänder, Haken – immer geprüft', photo: 'anschlagmittel' },
    ],
  },
  {
    id: 'fahrzeugtechnik',
    label: 'Fahrzeugtechnik',
    href: '/fahrzeugtechnik',
    overview: 'Alle Leistungen Fahrzeugtechnik',
    text: 'Trommeltausch, Revision und Reparatur für Fahrmischer und Aufbauten aller gängigen Marken – planbar im Winter.',
    photo: 'fahrmischer-werkstatt',
    ogTitle: 'Neue Trommel statt neuer Fahrmischer.',
    children: [
      { label: 'Fahrmischer', href: '/fahrzeugtechnik/fahrmischer', text: 'Service, Reparatur, Trommel-Revision und -tausch', photo: 'fahrmischer-werkstatt' },
      { label: 'Aufbauten: Reparatur & Service', href: '/fahrzeugtechnik/aufbauten-reparatur', text: 'LKW-Aufbauten, Mulden, Kipper, Hydraulik', photo: 'aufbau-reparatur' },
      { label: 'Verschleiss- & Ersatzteile', href: '/fahrzeugtechnik/verschleiss-ersatzteile', text: 'Rinnen, Schurren, Spiralschutz – alle gängigen Marken', photo: 'verschleissteile-detail' },
    ],
  },
  {
    id: 'sonderloesungen',
    label: 'Sonderlösungen',
    href: '/sonderloesungen',
    overview: 'Alle Leistungen Sonderlösungen',
    text: 'Konstruktion, Stahlbau und Umbauten an Baumaschinen – mit Ingenieurwissen und eigener Werkstatt.',
    photo: 'arbeit-werkstatt',
    ogTitle: 'Konstruktion, Schweiss- und Stahlbau, Umbau von Baumaschinen',
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
      'Krantechnik, Fahrzeugtechnik und Sonderlösungen aus Tuttwil-Wängi TG: Kranservice mit INEXXIO 365 für Industrie, Häfen und Landwirtschaft, Heukrananlagen und Bootslifte, Trommeltausch und Service für Fahrmischer, Konstruktion und Stahlbau. Seit {{history.founded}}.',
    /** Claim – OG-Bild und llms.txt. */
    claim: 'Krane und Fahrmischer mit Handschlagqualität. Ihr Bedarf, unsere passende Lösung. Zuverlässig und stets verfügbar.',
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
      text: 'Winter-Revision für Fahrmischer: Trommel und Aufbau überholen, solange der Bau ruht.',
      href: '/fahrzeugtechnik/fahrmischer#winter-revision',
      label: 'Revision planen',
      pages: ['/', '/fahrzeugtechnik', '/fahrzeugtechnik/fahrmischer', '/service'],
    },
    {
      id: 'heukran-planung',
      from: '01-01',
      to: '04-30',
      text: 'Neue Heukrananlage für die nächste Saison? Jetzt planen, damit sie vor dem ersten Schnitt läuft.',
      href: '/krantechnik/heukrananlagen#neuanlage',
      label: 'Anlage planen',
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
      '{{brand.legalName}} (ehemals {{brand.formerLegalName}}) – Krantechnik, Fahrzeugtechnik und Sonderlösungen aus Tuttwil-Wängi TG. Seit {{history.founded}}.',
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
    contentUpdated: '2026-10-07',
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
      'Kranservice', 'INEXXIO 365', 'Anschlagmittel', 'Krananlagen', 'Heukrananlagen', 'Heukrane', 'Industriekrane', 'Brückenkrane', 'Hängekrane',
      'Bootskrane', 'Mastkrane', 'Bootslifte', 'Hafenkrane', 'Trommeltausch',
      'Schwenkkrane', 'Drehkrane', 'Kranprüfung', 'Kranwartung', 
      'Funkfernsteuerung', 'Frequenzumrichter', 'Fahrmischer', 'Trommel-Revision',
      'Verschleissteile für Fahrmischer', 'LKW-Aufbauten', 'Konstruktion', 'Stahlbau',
      'Schweissarbeiten', 'Baumaschinen',
    ],
  },

  analytics: {
    /** null = aus. Mögliche Werte später: 'plausible'. */
    provider: null,
  },
};

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
