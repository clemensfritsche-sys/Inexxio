import { isStaff } from './record-status';

/**
 * **Wohin nach der Anmeldung – EINE Antwort für alle drei Wege** (Dialog, Route, Magic Link).
 *
 * Nie «/»: dort steht seit Oktober 2026 die öffentliche Website (`website/`), und die kennt
 * keine Anmeldung. Wer dorthin geschickt wurde, war angemeldet und sah es nirgends – kein
 * Konto, kein ERP-Link. Ohne genanntes Ziel geht es darum an den **Startplatz der Rolle**:
 * ins ERP, wer dort arbeitet, sonst ins eigene Konto.
 *
 * Navigiert wird **hart** (`window.location`), nicht über den Next-Router: «/» und alle
 * Website-Seiten sind keine Next-Seiten, und `router.push` auf sie endet in einer
 * nachgelagerten Seitennavigation, die eine zweite, spätere Navigation überholt (genau so
 * landete der Login auf der Website statt im ERP).
 */
export const REDIRECT_KEY = 'inexxio_login_redirect';

/** Startplatz einer Rolle. */
export function startPage(role: string | null | undefined): string {
  return isStaff(role) ? '/erp' : '/konto';
}

/**
 * Nur ein Pfad im eigenen Haus – nie eine fremde Adresse (`//…`), nie zurück zur Anmeldung
 * und nie die Startseite der Website (siehe oben).
 */
export function isSafeTarget(path: string | null | undefined): path is string {
  return !!path && path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/\\')
    && path !== '/' && !/^\/login(?:[/?#]|$)/.test(path);
}

/** Das gemerkte `?from=` für den Magic Link aufbewahren (er öffnet oft einen neuen Tab). */
export function rememberFrom(): void {
  const from = new URLSearchParams(window.location.search).get('from');
  if (isSafeTarget(from)) localStorage.setItem(REDIRECT_KEY, from);
}

/** Ziel nach der Anmeldung: `?from=` · gemerktes Ziel · Vorgabe des Aufrufers · Startplatz. */
export function loginTarget(role: string | null | undefined, fallback?: string): string {
  const from = new URLSearchParams(window.location.search).get('from');
  const saved = localStorage.getItem(REDIRECT_KEY);
  localStorage.removeItem(REDIRECT_KEY);
  return [from, saved, fallback].find(isSafeTarget) ?? startPage(role);
}

/** Hart dorthin – siehe oben, warum nicht über den Router. */
export function goTo(path: string): void {
  window.location.replace(path);
}
