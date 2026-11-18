/**
 * Die Zeichnungen (src/assets/illustrations/**\/*.svg, dazu die freigestellten Bilder der Karten
 * karten/*.webp) nach Schlüssel – EINE Stelle für Fragen, Karten und alles, was eine Zeichnung
 * beim Namen nennt («spezial-krane», «menu/trommeltausch», «karten/kran-kurve»). Ein unbekannter Schlüssel bricht den Build ab, statt still
 * ein leeres Bild zu zeigen; gibt es einen Schlüssel in beiden Formen, bricht er ebenso ab.
 */
const illos = import.meta.glob<string>(['../assets/illustrations/**/*.svg', '../assets/illustrations/karten/*.webp'], { eager: true, query: '?url', import: 'default' });

export const illustration = (key: string, who = 'Zeichnung'): string => {
  const found = ['svg', 'webp'].map((ext) => illos[`../assets/illustrations/${key}.${ext}`]).filter(Boolean);
  if (found.length === 0) throw new Error(`${who}: Zeichnung «${key}» fehlt in src/assets/illustrations/.`);
  if (found.length > 1) throw new Error(`${who}: Zeichnung «${key}» gibt es als .svg und als .webp – eine genügt.`);
  return found[0];
};
