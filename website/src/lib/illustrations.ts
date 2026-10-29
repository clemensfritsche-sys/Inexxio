/**
 * Die Zeichnungen (src/assets/illustrations/**\/*.svg) nach Schlüssel – EINE Stelle für Fragen,
 * Karten und alles, was eine Zeichnung beim Namen nennt («spezial-krane», «menu/trommeltausch»).
 * Ein unbekannter Schlüssel bricht den Build ab, statt still ein leeres Bild zu zeigen.
 */
const illos = import.meta.glob<string>('../assets/illustrations/**/*.svg', { eager: true, query: '?url', import: 'default' });

export const illustration = (key: string, who = 'Zeichnung'): string => {
  const url = illos[`../assets/illustrations/${key}.svg`];
  if (!url) throw new Error(`${who}: Zeichnung «${key}» fehlt in src/assets/illustrations/.`);
  return url;
};
