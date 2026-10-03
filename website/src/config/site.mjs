// @ts-check
/**
 * ►►► DIE EINE QUELLE der Website. ◄◄◄
 *
 * Alles, was mehr als einmal vorkommt – Name, Telefon, Adresse, Öffnungszeiten,
 * Navigation, Schalter –, steht hier und nur hier. Header, Footer, Kontaktseite,
 * JSON-LD, llms.txt, Sitemap, robots.txt und die E-Mail-Vorlagen des Formulars lesen
 * ausschliesslich daraus (die Vorlagen über `scripts/export-contact.mjs`).
 *
 * Ein Namenswechsel (z. B. «HS Steiner – Teil von INEXXIO») ist eine Änderung in
 * `brand` – Texte setzen den Namen über `{{brand.name}}` bzw. `{{brand.full}}` ein.
 *
 * Markierungen:
 *   [[PLATZHALTER: …]]  Information fehlt.
 *   [[PRÜFEN: …]]       vorhanden, aber freizugeben bzw. fachlich/rechtlich zu prüfen.
 * Im Modus «live» bricht der Build ab, solange eine davon existiert
 * (`scripts/check-content.mjs`). Ein Wert, der NUR aus einer Markierung besteht, gilt
 * als «fehlt» – Links darauf werden nicht gebaut.
 *
 * Bewusst .mjs statt .ts: die Node-Skripte (Prüfung, Export für die E-Mail-Vorlagen)
 * lesen dieselbe Datei ohne Übersetzungsschritt.
 */

