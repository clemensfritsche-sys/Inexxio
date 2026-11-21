/**
 * Anmeldezustand in der Kopfzeile – nur ANZEIGE (WEBSITE_PLAN §7.5, Anzeige-Cache).
 *
 * Quelle ist der Anzeige-Cache, den das Konto-/ERP-Frontend (frontend/, gleiche Domain)
 * nach jeder Anmeldung schreibt und beim Abmelden löscht (WEBSITE_PLAN §7.5, S1/S2).
 * Welcher Zustand sichtbar ist (Anmelden · Profil · ERP), hat scripts/early.js schon vor dem
 * ersten Zeichnen entschieden (`html[data-account]`); hier kommen nur Profilbild bzw. Initialen,
 * Name und E-Mail dazu. Fehlt etwas oder ist der Speicher gesperrt, bleibt es beim Symbol – nichts
 * bricht. Kein Token, keine ID, keine Anfrage an den Server.
 *
 * Die Schlüssel sind ein Spiegel der Frontend-Quellen – geprüft von scripts/account.test.mjs.
 */
const ACCOUNT_KEYS = {
  role: 'inexxio_user_role',
  name: 'inexxio_user_fullname',
  contact: 'inexxio_user_contact',
  photo: 'inexxio_user_photo',
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
export function accountInfo(): { name: string; photo: string; contact: AccountContact } | null {
  if (!read(ACCOUNT_KEYS.role)) return null;
  let contact: AccountContact = {};
  try {
    const raw = read(ACCOUNT_KEYS.contact);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    if (parsed && typeof parsed === 'object') contact = parsed as AccountContact;
  } catch { /* unlesbar – ohne Kontakt weiter */ }
  return { name: (read(ACCOUNT_KEYS.name) ?? '').trim(), photo: (read(ACCOUNT_KEYS.photo) ?? '').trim(), contact };
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (!parts.length) return '';
  const first = parts[0][0] ?? '';
  const last = parts.length > 1 ? parts[parts.length - 1][0] ?? '' : '';
  return (first + last).toUpperCase();
}

/**
 * Rolle → `html[data-account]` – dieselbe Regel wie scripts/early.js (das vor dem ersten
 * Zeichnen läuft und nichts importieren kann). Hier für den Fall, dass sich der Cache NACH dem
 * Laden ändert: im Konto/ERP schreibt ihn das Frontend nach der Anmeldung und ruft dann
 * `window.inexxioShell.account()`. Beide Fassungen prüft scripts/account.test.mjs.
 */
function syncRole(): void {
  const d = document.documentElement;
  let role: string | null = null;
  try { role = localStorage.getItem(ACCOUNT_KEYS.role); } catch { /* gesperrt */ }
  if (role) d.dataset.account = role === 'admin' || role === 'employee' ? 'staff' : 'user';
  else delete d.dataset.account;
}

/** «Anmelden» führt nach der Anmeldung dorthin zurück, wo man war (frontend/lib/login-target). */
function loginReturns(): void {
  const here = location.pathname + location.search;
  if (here.startsWith('/login')) return;
  document.querySelectorAll<HTMLAnchorElement>('a[href^="/login"]').forEach((a) => {
    a.href = `/login?from=${encodeURIComponent(here)}`;
  });
  loginOverlay();
}

/**
 * ►►► **Anmelden als Fenster ÜBER der Seite** (Rückmeldung 21.11.2026). ◄◄◄ Auf der Website
 * (`html[data-site]`) öffnet «Anmelden» die Anmeldung des ERP (`/login`, dieselbe Seite wie
 * sonst) in einem durchsichtigen Rahmen – die Seite bleibt dahinter stehen, nur leicht
 * abgedeckt. Die Anmeldung spricht über `postMessage` (`ready`, `close`); nach der Anmeldung
 * navigiert sie selbst das ganze Fenster (frontend/lib/login-target.goTo). Ohne Antwort in
 * 8 s geht es auf die Seite /login – nie ein stiller Klick.
 */
const LOGIN_FRAME = 'ix-login-frame';
let loginBound = false;
function loginOverlay(): void {
  if (loginBound || !document.documentElement.hasAttribute('data-site')) return;
  loginBound = true;
  document.addEventListener('click', (e) => {
    const a = (e.target as Element | null)?.closest?.('a[href^="/login"]') as HTMLAnchorElement | null;
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    openLogin(a.getAttribute('href') ?? '/login');
  });
  window.addEventListener('message', (e) => {
    if (e.origin !== location.origin) return;
    const frame = document.getElementById(LOGIN_FRAME) as HTMLIFrameElement | null;
    if (!frame || e.source !== frame.contentWindow) return;
    const data = e.data as { source?: string; what?: string } | null;
    if (data?.source !== 'inexxio-login') return;
    if (data.what === 'ready') { frame.style.visibility = 'visible'; frame.focus(); }
    if (data.what === 'close') frame.remove();
  });
}

function openLogin(href: string): void {
  if (document.getElementById(LOGIN_FRAME)) return;
  const frame = document.createElement('iframe');
  frame.id = LOGIN_FRAME;
  frame.title = 'Anmelden';
  frame.src = href;
  // Passkeys im Rahmen nur mit ausdrücklicher Erlaubnis (gleicher Ursprung).
  frame.allow = 'publickey-credentials-get *; publickey-credentials-create *';
  frame.setAttribute('style', 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:1000;'
    + 'background:transparent;color-scheme:normal;visibility:hidden');
  document.body.appendChild(frame);
  window.setTimeout(() => {
    if (document.getElementById(LOGIN_FRAME) === frame && frame.style.visibility !== 'visible') {
      frame.remove();
      location.href = href;
    }
  }, 8000);
}

/** Anmeldezustand neu lesen und zeigen – beim Laden und nach jeder Änderung des Caches. */
export function syncAccount(): void {
  syncRole();
  initAccount();
}

export function initAccount(): void {
  loginReturns();
  const info = accountInfo();
  if (!info || !document.documentElement.dataset.account) return;
  const ini = initials(info.name);
  // Profilbild wie im ERP (#1105) – nur ein https-Bild; sonst bleiben es die Initialen.
  const photo = /^https:\/\//.test(info.photo) ? info.photo : '';
  for (const el of document.querySelectorAll<HTMLElement>('[data-acct-initials]')) {
    if (photo) {
      const img = document.createElement('img');
      img.src = photo;
      img.alt = '';
      img.referrerPolicy = 'no-referrer';
      img.className = 'pm__avatar';
      img.addEventListener('error', () => { el.textContent = ini; }, { once: true });
      el.replaceChildren(img);
    } else if (ini) {
      el.textContent = ini;
    }
  }
  if (info.name) {
    for (const el of document.querySelectorAll<HTMLElement>('[data-acct-name]')) el.textContent = info.name;
  }
  const email = typeof info.contact.email === 'string' ? info.contact.email : '';
  for (const el of document.querySelectorAll<HTMLElement>('[data-acct-email]')) el.textContent = email;
  const company = typeof info.contact.company === 'string' ? info.contact.company : '';
  for (const el of document.querySelectorAll<HTMLElement>('[data-acct-company]')) el.textContent = company;
}
