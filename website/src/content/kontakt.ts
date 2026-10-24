/** Kontakt (Auftrag Kap. 7.7, 11.1). */
export const kontakt = {
  title: 'Kontakt und Anfrage',
  description:
    'Kontakt zu INEXXIO in {{address.home}}: Anfrage stellen, anrufen oder die Route zum Standort öffnen. Ein Satz genügt – wir melden uns rasch.',
  /** Überschrift und Satz des EINEN Kontaktbereichs (ContactSection) – auf jeder Seite gleich. */
  h1: 'Fragen kostet nichts.',
  lead: 'Ein Satz genügt. Den Rest klären wir mit Ihnen.',
  /** Die Karte mit dem Ansprechpartner neben dem Formular. */
  person: {
    label: 'Ihr Ansprechpartner',
    text: 'Lieber direkt sprechen? Rufen Sie an.',
  },
  summary:
    '{{brand.name}}, {{address.line}} ({{address.municipality}} {{address.canton}}). Telefon {{phone.display}}.',
  danke: {
    title: 'Danke für Ihre Anfrage',
    lead: 'Ihre Anfrage ist bei uns angekommen. Wir melden uns innert {{promises.responseTime}}.',
    next: [
      'Sie erhalten eine Bestätigung per E-Mail mit Ihren Angaben – sofern Sie eine E-Mail-Adresse genannt haben.',
      'Wir prüfen Ihr Anliegen und melden uns per Telefon oder E-Mail.',
      'Eilt es? Rufen Sie an: {{phone.link}}.',
    ],
  },
};
