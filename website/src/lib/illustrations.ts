/**
 * Die Zeichnungen (src/assets/illustrations/**\/*.svg, dazu die freigestellten Bilder der Karten
 * karten/*.webp) nach Schlüssel – EINE Stelle für Fragen, Karten und alles, was eine Zeichnung
 * beim Namen nennt («spezial-krane», «menu/trommeltausch», «karten/kran-kurve»). Ein unbekannter
 * Schlüssel bricht den Build ab, statt still ein leeres Bild zu zeigen; gibt es einen Schlüssel in
 * beiden Formen, bricht er ebenso ab.
 *
 * Zwei Fragen, zwei Funktionen:
 *  - `illustration(key)` – die Zeichnung selbst (die Fragen, `FaqStage`, behalten ihre Zeichnungen).
 *  - `picture(key)` – das Bild, das auf Karten und Bühnen für die Zeichnung steht (Entscheid
 *    November 2026: Bilder statt grober Zeichnungen, ausser in den Fragen). Steht für den Schlüssel
 *    ein Bild in `PICTURES` (Titelbild im Stil «grau gezeichnet, rot und echt» oder ein
 *    freigestelltes Bild der Karten), kommt dieses, klein gerechnet; sonst die Zeichnung.
 *    `foto/<name>` nennt ein Foto aus src/assets/photos (die Karte zeigt es dann mit runden Ecken).
 */
import { getImage } from 'astro:assets';
import type { ImageMetadata } from 'astro';

const illos = import.meta.glob<string>(['../assets/illustrations/**/*.svg', '../assets/illustrations/karten/*.webp'], { eager: true, query: '?url', import: 'default' });
const rasters = import.meta.glob<{ default: ImageMetadata }>(['../assets/illustrations/*-titel.webp', '../assets/illustrations/karten/*.webp'], { eager: true });
const photos = import.meta.glob<{ default: ImageMetadata }>('../assets/photos/*.{jpg,webp,png}', { eager: true });

export const illustration = (key: string, who = 'Zeichnung'): string => {
  const found = ['svg', 'webp'].map((ext) => illos[`../assets/illustrations/${key}.${ext}`]).filter(Boolean);
  if (found.length === 0) throw new Error(`${who}: Zeichnung «${key}» fehlt in src/assets/illustrations/.`);
  if (found.length > 1) throw new Error(`${who}: Zeichnung «${key}» gibt es als .svg und als .webp – eine genügt.`);
  return found[0];
};

/** Zeichnung → Bild (Pfad unter src/assets/illustrations, ohne Endung .webp). */
const PICTURES: Record<string, string> = {
  'menu/trommeltausch': 'trommel-titel',
  'menu/verschleissteile': 'teile-titel',
  'menu/kranservice': 'kranservice-titel',
  'menu/krane-nach-mass': 'nachmass-titel',
  'menu/heukrananlagen': 'heukran-titel',
  'menu/service': 'service-titel',
  'menu/ratgeber': 'ratgeber-titel',
  'menu/karriere': 'karriere-titel',
  'menu/ueber': 'ueber-titel',
  'menu/kontakt': 'kontakt-titel',
  'trommel-neu': 'fahrzeug-titel',
  'spezial-krane': 'karten/spezial-krane',
  'spezial-fahrzeuge': 'karten/spezial-fahrzeuge',
  'spezial-baumaschinen': 'karten/spezial-baumaschinen',
};

export const picture = async (key: string, who = 'Bild', width = 960): Promise<string> => {
  if (key.startsWith('foto/')) {
    const name = key.slice(5);
    const hit = Object.entries(photos).find(([path]) => path.replace(/\.(jpg|webp|png)$/, '').endsWith(`/${name}`));
    if (!hit) throw new Error(`${who}: Foto «${name}» fehlt in src/assets/photos/.`);
    const img = hit[1].default;
    return (await getImage({ src: img, width: Math.min(width, img.width), format: 'webp', quality: 78 })).src;
  }
  const name = PICTURES[key] ?? (key.startsWith('karten/') ? key : undefined);
  if (!name) return illustration(key, who);
  const img = rasters[`../assets/illustrations/${name}.webp`]?.default;
  if (!img) throw new Error(`${who}: Bild «${name}.webp» für «${key}» fehlt in src/assets/illustrations/.`);
  return (await getImage({ src: img, width: Math.min(width, img.width), format: 'webp', quality: 80 })).src;
};
