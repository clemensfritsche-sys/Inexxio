// @ts-check
/**
 * ►►► Das Vokabular des Anfrage-Formulars – an EINER Stelle. ◄◄◄
 *
 * Das Formular (InquiryForm) baut daraus seine Felder, das Backend
 * (backend/app/routers/contact.py) prüft gegen dieselbe Liste und schreibt mit denselben
 * Beschriftungen die E-Mail – `scripts/export-contact.mjs` überträgt sie nach
 * backend/app/assets/website_contact.json.
 *
 * ►►► Ein Feld für das Anliegen, sonst nur «wer fragt an» (Rückmeldung 04.10.2026). ◄◄◄
 * Bereich, Anliegen, Dringlichkeit, Standort, Hersteller und Baujahr sind ersatzlos
 * entfallen: «die Anfrage muss extrem einfach sein … ich plane, Anfragen KI-basiert zu
 * analysieren, dann weiss ich sofort, um was es geht». Was der Mensch schreibt, ist die
 * Angabe; eine Auswahl davor wäre eine zweite, die er erst treffen muss.
 */

export const inquiry = {
  /** Anhänge (freiwillig): Fotos, Skizzen, PDF. */
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
   * Wörter in der E-Mail an uns, in der Bestätigung und im mailto-Ausweg.
   */
  labels: [
    ['message', 'Anliegen'],
    ['name', 'Name'],
    ['company', 'Firma'],
    ['phone', 'Telefon'],
    ['email', 'E-Mail'],
  ],
  /** Fehlermeldungen – im Browser direkt am Feld und vom Server, wortgleich. */
  messages: {
    message: 'Bitte beschreiben Sie kurz Ihr Anliegen.',
    name: 'Bitte geben Sie Ihren Namen an.',
    contact: 'Bitte geben Sie eine Telefonnummer oder eine E-Mail-Adresse an.',
    phone: 'Diese Telefonnummer sieht unvollständig aus.',
    email: 'Diese E-Mail-Adresse ist nicht vollständig (Beispiel: name@firma.ch).',
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
    closing: 'Freundliche Grüsse',
  },
  /** Höchstlängen je Feld – im Formular (maxlength) und im Backend dieselben. */
  limits: {
    message: 4000,
    name: 120,
    company: 160,
    phone: 40,
    email: 160,
  },
};
