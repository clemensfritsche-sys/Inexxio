// @ts-check
/**
 * Verschleissteile für Fahrmischer – das Programm ist im Aufbau. Teileliste, Material und
 * passende Typen sind fachlich zu bestätigen; Preise gibt es bewusst keine (kein Shop).
 * Gruppiert nach Teileart.
 *
 * Die Felder je Teil sind die eines ERP-Artikels (Auftrag 6.4), damit der Katalog später 1:1
 * aus dem ERP gefüllt werden kann: `sku` (Artikelnummer, solange keine vergeben ist: leer),
 * `name` (Bezeichnung), `fits` (passend für – fehlt es, gilt `catalog.fits`), `material`,
 * `photo` (Bild).
 *
 * @typedef {{ id: string, sku?: string, name: string, text: string, fits?: string[], material: string, photo: string }} Part
 * @typedef {{ id: string, title: string, intro: string, items: Part[] }} PartGroup
 */
export const catalog = {
  review: '[[PRÜFEN: Teileliste, Material, passende Typen]]',
  priceNote: 'Preise auf Anfrage [[PLATZHALTER: Preise für Verschleissteile]]',
  /** @type {PartGroup[]} */
  groups: [
    {
      id: 'rinnen',
      title: 'Rinnen',
      intro: 'Die Rinne führt den Beton von der Trommel an die Einbaustelle – ihre Lauffläche nutzt sich mit jeder Fuhre ab.',
      items: [
        {
          id: 'auslaufrinne',
          photo: 'teil-auslaufrinne',
          name: 'Auslaufrinne',
          text: 'Hauptrinne am Trommelauslauf, schwenk- und klappbar.',
          material: '[[PRÜFEN: Material und Blechstärke]]',
        },
        {
          id: 'verlaengerungsrinne',
          photo: 'teil-verlaengerungsrinne',
          name: 'Verlängerungsrinne',
          text: 'Ansteckbare Rinne für mehr Reichweite an der Baustelle.',
          material: '[[PRÜFEN: Material und Länge]]',
        },
      ],
    },
    {
      id: 'schurren',
      title: 'Schurren und Trichter',
      intro: 'Schurren und Trichter lenken den Beton beim Befüllen und Entleeren – und fangen dabei den Verschleiss ab.',
      items: [
        {
          id: 'einfuelltrichter',
          photo: 'teil-einfuelltrichter',
          name: 'Einfülltrichter',
          text: 'Trichter, über den die Trommel im Werk befüllt wird.',
          material: '[[PRÜFEN: Material]]',
        },
        {
          id: 'auslaufschurre',
          photo: 'teil-auslaufschurre',
          name: 'Auslaufschurre',
          text: 'Leitet den Beton aus der Trommel in die Rinne.',
          material: '[[PRÜFEN: Material]]',
        },
      ],
    },
    {
      id: 'spiralschutz',
      title: 'Spiralschutz',
      intro: 'Die Mischspiralen in der Trommel verschleissen an der Kante. Ein Schutz verlängert ihre Lebensdauer.',
      items: [
        {
          id: 'spiralschutz',
          photo: 'teil-spiralschutz',
          name: 'Spiralschutz',
          text: 'Verschleissschutz für die Kanten der Mischspiralen in der Trommel.',
          material: '[[PRÜFEN: Material und Ausführung]]',
        },
      ],
    },
  ],
  /** Gilt für alle Teile, bis die Liste je Teil bestätigt ist. */
  fits: ['Intermix', 'Putzmeister', 'Cifa', 'Stetter', 'Liebherr', 'Belmix', 'Peter'],
  fitsReview: '[[PRÜFEN: passende Marken und Typen je Teil]]',
};