export const site = {
  brand: {
    name: 'INEXXIO',
    /** Beschreibender Zusatz – steht nie allein weg (Verwechslungsgefahr mit «inexio»). */
    descriptor: 'Kran- und Fahrmischertechnik',
    descriptorReview:
      '[[PRÜFEN: Zusatz zum Markennamen – Alternativen «Krantechnik» oder «Kran- und Fahrzeugtechnik»]]',
    formerly: 'ehemals HS Steiner',
    /** Erste Nennung auf jeder Seite. */
    full: '{{brand.name}} ({{brand.formerly}})',
    /** Wortmarke: 'a' = schwarz, 'b' = rotes «XX» (Alternative). */
    logoVariant: 'a',
    logoReview: '[[PLATZHALTER: finales Logo]]',
    legalName: '[[PLATZHALTER: künftiger Name im Handelsregister]]',
    formerLegalName: 'HS Steiner Fahrzeug- und Kranbau GmbH',
    alternateNames: ['HS Steiner', 'HS Steiner Fahrzeug- und Kranbau GmbH', 'HS Krananlagen'],
    /** Abgrenzung für Suchmaschinen und KI-Assistenten. */
    notToConfuse: 'Nicht zu verwechseln mit inexio (Telekommunikation, Deutschland).',
    uid: '[[PLATZHALTER: UID]]',
  },

  history: {
    founded: 1982,
    foundedText: 'Heiri Steiner baut die Reparaturwerkstätte in Tuttwil-Wängi und macht sich selbstständig.',
    cranesSince: 1985,
    cranesText: 'Erste eigene Krananlagen – «HS Krananlagen» für Industrie und Landwirtschaft.',
    gmbhYear: 1993,
    gmbhReview: '[[PRÜFEN: Gründungsjahr der GmbH]]',
    handoverDate: '[[PLATZHALTER: Übergabedatum]]',
    /** Formulierung statt einer Zahl, die jedes Jahr nachgeführt werden müsste. */
    experience: 'über 40 Jahre',
    markets: 'in der Schweiz, in Deutschland, Österreich und im Südtirol',
  },

  people: {
    owner: {
      name: 'Clemens Fritsche',
      role: 'Geschäftsführer',
      short:
        'Maschinenbauingenieur, Produktentwicklung bei Liebherr (Baumaschinen), Produkt- und Plattformmanagement im IoT-Umfeld, betriebswirtschaftliche Weiterbildung.',
      titles: '[[PLATZHALTER: genaue Titel und Abschlüsse]]',
      linkedin: '[[PLATZHALTER: LinkedIn-Link]]',
    },
    founder: {
      name: 'Heiri Steiner',
      role: 'Gründer',
    },
  },

  phone: { display: '052 378 22 47', intl: '+41 52 378 22 47', e164: '+41523782247' },
  pikett: {
    display: '076 563 22 47',
    intl: '+41 76 563 22 47',
    e164: '+41765632247',
    review: '[[PRÜFEN: Pikett weiterführen? Zeiten?]]',
    hours: '[[PLATZHALTER: Pikett-Zeiten]]',
  },
  email: {
    /** Die neue Adresse ist offen; bis dahin bleibt die bisherige erreichbar. */
    primary: '[[PLATZHALTER: neue E-Mail-Adresse]]',
    legacy: 'fahrzeug-kranbau@hs-steiner.ch',
  },
  /** Bewerbungen: dieselbe Adresse, bis eine eigene feststeht. */
  jobsEmailReview: '[[PLATZHALTER: Adresse für Bewerbungen]]',

  address: {
    street: 'Waldweg 1',
    zip: '9546',
    city: 'Tuttwil',
    municipality: 'Wängi',
    canton: 'TG',
    country: 'CH',
    countryName: 'Schweiz',
  },
  geo: { lat: 47.4836, lng: 8.9357, review: '[[PRÜFEN: Koordinaten]]' },

  hours: {
    /** Für Menschen. */
    text: 'Mo–Fr 7.00–12.00 und 13.15–17.30 Uhr',
    /** Für JSON-LD (openingHoursSpecification). */
    spec: [
      { days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], opens: '07:00', closes: '12:00' },
      { days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], opens: '13:15', closes: '17:30' },
    ],
    review: '[[PRÜFEN: Öffnungszeiten]]',
  },

  area: {
    summary: 'rund 1 Stunde ab Tuttwil: Thurgau, St. Gallen, Raum Winterthur/Zürich, Schaffhausen',
    regions: ['Thurgau', 'St. Gallen', 'Raum Winterthur', 'Raum Zürich', 'Schaffhausen'],
    review: '[[PRÜFEN: Einsatzgebiet]]',
    abroad: 'Service für HS-Krananlagen in Deutschland, Österreich und im Südtirol auf Anfrage.',
    abroadReview: '[[PRÜFEN: Service im Ausland]]',
    /** Für JSON-LD: Kantone und Länder. */
    served: ['Thurgau', 'St. Gallen', 'Zürich', 'Schaffhausen', 'Appenzell Ausserrhoden'],
  },

  promises: {
    /** «Wir melden uns innert …» */
    responseTime: '[[PLATZHALTER: Antwortzeit, z. B. einem Arbeitstag]]',
    /** «Wie schnell sind Sie vor Ort?» */
    reactionTime: '[[PLATZHALTER: realistische Reaktionszeit]]',
  },

  marks: {
    crane: 'Krane aller Hersteller',
    mixers: ['Intermix', 'Putzmeister', 'Cifa', 'Stetter', 'Liebherr', 'Belmix', 'Peter'],
    mixerNotice:
      'Markennamen gehören ihren Inhabern. Wir sind unabhängig und kein Vertragshändler.',
    mixerReview: '[[PRÜFEN: bestehende Partnerschaften, z. B. Cifa?]]',
  },

  /** Elemente, die sich per Schalter abschalten lassen. */
  features: {
    /** Ankündigungsleiste über dem Header. */
    announcement: true,
    /** Heiri Steiner bleibt in der Übergangszeit beratend dabei – alles dazu hängt hier. */
    heiriAdvisory: true,
    pikett: true,
    /** Ohne echten Inhalt aus: */
    references: false,
    beforeAfter: false,
    team: false,
    jobPosting: false,
    whatsapp: false,
  },
  whatsappReview: '[[PLATZHALTER: WhatsApp-Kontakt – ja oder nein, mit welcher Nummer?]]',

  announcement: {
    text: 'HS Steiner heisst jetzt {{brand.name}}. Gleiches Team, gleiche Nummer.',
    review: '[[PRÜFEN: «Gleiches Team» bestätigen]]',
    link: { label: 'Mehr erfahren', href: '/uebergabe' },
    /** Neue ID = die Leiste erscheint wieder, auch bei denen, die sie geschlossen haben. */
    id: 'uebergabe-2026',
  },

  /** Saison-Aktionen: von/bis als MM-TT, über den Jahreswechsel erlaubt. */
  seasons: [
    {
      id: 'winter-revision',
      from: '11-01',
      to: '02-28',
      text: 'Winter-Revision für Fahrmischer: Trommel und Aufbau überholen, solange der Bau ruht.',
      href: '/fahrmischer/service-reparatur#winter-revision',
      label: 'Revision planen',
      pages: ['/', '/fahrmischer', '/fahrmischer/service-reparatur'],
    },
    {
      id: 'heukran-check',
      from: '03-01',
      to: '05-31',
      text: 'Saison-Check für Heukrane – vor dem ersten Schnitt.',
      href: '/krane/hs-krananlagen#saison-check',
      label: 'Check anfragen',
      pages: ['/', '/krane', '/krane/hs-krananlagen', '/krane/pruefung-wartung'],
    },
  ],

  nav: [
    {
      label: 'Krane',
      href: '/krane',
      overview: 'Alle Kranleistungen',
      children: [
        { label: 'Prüfung & Wartung', href: '/krane/pruefung-wartung', text: 'Jährliche Kontrolle mit Prüfbericht' },
        { label: 'Reparatur & Pikett', href: '/krane/reparatur', text: 'Störung beheben, Teile ab Lager' },
        { label: 'Modernisierung', href: '/krane/modernisierung', text: 'Funk, Umrichter, Überlastsicherung' },
        { label: 'HS-Krananlagen', href: '/krane/hs-krananlagen', text: 'Service, Ersatzteile, Neuanlagen' },
      ],
    },
    {
      label: 'Fahrmischer',
      href: '/fahrmischer',
      overview: 'Übersicht Fahrmischer',
      children: [
        { label: 'Service & Reparatur', href: '/fahrmischer/service-reparatur', text: 'Alle Marken, Trommel-Revision' },
        { label: 'Verschleissteile', href: '/fahrmischer/verschleissteile', text: 'Rinnen, Schurren, Spiralschutz' },
      ],
    },
    { label: 'Service', href: '/service-abo' },
    { label: 'Ratgeber', href: '/ratgeber' },
    { label: 'Über uns', href: '/ueber-uns' },
  ],

  /** Hauptaktion überall: Anfrage. */
  cta: { label: 'Service anfragen', href: '/kontakt' },

  footer: {
    claim:
      '{{brand.name}} (ehemals {{brand.formerLegalName}}) – Prüfung, Service und Reparatur von Krananlagen und Fahrmischern in der Ostschweiz. Seit {{history.founded}} in Tuttwil-Wängi TG.',
  },

  /** Kundenbereich des ERP (eigene Anwendung auf derselben Domain). */
  login: { label: 'Kunden-Login', href: '/login' },
  /** Pfade, die nicht zur Website gehören – robots.txt sperrt sie im Modus «live». */
  privatePaths: ['/erp', '/konto', '/login', '/api/'],

  seo: {
    /** Bisherige Domain – wird später auf die neue weitergeleitet. */
    oldDomain: 'hs-steiner.ch',
    /** Künftige Domain (ohne https://). Im Modus «live» muss SITE_URL darauf zeigen. */
    domain: '[[PLATZHALTER: Domain]]',
    sameAs: [],
    sameAsReview: '[[PLATZHALTER: Google-Unternehmensprofil, LinkedIn]]',
    /** robots.txt im Modus «live»: diese Crawler ausdrücklich zugelassen. */
    bots: [
      'Googlebot', 'Bingbot', 'Google-Extended', 'GPTBot', 'OAI-SearchBot', 'ChatGPT-User',
      'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'PerplexityBot', 'Perplexity-User',
      'Applebot', 'Applebot-Extended', 'CCBot',
    ],
    knowsAbout: [
      'Kranprüfung', 'Kranwartung', 'Kranreparatur', 'Brückenkrane', 'Hängekrane', 'Schwenkkrane',
      'Drehkrane', 'Heukrane', 'HS-Krananlagen', 'Funkfernsteuerung', 'Frequenzumrichter',
      'Fahrmischer', 'Betonfördertechnik', 'Trommel-Revision', 'Verschleissteile für Fahrmischer',
    ],
  },

  analytics: {
    /** null = aus. Mögliche Werte später: 'plausible'. */
    provider: null,
    review: '[[PRÜFEN: kostenlose oder günstige cookielose Analytics-Lösung wählen]]',
  },
};

/**
 * Ist dieser Wert nur eine Markierung (also: die Angabe fehlt)?
 * @param {unknown} value
 */
export function isMissing(value) {
  return typeof value !== 'string' || /^\s*\[\[(PLATZHALTER|PRÜFEN):[^\]]*\]\]\s*$/.test(value);
}

/** Die E-Mail-Adresse, die heute funktioniert. */
export function contactEmail() {
  return isMissing(site.email.primary) ? site.email.legacy : site.email.primary;
}
