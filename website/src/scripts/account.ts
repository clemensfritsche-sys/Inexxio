/**
 * Anmeldezustand in der Kopfzeile – nur ANZEIGE (Auftrag Kap. 6.3).
 *
 * Quelle ist der Anzeige-Cache, den das Konto-/ERP-Frontend (frontend/, gleiche Domain)
 * nach jeder Anmeldung schreibt und beim Abmelden löscht (WEBSITE_PLAN §7.5, S1/S2).
 * Welcher Zustand sichtbar ist (Anmelden · Profil · ERP), hat scripts/early.js schon vor dem
 * ersten Zeichnen entschieden (`html[data-account]`); hier kommen nur Initialen, Name und
 * E-Mail dazu. Fehlt etwas oder ist der Speicher gesperrt, bleibt es beim Symbol – nichts
 * bricht. Kein Token, keine ID, keine Anfrage an den Server.
 *
 * Die Schlüssel sind ein Spiegel der Frontend-Quellen – geprüft von scripts/account.test.mjs.
 */
export const ACCOUNT_KEYS = {
  role: 'inexxio_user_role',
  name: 'inexxio_user_fullname',
  contact: 'inexxio_user_contact',
} as const;

export interface AccountContact { email?: string; phone?: string; company?: string }

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Name und Kontakt aus dem Anzeige-Cache – nur wenn jemand angemeldet ist. */
export function accountInfo(): { name: string; contact: AccountContact } | null {
  if (!read(ACCOUNT_KEYS.role)) return null;
  let contact: AccountContact = {};
  try {
    const raw = read(ACCOUNT_KEYS.contact);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    if (parsed && typeof parsed === 'object') contact = parsed as AccountContact;
  } catch { /* unlesbar – ohne Kontakt weiter */ }
  return { name: (read(ACCOUNT_KEYS.name) ?? '').trim(), contact };
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (!parts.length) return '';
  const first = parts[0][0] ?? '';
  const last = parts.length > 1 ? parts[parts.length - 1][0] ?? '' : '';
  return (first + last).toUpperCase();
}

export function initAccount(): void {
  const info = accountInfo();
  if (!info || !document.documentElement.dataset.account) return;
  const ini = initials(info.name);
  if (ini) {
    for (const el of document.querySelectorAll<HTMLElement>('[data-acct-initials]')) el.textContent = ini;
  }
  if (info.name) {
    for (const el of document.querySelectorAll<HTMLElement>('[data-acct-name]')) el.textContent = info.name;
  }
  const email = typeof info.contact.email === 'string' ? info.contact.email : '';
  for (const el of document.querySelectorAll<HTMLElement>('[data-acct-email]')) el.textContent = email;
}
