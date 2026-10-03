// @ts-check
/**
 * Service-Abo: drei Stufen. Namen, Inhalte und Preise sind offen – sie stehen hier einmal und
 * erscheinen auf /service-abo und als Vorschau auf der Startseite.
 */
export const abo = {
  review: '[[PRÜFEN: Stufennamen und Inhalte der Abo-Stufen]]',
  price: 'ab CHF [[PLATZHALTER: Preis]] pro Kran und Jahr',
  tiers: [
    {
      id: 'pruefung',
      name: 'Prüfung',
      summary: 'Die Prüfpflicht erfüllt – ohne daran denken zu müssen.',
      items: [
        'Jährliche Überprüfung durch Kranfachleute',
        'Prüfbericht',
        'Eintrag ins digitale Kranbuch',
        'Terminerinnerung',
      ],
    },
    {
      id: 'service',
      name: 'Service',
      featured: true,
      summary: 'Prüfung und Wartung in einem Termin.',
      includes: 'Alles aus «Prüfung», dazu:',
      items: [
        'Wartung nach Herstellervorgabe',
        'Verschleiss-Check',
        'Schmierung',
        'Anfahrt zum Fixpreis',
      ],
    },
    {
      id: 'komplett',
      name: 'Komplett',
      summary: 'Für Krane, die nicht stillstehen dürfen.',
      includes: 'Alles aus «Service», dazu:',
      items: [
        'Bevorzugte Reaktion bei Störungen',
        'Rabatt auf Ersatzteile',
        'Jährlicher Modernisierungs-Check',
      ],
    },
  ],
};
