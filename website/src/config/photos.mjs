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
 * Fotos: Betrieb, Team bei der Arbeit, Krane im Einsatz – echt oder generiert. Generierte Bilder
 * nur ohne echte Personen und Orte (keine erfundenen Mitarbeitenden, kein erfundener Betrieb);
 * wer oder was echt sein soll, wird fotografiert. Keine Stockfotos mit Menschen.
 * Bis dahin steht dort der graue Rahmen «Foto fehlt» – im Modus «live» ein Fehler.
 *
 * Ein Video dazu: Datei (MP4, H.264, ohne Ton, kurz, ≤ 8 MB) nach public/video/ legen, daneben
 * ihr erstes Bild als Standbild mit gleichem Namen (.webp, z. B.
 * `ffmpeg -i buehne.mp4 -frames:v 1 -vf scale=1280:-2 buehne.webp`), und hier bei `video`
 * eintragen. In Bühne und Seitenkopf steht dann das Video statt des Fotos (components/Media.astro).
 *
 * @typedef {{ alt: string, brief: string, ratio: '3/2' | '4/3' | '4/5' | '1/2' | '1/1' | '16/9', file?: string, video?: string }} Photo
 */

/** @type {Record<string, Photo>} */
export const photos = {
  'hafen-bootskran': {
    alt: 'Bootskran an einem Hafensteg hebt ein Segelboot aus dem Wasser',
    brief: 'Boots- oder Mastkran an einem Schweizer Hafen oder Segelclub, Boot am Haken über dem Wasser, Steg und Masten im Hintergrund, quer',
    ratio: '4/3',
  },
  'pruefung-hallenkran': {
    file: 'pruefung-hallenkran.jpg',
    alt: 'Techniker prüft auf einer Arbeitsbühne das Hubwerk eines Brückenkrans in einer Produktionshalle',
    brief: 'Techniker bei der Prüfung eines Hallenkrans (Brückenkran), Hubwerk und Laufkatze im Bild, natürliches Licht, quer',
    ratio: '4/3',
  },
  'reparatur-vor-ort': {
    file: 'reparatur-vor-ort.webp',
    alt: 'Techniker arbeitet am offenen Schaltschrank eines roten Brückenkrans in einer Halle',
    brief: 'Industriekran (Brückenkran) in einer Halle, Techniker bei Service oder Reparatur am Hubwerk oder Schaltschrank, quer',
    ratio: '4/3',
  },
  'heukran-einsatz': {
    file: 'heukran-einsatz.webp',
    video: 'buehne.mp4',
    alt: 'Heukrananlage mit vollem Greifer im Einsatz in einer Scheune',
    brief: 'Heukrananlage im Einsatz in einer Scheune, Greifer voll mit Heu, Betriebsleiter an der Steuerung, quer',
    ratio: '4/3',
  },
  // Krane nach Mass, Belege (sichtbar erst mit `features.craneReferences`) – je ein echtes Projekt.
  'kran-kurve': {
    alt: 'Kranfahrbahn, die in einer Scheune oder Halle um die Ecke biegt',
    brief: 'Kran nach Mass mit Kurvenfahrbahn: die Fahrbahn biegt sichtbar um eine Ecke, Katze oder Greifer in der Kurve, Gebäude erkennbar, quer',
    ratio: '4/3',
  },
  'kran-steigung': {
    alt: 'Kranfahrbahn unter einem ansteigenden Dach',
    brief: 'Kran nach Mass in einem Gebäude mit Steigung: Fahrbahn folgt dem ansteigenden Dach oder Boden, Steigung gut sichtbar, quer',
    ratio: '4/3',
  },
  'kran-versatz': {
    alt: 'Kranfahrbahn unter einer Decke mit Versatz und Unterzug',
    brief: 'Kran nach Mass unter einer Decke mit Höhensprung oder Unterzug: Aufhängungen unterschiedlich lang, die Fahrbahn läuft durch, quer',
    ratio: '4/3',
  },
  'kran-eng': {
    alt: 'Kompakter Kran mit Greifer zwischen Stützen in einem engen Raum',
    brief: 'Kompakter Kran in einem engen, verwinkelten Raum mit Stützen oder Nischen, der Greifer erreicht eine Ecke, quer',
    ratio: '4/3',
  },
  // Heukrananlagen, «Funk statt Kabine» (generiert, ohne echte Person oder echten Ort).
  'heukran-funk': {
    file: 'heukran-funk.jpg',
    alt: 'Landwirt steht neben dem Heuwagen in der Scheune, schaut zum Greifer hinauf und hält den Funksender',
    brief: 'Landwirt am Boden der Scheune neben dem Heuwagen mit Funksender in der Hand, darüber der Heukran mit vollem Greifer, keine Kabine, hoch',
    ratio: '4/5',
  },
  // Heukrananlagen, «Funk statt Kabine», dunkle Karte (generiert).
  'funk-sicht': {
    file: 'funk-sicht.jpg',
    alt: 'Blick vom Scheunenboden hinauf zum vollen Heugreifer unter dem Dachstuhl, vorne die Hand mit dem Funksender',
    brief: 'Blick vom Scheunenboden steil nach oben zum Heugreifer unter dem dunklen Dachstuhl, Lichtstrahlen, vorne unscharf die Hand mit dem Funksender, hoch',
    ratio: '4/5',
  },
  'fahrmischer-werkstatt': {
    file: 'fahrmischer-werkstatt.jpg',
    alt: 'Techniker steht auf einer Leiter am Heck eines Fahrmischers in einer hellen Halle, die Trommelluke ist offen',
    brief: 'Fahrmischer in der Halle, Trommel offen bzw. Einstiegsluke geöffnet, Techniker im Bild, quer',
    ratio: '4/3',
  },
  'teil-auslaufrinne': {
    file: 'teil-auslaufrinne.jpg',
    alt: 'Stählerne Auslaufrinne für Fahrmischer auf einer Werkbank aus Stahl',
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
  handschlag: {
    alt: 'Heiri Steiner und Clemens Fritsche geben sich vor dem Betrieb in Tuttwil die Hand',
    brief: 'Heiri Steiner und Clemens Fritsche beim Handschlag, freigestellt (transparenter Grund), hoch – heute steht dort portraet-clemens',
    ratio: '4/5',
  },
  'werkstatt-aussen': {
    alt: 'Betrieb von INEXXIO in Tuttwil (Wängi TG) von aussen',
    brief: 'Betriebsgebäude in Tuttwil von aussen, mit Zufahrt und Beschriftung, quer',
    ratio: '3/2',
  },
  'portraet-clemens': {
    file: 'portraet-clemens.png',
    alt: 'Clemens Fritsche',
    brief: 'Clemens Fritsche, freigestellt, Kopf bis Hüfte (Ausschnitt aus portraet-clemens-stehend)',
    ratio: '4/5',
  },
  'portraet-clemens-stehend': {
    file: 'portraet-clemens-stehend.png',
    alt: 'Clemens Fritsche',
    brief: 'Clemens Fritsche stehend, freigestellt (transparenter Grund), hoch',
    ratio: '1/2',
  },
  'team': {
    alt: 'Das Team von INEXXIO bei der Arbeit',
    brief: 'Teamfoto im Betrieb (nur mit Einverständnis aller Abgebildeten), quer',
    ratio: '3/2',
  },
  // Garantien, Karte «Die erste Inspektion ist gratis» (generiert, ohne echte Person oder echten Betrieb).
  'erste-inspektion': {
    file: 'erste-inspektion.jpg',
    alt: 'Techniker auf einer Arbeitsbühne prüft Haken und Unterflasche eines roten Brückenkrans, in der Hand ein Tablet',
    brief: 'Kran-Techniker auf einer Arbeitsbühne prüft Haken und Hubwerk eines roten Brückenkrans in einer hellen Produktionshalle, Tablet in der Hand, quer',
    ratio: '16/9',
  },
  'arbeit-werkstatt': {
    file: 'arbeit-werkstatt.webp',
    alt: 'Schweisser mit Schutzhelm an einer roten Stahlkonstruktion, Funken fliegen',
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
