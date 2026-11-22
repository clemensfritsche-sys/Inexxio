/**
 * ►►► **Die Sprache von Konto und Anmeldung – die EINE Stelle.** ◄◄◄
 *
 * Das ERP ist bewusst deutsch. Konto und Anmeldung sieht auch der Kunde – sie sprechen die Sprache
 * der Website-Seite, von der er kommt. Welche das ist, entscheidet EINE Regel im ausgelieferten HTML
 * (`components/layout/site-shell.ShellLanguage`): sie setzt `html[data-lang]`; hier wird es nur
 * gelesen. Ohne das Zeichen (ERP, Vorab-HTML) ist es Deutsch.
 *
 * Wie auf der Website ist der **deutsche Text der Schlüssel** (`src/i18n/<sprache>.json`,
 * «Deutsch → Übersetzung»): `t('Gespeichert')`, mit Werten `t('Seit {tag}', { tag })`. Fehlt eine
 * Übersetzung, bricht der Wächter ab (`scripts/i18n.test.mjs`) – keine Sprache bleibt still zurück.
 */
import { useCallback, useSyncExternalStore } from 'react';
import fr from '@/i18n/fr.json';
import en from '@/i18n/en.json';
import it from '@/i18n/it.json';

/** Die Sprachen – dieselben wie die der Website (Wächter `scripts/i18n.test.mjs`). */
export type Lang = 'de' | 'fr' | 'en' | 'it';
const DICTS: Record<Exclude<Lang, 'de'>, Record<string, string>> = { fr, en, it };
const isLang = (l: string | undefined): l is Exclude<Lang, 'de'> => !!l && l in DICTS;

/** Die Sprache dieser Seite: `html[data-lang]`, sonst Deutsch. */
export function currentLang(): Lang {
  if (typeof document === 'undefined') return 'de';
  const l = document.documentElement.dataset.lang;
  return isLang(l) ? l : 'de';
}

/** Werte einsetzen: «Seit {tag}» + `{ tag: '3.11.2026' }`. */
function fill(text: string, values?: Record<string, string | number>): string {
  return values ? text.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m)) : text;
}

export type T = (de: string, values?: Record<string, string | number>) => string;

/** Übersetzen ohne React (Fehlertexte, Hilfsfunktionen) – in der Sprache dieser Seite. */
export const t: T = (de, values) => {
  const l = currentLang();
  return fill((l !== 'de' && DICTS[l][de]) || de, values);
};

const never = () => () => {};

/**
 * Für Bauteile: im Vorab-HTML Deutsch, im Browser die Sprache der Seite – ohne Abweichung beim
 * Übernehmen (React rendert danach einmal in der richtigen Sprache).
 */
export function useT(): T {
  const lang = useSyncExternalStore<Lang>(never, currentLang, () => 'de');
  return useCallback<T>((de, values) => fill((lang !== 'de' && DICTS[lang][de]) || de, values), [lang]);
}

/** Ein Link innerhalb von Konto und Anmeldung, der die Sprache behält. */
export function withLang(href: string): string {
  const l = currentLang();
  // Deutsch braucht kein Zeichen; eine Seite der Website in der Sprache trägt sie schon im Pfad.
  if (l === 'de' || href === `/${l}` || href.startsWith(`/${l}/`)) return href;
  const [path, hash] = href.split('#');
  return `${path}${path.includes('?') ? '&' : '?'}lang=${l}${hash !== undefined ? `#${hash}` : ''}`;
}
