// @ts-check
/**
 * ►►► Das Vokabular des Anfrage-Formulars – an EINER Stelle. ◄◄◄
 *
 * Das Formular (InquiryForm/ShortForm) baut daraus seine Auswahl, das Backend
 * (backend/app/routers/contact.py) prüft gegen dieselbe Liste und schreibt mit denselben
 * Beschriftungen die E-Mail – `scripts/export-contact.mjs` überträgt sie nach
 * backend/app/assets/website_contact.json. Ein neuer Wert ist damit eine Zeile hier.
 *
 * Die drei Bereiche heissen wie in der Navigation (Auftrag Kap. 5.4 und 11.1).
 */

/** @typedef {'krantechnik' | 'fahrzeugtechnik' | 'sonderloesungen' | 'teile' | 'anderes'} InquiryKind */

export const inquiry = {
  /** Schritt 1 «Bereich». */
  kinds: [
    { value: 'krantechnik', label: 'Krantechnik', hint: 'Heukrananlage, Industriekran, Prüfung, Wartung, Störung, Modernisierung', subject: 'Krantechnik' },
    { value: 'fahrzeugtechnik', label: 'Fahrzeugtechnik', hint: 'Fahrmischer-Service, Reparatur, Trommel-Revision, Aufbauten', subject: 'Fahrzeugtechnik' },
    { value: 'sonderloesungen', label: 'Sonderlösungen', hint: 'Konstruktion, Schweiss- und Stahlbau, Baumaschinen', subject: 'Sonderlösungen' },
    { value: 'teile', label: 'Ersatz- oder Verschleissteile', hint: 'Rinnen, Schurren, Spiralschutz, Kranteile', subject: 'Teile' },
    { value: 'anderes', label: 'Anderes', hint: 'Beschreiben Sie Ihr Anliegen im nächsten Schritt', subject: 'Anderes' },
  ],
  /** Schritt 2 «Anliegen» – abhängig vom Bereich. Teile fragen stattdessen «welches, wofür». */
  needs: {
    krantechnik: [
      { value: 'heukrananlage', label: 'Neue Heukrananlage' },
      { value: 'industriekran', label: 'Neuer Industriekran' },
      { value: 'pruefung', label: 'Prüfung' },
      { value: 'wartung', label: 'Wartung' },
      { value: 'stoerung', label: 'Störung / Reparatur' },
      { value: 'modernisierung', label: 'Modernisierung' },
    ],
    fahrzeugtechnik: [
      { value: 'fahrmischer-service', label: 'Fahrmischer-Service' },
      { value: 'reparatur', label: 'Reparatur' },
      { value: 'trommel', label: 'Trommel-Revision' },
      { value: 'aufbau', label: 'Aufbau-Reparatur' },
    ],
    sonderloesungen: [
      { value: 'konstruktion', label: 'Konstruktion' },
      { value: 'stahlbau', label: 'Schweiss-/Stahlbau' },
      { value: 'baumaschine', label: 'Baumaschine Umbau/Reparatur' },
    ],
  },
  urgencies: [
    { value: 'dringend', label: 'Steht still – dringend', subject: 'DRINGEND' },
    { value: 'wochen', label: 'In den nächsten Wochen', subject: 'BALD' },
    { value: 'planung', label: 'Planung', subject: 'PLANUNG' },
  ],
  contactPrefs: [
    { value: 'telefon', label: 'Telefon' },
    { value: 'email', label: 'E-Mail' },
  ],
  /** Fotos oder Skizzen (Auftrag 11.1): Bilder und PDF. */
  photos: {
    max: 3,
    maxTotalBytes: 10 * 1024 * 1024,
    accept: 'image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif,application/pdf,.pdf',
    extensions: ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.pdf'],
  },
  /** Mindestausfüllzeit in Sekunden (Schutz vor Bots, ohne CAPTCHA). */
  minSeconds: 3,
  /**
   * Beschriftung je Feld in E-Mail und mailto-Text – in dieser Reihenfolge. Dieselben
   * Wörter in der E-Mail an uns, in der Bestätigung und im Notfall-mailto.
   */
  labels: [
    ['kind', 'Bereich'],
    ['need', 'Anliegen'],
    ['part', 'Teil'],
    ['usage', 'Wofür'],
    ['urgency', 'Dringlichkeit'],
    ['maker', 'Hersteller / Typ'],
    ['year', 'Baujahr'],
    ['place', 'Standort'],
    ['message', 'Beschreibung'],
    ['name', 'Name'],
    ['company', 'Firma'],
    ['phone', 'Telefon'],
    ['email', 'E-Mail'],
    ['contact_pref', 'Rückmeldung per'],
  ],
  /** Fehlermeldungen – im Browser direkt am Feld und vom Server, wortgleich. */
  messages: {
    kind: 'Bitte wählen Sie den Bereich.',
    need: 'Bitte wählen Sie Ihr Anliegen.',
    part: 'Bitte nennen Sie das Teil, das Sie brauchen.',
    urgency: 'Bitte wählen Sie, wie dringend es ist.',
    year: 'Bitte das Baujahr vierstellig angeben, z. B. 1998.',
    place: 'Bitte geben Sie PLZ und Ort an – dort, wo die Anlage oder Maschine steht.',
    message: 'Bitte beschreiben Sie kurz Ihr Anliegen.',
    name: 'Bitte geben Sie Ihren Namen an.',
    contact: 'Bitte geben Sie eine Telefonnummer oder eine E-Mail-Adresse an.',
    phone: 'Diese Telefonnummer sieht unvollständig aus.',
    email: 'Diese E-Mail-Adresse ist nicht vollständig (Beispiel: name@firma.ch).',
    prefPhone: 'Sie möchten einen Anruf – dafür brauchen wir Ihre Telefonnummer.',
    prefEmail: 'Sie möchten eine E-Mail – dafür brauchen wir Ihre Adresse.',
    tooLong: 'Dieser Text ist zu lang – höchstens {max} Zeichen.',
    photosCount: 'Bitte höchstens {max} Dateien auswählen (jetzt {count}).',
    photosType: '«{name}» ist kein unterstütztes Format (JPG, PNG, WEBP, HEIC oder PDF).',
    photosSize: 'Die Dateien sind zusammen {size} gross – erlaubt sind {max}.',
    tooFast: 'Das ging schneller, als man tippen kann. Bitte senden Sie die Anfrage noch einmal.',
  },
  /**
   * Texte der Bestätigung an die anfragende Person. Werte mit {{…}} aus site.mjs; fehlt
   * ein Wert noch (Markierung), gilt `fallback` – eine E-Mail enthält nie eine Markierung.
   */
  mail: {
    confirmSubject: 'Ihre Anfrage bei {{brand.full}}',
    confirmIntro: 'Danke für Ihre Anfrage. Hier ist eine Kopie Ihrer Angaben.',
    confirmNext: { text: 'Wir melden uns innert {{promises.responseTime}}.', fallback: 'Wir melden uns so bald wie möglich.' },
    urgent: 'Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.display}}.',
    urgentNotfall: 'Ausserhalb der Bürozeiten erreichen Sie unsere Notfallnummer: {{notfall.display}}.',
    closing: 'Freundliche Grüsse',
  },
  /** Höchstlängen je Feld – im Formular (maxlength) und im Backend dieselben. */
  limits: {
    name: 120,
    company: 160,
    phone: 40,
    email: 160,
    place: 120,
    maker: 160,
    year: 4,
    message: 4000,
    part: 200,
    usage: 160,
  },
};

/** Bereiche mit einer Auswahl «Anliegen». */
export const kindsWithNeeds = /** @type {(keyof typeof inquiry.needs)[]} */ (Object.keys(inquiry.needs));
