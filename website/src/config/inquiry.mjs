// @ts-check
/**
 * ►►► Das Vokabular des Anfrage-Formulars – an EINER Stelle. ◄◄◄
 *
 * Das Formular (InquiryForm/ShortForm) baut daraus seine Auswahl, das Backend
 * (backend/app/routers/contact.py) prüft gegen dieselbe Liste und schreibt mit denselben
 * Beschriftungen die E-Mail – `scripts/export-contact.mjs` überträgt sie nach
 * backend/app/assets/website_contact.json. Ein neuer Wert ist damit eine Zeile hier.
 */
export const inquiry = {
  kinds: [
    { value: 'kran', label: 'Kran', hint: 'Prüfung, Wartung, Störung, Modernisierung, Neuanlage', subject: 'Kran' },
    { value: 'fahrmischer', label: 'Fahrmischer', hint: 'Service, Reparatur, Trommel-Revision', subject: 'Fahrmischer' },
    { value: 'teile', label: 'Verschleiss- oder Ersatzteile', hint: 'Rinnen, Schurren, Spiralschutz, Kranteile', subject: 'Teile' },
    { value: 'abo', label: 'Service-Abo', hint: 'Prüfung und Wartung zum Fixpreis', subject: 'Abo' },
    { value: 'anderes', label: 'Anderes', hint: 'Beschreiben Sie Ihr Anliegen im nächsten Schritt', subject: 'Anderes' },
  ],
  needs: {
    kran: [
      { value: 'pruefung', label: 'Prüfung' },
      { value: 'wartung', label: 'Wartung' },
      { value: 'stoerung', label: 'Störung / Reparatur' },
      { value: 'modernisierung', label: 'Modernisierung' },
      { value: 'neuanlage', label: 'Neuanlage' },
    ],
    fahrmischer: [
      { value: 'service', label: 'Service' },
      { value: 'reparatur', label: 'Reparatur' },
      { value: 'trommel', label: 'Trommel-Revision' },
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
  photos: {
    max: 3,
    maxTotalBytes: 10 * 1024 * 1024,
    accept: 'image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif',
    extensions: ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'],
  },
  /** Mindestausfüllzeit in Sekunden (Schutz vor Bots, ohne CAPTCHA). */
  minSeconds: 3,
  /**
   * Beschriftung je Feld in E-Mail und mailto-Text – in dieser Reihenfolge. Dieselben
   * Wörter in der E-Mail an uns, in der Bestätigung und im Notfall-mailto.
   */
  labels: [
    ['kind', 'Worum geht es'],
    ['need', 'Was'],
    ['part', 'Teil'],
    ['mixer', 'Für Fahrmischer'],
    ['cranes', 'Anzahl Krane'],
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
    kind: 'Bitte wählen Sie aus, worum es geht.',
    need: 'Bitte wählen Sie, was gemacht werden soll.',
    part: 'Bitte nennen Sie das Teil, das Sie brauchen.',
    urgency: 'Bitte wählen Sie, wie dringend es ist.',
    year: 'Bitte das Baujahr vierstellig angeben, z. B. 1998.',
    cranes: 'Bitte die Anzahl Krane als Zahl angeben, z. B. 3.',
    place: 'Bitte geben Sie PLZ und Ort an – dort, wo die Anlage steht.',
    message: 'Bitte beschreiben Sie kurz Ihr Anliegen.',
    name: 'Bitte geben Sie Ihren Namen an.',
    contact: 'Bitte geben Sie eine Telefonnummer oder eine E-Mail-Adresse an.',
    phone: 'Diese Telefonnummer sieht unvollständig aus.',
    email: 'Diese E-Mail-Adresse ist nicht vollständig (Beispiel: name@firma.ch).',
    prefPhone: 'Sie möchten einen Anruf – dafür brauchen wir Ihre Telefonnummer.',
    prefEmail: 'Sie möchten eine E-Mail – dafür brauchen wir Ihre Adresse.',
    tooLong: 'Dieser Text ist zu lang – höchstens {max} Zeichen.',
    photosCount: 'Bitte höchstens {max} Fotos auswählen (jetzt {count}).',
    photosType: '«{name}» ist kein unterstütztes Bild (JPG, PNG, WEBP oder HEIC).',
    photosSize: 'Die Fotos sind zusammen {size} gross – erlaubt sind {max}.',
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
    urgentPikett: 'Ausserhalb der Bürozeiten erreichen Sie unser Pikett: {{pikett.display}}.',
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
    mixer: 160,
    cranes: 3,
  },
};
