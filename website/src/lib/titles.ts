/**
 * Die Titelbilder der Seiten – EINE Stelle für «welche Seite trägt welches Bild». Der Seitenkopf
 * (components/StageHero) zeigt es gross, das Kopf-Menü (components/Header) klein auf der Kachel der
 * Seite (Regel 23.10.2026: Titelbild vor Zeichnung; ohne Titelbild bleibt die Zeichnung).
 * Die Bilder sind freigestellte WebP in src/assets/illustrations/<name>-titel.webp.
 */
import type { ImageMetadata } from 'astro';

const files = import.meta.glob<{ default: ImageMetadata }>('../assets/illustrations/*-titel.webp', { eager: true });

/** Pfad der Seite → Name des Titelbilds (ohne «-titel.webp»). */
const TITLES: Record<string, string> = {
  '/spezialloesungen': 'spezial',
  '/krantechnik': 'kran',
  '/krantechnik/krane-nach-mass': 'nachmass',
  '/krantechnik/kranservice': 'kranservice',
  '/krantechnik/heukrananlagen': 'heukran',
  '/fahrzeugtechnik': 'fahrzeug',
  '/fahrzeugtechnik/trommeltausch': 'trommel',
  '/fahrzeugtechnik/verschleissteile': 'teile',
  '/ueber-uns': 'ueber',
};

const fileOf = (name: string): ImageMetadata => {
  const f = files[`../assets/illustrations/${name}-titel.webp`]?.default;
  if (!f) throw new Error(`Titelbild «${name}-titel.webp» fehlt in src/assets/illustrations/.`);
  return f;
};

/** Das Titelbild einer Seite, falls sie eines hat (das Menü fällt sonst auf die Zeichnung zurück). */
export const titleImage = (path: string): ImageMetadata | undefined => (TITLES[path] ? fileOf(TITLES[path]) : undefined);

/** Das Titelbild für den Seitenkopf – eine Seite mit StageHero muss eines haben. */
export const pageTitle = (path: string): ImageMetadata => {
  const img = titleImage(path);
  if (!img) throw new Error(`Seite «${path}»: kein Titelbild in lib/titles.ts eingetragen.`);
  return img;
};
