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
  /**
   * Anhänge (freiwillig): nur Bilder – sie werden im ERP gespeichert und an der Anfrage
   * gezeigt. HEIC fehlt mit Absicht: nennt `accept` es nicht, wandelt das iPhone das Foto
   * beim Auswählen selbst in JPEG um.
   */
  photos: {
    max: 3,
    maxTotalBytes: 10 * 1024 * 1024,
    accept: 'image/jpeg,image/png,image/webp',
    extensions: ['.jpg', '.jpeg', '.png', '.webp'],
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
    contact: 'Bitte geben Sie Ihre E-Mail-Adresse an – dorthin geht unsere Antwort.',
    phone: 'Diese Telefonnummer sieht unvollständig aus.',
    email: 'Diese E-Mail-Adresse ist nicht vollständig (Beispiel: name@firma.ch).',
    tooLong: 'Dieser Text ist zu lang – höchstens {max} Zeichen.',
    photosCount: 'Bitte höchstens {max} Dateien auswählen (jetzt {count}).',
    photosType: '«{name}» ist kein Bild im Format JPG, PNG oder WEBP.',
    photosSize: 'Die Dateien sind zusammen {size} gross – erlaubt sind {max}.',
    tooFast: 'Das ging schneller, als man tippen kann. Bitte senden Sie die Anfrage noch einmal.',
  },
  /** Texte der Bestätigung an die anfragende Person. Werte mit {{…}} aus site.mjs. */
  mail: {
    /** Betreff = Überschrift der Mail. Bewusst ein eigenes Anliegen: die Bestätigung
     *  beantwortet die Anfrage nicht, sie bleibt offen, bis ein Mensch antwortet. */
    confirmSubject: 'Angekommen – danke für Ihre Anfrage',
    confirmIntro:
      'Danke für Ihre Nachricht. Sie liegt jetzt nicht in einem Stapel, sondern bei den Menschen, die sich damit auskennen.',
    confirmNext: 'Wir melden uns innert {{promises.responseTime}}.',
    confirmMore: 'Fällt Ihnen noch etwas ein? Antworten Sie einfach auf diese E-Mail – es landet am selben Ort.',
    /** Stichwort rechts im Kopf der Mail. */
    kicker: 'Anfrage erhalten',
    copyTitle: 'Ihre Angaben',
    factCompany: 'Firma',
    factPhone: 'Rückruf an',
    factPhotos: 'Fotos',
    photoOne: '1 Bild',
    photoMany: '{n} Bilder',
    nextTitle: 'So geht es weiter',
    received: 'Angekommen',
    /** Davor steht die Telefonnummer der Gesellschaft – aus dem ERP, wie in der Unterschrift. */
    urgent: 'Eilt es? Dann rufen Sie uns direkt an:',
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
