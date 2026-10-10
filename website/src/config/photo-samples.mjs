// @ts-check
/**
 * ►►► Beispielbilder – Platzhalter mit Bild, bis echte Fotos da sind. ◄◄◄
 *
 * Frei lizenzierte Fotos aus Wikimedia Commons (CC0, gemeinfrei, CC BY, CC BY-SA), geholt mit
 * scripts/sample-photos.mjs (in GitHub Actions – die Arbeitsumgebung hat keinen Zugang zu
 * Bildquellen). Sie zeigen, wie die Seite mit Bildern wirkt; sie zeigen NICHT INEXXIO.
 *
 * Darum gilt dreierlei:
 *  - jedes trägt sichtbar das Wort «Beispielbild» und einen Alt-Text, der sagt, was WIRKLICH
 *    zu sehen ist (nicht «Clemens Fritsche …» unter dem Foto einer fremden Halle);
 *  - der Bildnachweis (Urheber, Lizenz, Quelle) steht im Impressum, wie CC BY/BY-SA es
 *    verlangen;
 *  - im Modus «live» bricht der Build ab, solange ein Beispielbild verwendet wird – genau wie
 *    bei einem fehlenden Foto. Ein echtes Foto in photos.mjs (`file`) ersetzt das Beispiel.
 *
 * @typedef {{ file: string, alt: string, author: string, license: string, licenseUrl: string, source: string, title: string }} Sample
 */
// Urheber, Lizenz und Quelle so, wie Commons sie liefert (eingetragen von scripts/sample-photos.mjs).
import credits from './photo-credits.json' with { type: 'json' };

/** Was auf dem Beispielbild zu sehen ist – je Bildstelle. */
const ALT = {
  'pruefung-hallenkran': 'Gelbe Brückenkrane in einer Produktionshalle, ein Mitarbeiter mit Steuergerät',
  'reparatur-vor-ort': 'Roter Brückenkran in einer hellen Werkhalle',
  'heukran-einsatz': 'Heukran in einer Scheune (Rougemont VD)',
  'typenschild-hs': 'Typenschild an einer Maschine',
  'fahrmischer-werkstatt': 'Fahrmischer in einer Halle',
  'teil-auslaufrinne': 'Heck eines Fahrmischers mit Auslaufrinne auf einer Baustelle',
  'teil-verlaengerungsrinne': 'Fahrmischer auf einer Baustelle',
  'teil-einfuelltrichter': 'Betonwerk mit Fahrmischern (Unterengstringen ZH)',
  'teil-auslaufschurre': 'Fahrmischer mit Betonpumpe vor einem Gebäude',
  'teil-spiralschutz': 'Trommel eines kleinen Betonmischers',
  'clemens-heiri-quer': 'Werkhalle von aussen',
  'werkstatt-aussen': 'Werkstattgebäude von aussen',
  'servicefahrzeug': 'Kleinbus auf einer Strasse in Basel',
  'portraet-clemens': 'Umlenkrolle mit Kranhaken',
  'team': 'Werkhalle mit Arbeitsplätzen',
  'arbeit-werkstatt': 'Schweisser bei der Arbeit in einer Werkstatt',
};


/** @type {Record<string, Sample>} */
export const samples = Object.fromEntries(
  Object.entries(credits).map(([id, c]) => {
    const alt = ALT[/** @type {keyof typeof ALT} */ (id)];
    if (!alt) throw new Error(`Beispielbild «${id}»: Alt-Text fehlt in photo-samples.mjs.`);
    return [id, {
      file: `samples/${id}.jpg`,
      alt: `Beispielbild: ${alt}`,
      author: c.author,
      license: c.license,
      licenseUrl: c.licenseUrl,
      source: c.page,
      title: c.file.replace(/^File:/, '').replace(/\.[a-z]+$/i, ''),
    }];
  }),
);
