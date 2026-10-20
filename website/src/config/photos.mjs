// @ts-check
/**
 * ►►► Die Fotoliste – zugleich Bildregister der Website. ◄◄◄
 *
 * Jede Bildstelle der Website nennt eine ID von hier. Solange `file` fehlt, zeigt sie einen
 * grauen Rahmen im richtigen Seitenverhältnis mit der Bildbeschreibung (`brief`) – und
 * genau diese Beschreibungen sind die Fotoliste in OFFENE_PUNKTE.md.
 *
 * Ein echtes Foto einsetzen: Datei nach src/assets/photos/ legen (JPG, sprechender Name,
 * z. B. kranpruefung-brueckenkran-tuttwil.jpg, lange Seite ≥ 2400 px), hier bei `file`
 * eintragen. AVIF/WebP, srcset und feste Masse erzeugt der Build.
 *
 * Nur echte Fotos: Betrieb, Team bei der Arbeit, Krane im Einsatz. Keine Stockfotos mit
 * Menschen, keine KI-Bilder. Bis dahin füllt ein gekennzeichnetes Beispielbild die Stelle
 * (config/photo-samples.mjs) – im Modus «live» ist das, wie ein fehlendes Foto, ein Fehler.
 *
 * Ein Video dazu: Datei (MP4, H.264, ohne Ton, kurz, ≤ 8 MB) nach public/video/ legen und hier
 * bei `video` eintragen. Es läuft stumm in Schleife über dem Foto, das Foto bleibt Standbild
 * (vor dem Laden, bei «reduzierter Bewegung» und ohne Video).
 *
 * @typedef {{ alt: string, brief: string, ratio: '3/2' | '4/3' | '4/5' | '1/1' | '16/9', file?: string, video?: string }} Photo
 */

/** @type {Record<string, Photo>} */
export const photos = {
  'hafen-bootskran': {
    alt: 'Bootskran an einem Hafensteg hebt ein Segelboot aus dem Wasser',
    brief: 'Boots- oder Mastkran an einem Schweizer Hafen oder Segelclub, Boot am Haken über dem Wasser, Steg und Masten im Hintergrund, quer',
    ratio: '4/3',
  },
  'pruefung-hallenkran': {
    alt: 'Techniker prüft einen Brückenkran in einer Produktionshalle',
    brief: 'Techniker bei der Prüfung eines Hallenkrans (Brückenkran), Hubwerk und Laufkatze im Bild, natürliches Licht, quer',
    ratio: '4/3',
  },
  'reparatur-vor-ort': {
    alt: 'Industriekran in einer Halle, Techniker bei der Arbeit am Hubwerk',
    brief: 'Industriekran (Brückenkran) in einer Halle, Techniker bei Service oder Reparatur am Hubwerk oder Schaltschrank, quer',
    ratio: '4/3',
  },
  'heukran-einsatz': {
    alt: 'Heukrananlage mit vollem Greifer im Einsatz in einer Scheune',
    brief: 'Heukrananlage im Einsatz in einer Scheune, Greifer voll mit Heu, Betriebsleiter an der Steuerung, quer',
    ratio: '4/3',
  },
  'fahrmischer-werkstatt': {
    alt: 'Fahrmischer in der Halle mit geöffneter Trommel',
    brief: 'Fahrmischer in der Halle, Trommel offen bzw. Einstiegsluke geöffnet, Techniker im Bild, quer',
    ratio: '4/3',
  },
  'teil-auslaufrinne': {
    alt: 'Auslaufrinne für Fahrmischer',
    brief: 'Produktfoto Auslaufrinne, freigestellt auf hellem Grund oder auf der Werkbank, quer',
    ratio: '4/3',
  },
  'teil-verlaengerungsrinne': {
    alt: 'Verlängerungsrinne für Fahrmischer',
    brief: 'Produktfoto Verlängerungsrinne, quer',
    ratio: '4/3',
  },
  'teil-einfuelltrichter': {
    alt: 'Einfülltrichter eines Fahrmischers',
    brief: 'Produktfoto Einfülltrichter, quer',
    ratio: '4/3',
  },
  'teil-auslaufschurre': {
    alt: 'Auslaufschurre eines Fahrmischers',
    brief: 'Produktfoto Auslaufschurre, quer',
    ratio: '4/3',
  },
  'teil-spiralschutz': {
    alt: 'Spiralschutz für die Mischspiralen eines Fahrmischers',
    brief: 'Detail Spiralschutz an der Trommelspirale bzw. als Einzelteil, quer',
    ratio: '4/3',
  },
  'clemens-heiri-quer': {
    alt: 'Clemens Fritsche und Heiri Steiner vor dem Betrieb in Tuttwil',
    brief: 'Clemens Fritsche und Heiri Steiner gemeinsam vor dem Betrieb in Tuttwil, Querformat',
    ratio: '3/2',
  },
  'werkstatt-aussen': {
    alt: 'Betrieb von INEXXIO in Tuttwil (Wängi TG) von aussen',
    brief: 'Betriebsgebäude in Tuttwil von aussen, mit Zufahrt und Beschriftung, quer',
    ratio: '3/2',
  },
  'portraet-clemens': {
    file: 'portraet-clemens.png',
    alt: 'Clemens Fritsche',
    brief: 'Porträt Clemens Fritsche – rund freigestellt',
    ratio: '1/1',
  },
  'team': {
    alt: 'Das Team von INEXXIO bei der Arbeit',
    brief: 'Teamfoto im Betrieb (nur mit Einverständnis aller Abgebildeten), quer',
    ratio: '3/2',
  },
  'arbeit-werkstatt': {
    alt: 'Schweissarbeit an einer Stahlkonstruktion bei INEXXIO',
    brief: 'Schweissarbeit oder Stahlkonstruktion bei INEXXIO in Tuttwil, Funken und Schutzschild, quer',
    ratio: '4/3',
  },
};

/** @param {string} id */
export function photo(id) {
  const p = photos[id];
  if (!p) throw new Error(`Unbekanntes Foto «${id}» – nicht in src/config/photos.mjs.`);
  return p;
}
