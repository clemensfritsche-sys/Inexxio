/** Kontakt (Auftrag Kap. 7.7, 11.1). */
export const kontakt = {
  title: 'Kontakt und Anfrage',
  description:
    'Kontakt zu INEXXIO (ehemals HS Steiner) in Tuttwil-Wängi TG: Anfrage in drei Schritten, Telefon 052 378 22 47 und Anfahrt. Antwort innert kurzer Zeit.',
  /** Überschrift und Satz des EINEN Kontaktbereichs (ContactSection) – auf jeder Seite gleich. */
  h1: 'Kontakt und Anfrage',
  lead: 'Beschreiben Sie Ihr Anliegen in drei kurzen Schritten – oder rufen Sie an: {{phone.link}}.',
  summary:
    '{{brand.full}}, {{address.line}} ({{address.municipality}} {{address.canton}}). Telefon {{phone.display}}.',
  /** Satz über der Anschrift – die Anschrift selbst kommt aus dem ERP (#1108). */
  where: '{{brand.full}} – unsere Werkstatt in {{area.home}}.',
  route: 'Route in Google Maps öffnen',
  danke: {
    title: 'Danke für Ihre Anfrage',
    lead: 'Ihre Anfrage ist bei uns angekommen. Wir melden uns innert {{promises.responseTime}}.',
    next: [
      'Sie erhalten eine Bestätigung per E-Mail mit Ihren Angaben – sofern Sie eine E-Mail-Adresse genannt haben.',
      'Wir prüfen Ihr Anliegen und melden uns auf dem Weg, den Sie gewählt haben.',
      'Eilt es? Rufen Sie an: {{phone.link}}.',
    ],
  },
};
