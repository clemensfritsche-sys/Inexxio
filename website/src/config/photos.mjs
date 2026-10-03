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
 * Nur echte Fotos: Werkstatt, Team bei der Arbeit, Krane im Einsatz. Keine Stockfotos mit
 * Menschen, keine KI-Bilder.
 *
 * @typedef {{ alt: string, brief: string, ratio: '3/2' | '4/3' | '4/5' | '1/1' | '16/9', file?: string, feature?: string }} Photo
 */

/** @type {Record<string, Photo>} */
export const photos = {
  'pruefung-hallenkran': {
    alt: 'Techniker prüft einen Brückenkran in einer Produktionshalle',
    brief: 'Techniker bei der Prüfung eines Hallenkrans (Brückenkran), Hubwerk und Laufkatze im Bild, natürliches Licht, quer',
    ratio: '4/3',
  },
  'reparatur-vor-ort': {
    alt: 'Techniker arbeitet an der Steuerung eines Hallenkrans',
    brief: 'Techniker bei einer Reparatur vor Ort: geöffneter Schaltschrank oder Hubwerk eines Hallenkrans, quer',
    ratio: '4/3',
  },
  'steuerung-funk': {
    alt: 'Funkfernsteuerung und Kransteuerung im Detail',
    brief: 'Detail: Funkfernsteuerung in der Hand, dahinter der Kran; alternativ Steuerung mit Frequenzumrichter im Schaltschrank, quer',
    ratio: '4/3',
  },
  'heukran-einsatz': {
    alt: 'HS-Heukran im Einsatz auf einem Landwirtschaftsbetrieb',
    brief: 'HS-Heukran (Greifer mit Heu) im Einsatz in einer Scheune, Betriebsleiter an der Steuerung, quer',
    ratio: '4/3',
  },
  'typenschild-hs': {
    alt: 'Typenschild einer HS-Krananlage mit Typ und Baujahr',
    brief: 'Typenschild eines HS-Krans, gut lesbar (Typ, Baujahr, Nummer), Detail',
    ratio: '4/3',
  },
  'ersatzteillager': {
    alt: 'Ersatzteillager mit Greifern, Auslegern und Fahrwerken',
    brief: 'Ersatzteillager in Tuttwil: Regale mit Greifern, Auslegern, Fahrwerken und Drehtürmen, quer',
    ratio: '3/2',
  },
  'fahrmischer-werkstatt': {
    alt: 'Fahrmischer in der Werkstatt mit geöffneter Trommel',
    brief: 'Fahrmischer in der Werkstatt, Trommel offen bzw. Einstiegsluke geöffnet, Techniker im Bild, quer',
    ratio: '4/3',
  },
  'verschleissteile-detail': {
    alt: 'Verschleissteile für Fahrmischer: Rinne, Schurre und Spiralschutz',
    brief: 'Detail Verschleissteile: neue Rinne, Schurre und Spiralschutz nebeneinander auf der Werkbank, quer',
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
    alt: 'Clemens Fritsche und Heiri Steiner vor der Werkstatt in Tuttwil',
    brief: 'Clemens Fritsche und Heiri Steiner gemeinsam vor der Werkstatt in Tuttwil, Querformat',
    ratio: '3/2',
  },
  'clemens-heiri-hoch': {
    alt: 'Clemens Fritsche und Heiri Steiner vor der Werkstatt in Tuttwil',
    brief: 'Clemens Fritsche und Heiri Steiner gemeinsam vor der Werkstatt in Tuttwil, Hochformat',
    ratio: '4/5',
  },
  'werkstatt-aussen': {
    alt: 'Werkstatt von INEXXIO in Tuttwil (Wängi TG) von aussen',
    brief: 'Werkstatt in Tuttwil von aussen, mit Zufahrt und Beschriftung, quer',
    ratio: '3/2',
  },
  'servicefahrzeug': {
    alt: 'Servicefahrzeug von INEXXIO',
    brief: 'Servicefahrzeug, beschriftet, vor einer Kundenhalle oder der Werkstatt, quer',
    ratio: '3/2',
  },
  'portraet-clemens': {
    alt: 'Clemens Fritsche, Geschäftsführer',
    brief: 'Porträt Clemens Fritsche, hoch, neutraler Hintergrund, Arbeitskleidung oder Hemd',
    ratio: '4/5',
  },
  'team': {
    alt: 'Das Team von INEXXIO in der Werkstatt',
    brief: 'Teamfoto in der Werkstatt (nur mit Einverständnis aller Abgebildeten), quer',
    ratio: '3/2',
    feature: 'team',
  },
  'vorher-kran': {
    alt: 'Kransteuerung vor der Modernisierung',
    brief: 'Vorher/Nachher-Paar 1/2: ältere Kransteuerung bzw. Hängetaster vor der Modernisierung (gleicher Bildausschnitt wie «nachher»)',
    ratio: '4/3',
    feature: 'beforeAfter',
  },
  'nachher-kran': {
    alt: 'Kransteuerung nach der Modernisierung mit Funkfernsteuerung',
    brief: 'Vorher/Nachher-Paar 2/2: dieselbe Anlage nach der Modernisierung (Funk, Umrichter), gleicher Bildausschnitt',
    ratio: '4/3',
    feature: 'beforeAfter',
  },
  'arbeit-werkstatt': {
    alt: 'Mechaniker bei der Arbeit an einem Kranteil in der Werkstatt',
    brief: 'Mechaniker bei der Arbeit (Schweissen oder Montage an einem Kranteil) in der Werkstatt, quer',
    ratio: '4/3',
  },
};

/** @param {string} id */
export function photo(id) {
  const p = photos[id];
  if (!p) throw new Error(`Unbekanntes Foto «${id}» – nicht in src/config/photos.mjs.`);
  return p;
}
