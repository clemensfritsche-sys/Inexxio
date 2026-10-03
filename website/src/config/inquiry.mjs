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
