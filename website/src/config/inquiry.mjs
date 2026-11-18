// @ts-check
import { t } from '../i18n/t.mjs';
/**
 * ►►► Das Vokabular des Anfrage-Formulars – an EINER Stelle. ◄◄◄
 *
 * Das Formular (InquiryForm) baut daraus seine Felder, das Backend
 * (backend/app/routers/contact.py) prüft gegen dieselbe Liste und schreibt mit denselben
 * Beschriftungen die E-Mail – `scripts/export-erp.mjs` überträgt sie nach
 * backend/app/assets/website_contact.json.
 *
 * ►►► Ein Feld für das Anliegen, sonst nur «wer fragt an» (Rückmeldung 04.10.2026). ◄◄◄
 * Bereich, Anliegen, Dringlichkeit, Standort, Hersteller und Baujahr sind ersatzlos
 * entfallen: «die Anfrage muss extrem einfach sein … ich plane, Anfragen KI-basiert zu
 * analysieren, dann weiss ich sofort, um was es geht». Was der Mensch schreibt, ist die
 * Angabe; eine Auswahl davor wäre eine zweite, die er erst treffen muss.
 */

export const inquiry = t('inquiry', {
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
   * Beschriftung je Feld im mailto-Ausweg – in dieser Reihenfolge, im Browser und auf der
   * Ausweichseite des Servers mit denselben Wörtern.
   */
  labels: [
    ['message', 'Anliegen'],
    ['name', 'Name'],
    ['company', 'Firma'],
    ['phone', 'Telefon'],
    ['email', 'E-Mail'],
  ],
  /**
   * Was als E-Mail-Adresse bzw. Telefonnummer gilt – als Text, denn Browser (`new RegExp`)
   * und Server (`re.compile`) lesen DENSELBEN Ausdruck. Beide Sprachen verstehen ihn gleich:
   * nur Zeichenklassen, Anker und Wiederholungen, keine Eigenheit der einen.
   */
  patterns: {
    email: '^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$',
    phone: '^[+()\\d][\\d\\s/().-]{5,}$',
  },
  /**
   * Der Betreff einer Anfrage: «Anfrage: <erster Satz>», gekappt am Wort nach `max` Zeichen.
   * Dieselbe Regel im ERP (backend/app/services/inquiry.subject_of) und im mailto-Ausweg
   * (src/lib/inquiry-subject.mjs) – sonst stünde dieselbe Anfrage je nach Weg unter einem
   * anderen Anliegen im Verlauf.
   */
  subject: { word: 'Anfrage', max: 60 },
  /** Beschriftung der Seite, von der die Anfrage kam – in der Nachricht im ERP. */
  sourceLabel: 'Seite',
  /** Fehlermeldungen – im Browser direkt am Feld und vom Server, wortgleich. */
  messages: {
    message: 'Bitte beschreiben Sie kurz Ihr Anliegen.',
    name: 'Bitte geben Sie Ihren Namen an.',
    emailMissing: 'Bitte geben Sie Ihre E-Mail-Adresse an – dorthin geht unsere Antwort.',
    phone: 'Diese Telefonnummer sieht unvollständig aus.',
    email: 'Diese E-Mail-Adresse ist nicht vollständig (Beispiel: name@firma.ch).',
    tooLong: 'Dieser Text ist zu lang – höchstens {max} Zeichen.',
    photosCount: 'Bitte höchstens {max} Dateien auswählen (jetzt {count}).',
    photosType: '«{name}» ist kein Bild im Format JPG, PNG oder WEBP.',
    photosSize: 'Die Dateien sind zusammen {size} gross – erlaubt sind {max}.',
    tooFast: 'Das ging schneller, als man tippen kann. Bitte senden Sie die Anfrage noch einmal.',
  },
  /**
   * Was der Server selbst sagt – die Antwort ohne JavaScript und die Meldungen, bevor das Formular
   * gelesen ist (`backend/app/routers/contact.py`, `routers/newsletter.py`). In der Sprache der Seite:
   * das Formular schickt sie mit (`?lang=`).
   */
  server: {
    check: 'Bitte prüfen Sie die markierten Angaben.',
    missingTitle: 'Es fehlen noch Angaben',
    missingLead: 'Es fehlen noch Angaben:',
    back: 'Mit der Zurück-Taste Ihres Browsers kommen Sie zum Formular – Ihre Eingaben sind noch da.',
    backButton: 'Zurück zum Formular',
    failedTitle: 'Das Senden hat nicht geklappt',
    failedText: 'Ihre Angaben sind nicht verloren: Rufen Sie uns an oder schicken Sie sie per E-Mail – der Text ist bereits vorbereitet.',
    call: 'Anrufen',
    mail: 'Per E-Mail senden',
    phone: 'Telefon',
    tooBig: 'Die Anfrage ist zu gross – Dateien zusammen höchstens {max}.',
    unreadable: 'Die Anfrage konnte nicht gelesen werden.',
    tooMany: 'Zu viele Anfragen in kurzer Zeit. Bitte rufen Sie uns an: {phone}.',
    unavailable: 'Das Senden ist gerade nicht möglich.',
    newsletterTooMany: 'Zu viele Anmeldungen in kurzer Zeit – bitte später noch einmal.',
    newsletterUnavailable: 'Die Anmeldung ist gerade nicht möglich – bitte später noch einmal.',
    newsletterBack: 'Mit der Zurück-Taste kommen Sie zum Formular.',
    newsletterAgain: 'Neu anmelden',
    /** Die Anrede der Mails (auf Deutsch steht sie im ERP: `domain/communication.greeting`). */
    hello: 'Guten Tag',
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
  },
  /** Höchstlängen je Feld – im Formular (maxlength) und im Backend dieselben. */
  limits: {
    message: 4000,
    name: 120,
    company: 160,
    phone: 40,
    email: 160,
  },
}, { keep: ['patterns', 'photos', 'subject.word', 'sourceLabel', 'labels'] });
