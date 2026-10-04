/**
 * ►►► Kontaktdaten aus dem ERP – die Website ist sein Spiegelbild (Testnotiz #1094). ◄◄◄
 *
 * Im HTML stehen Telefon, E-Mail und Anschrift so, wie sie beim Bauen galten (für
 * Suchmaschinen und ohne JavaScript). Hier werden sie gegen die Angaben des ERP getauscht:
 * `GET /api/v1/public/contact` liefert das Unternehmen zum Land des Besuchers (IP-Adresse →
 * Land → Gebiete im ERP; ohne Treffer der Betreiber). Ändert sich im ERP eine Nummer, steht
 * sie sofort auf jeder Seite – ohne neuen Build.
 *
 * Getauscht wird nach **Wert**, nicht nach Markierung: jede Stelle, die die Nummer der
 * Vorgabe zeigt (Links, Fliesstext, Formular-Hinweise), bekommt die aus dem ERP – eine
 * neue Stelle braucht keine eigene Zeile. Die Anschrift ist mehrzeilig und wird darum dort
 * ersetzt, wo `data-erp="address"` steht. Impressum und Datenschutz (`data-erp-fixed`)
 * bleiben unberührt: dort steht der Betreiber, nicht die Gesellschaft des Besucherlandes.
 *
 * Fehlt eine Angabe im ERP oder ist der Server nicht erreichbar, bleibt die Vorgabe stehen.
 * Zwischengespeichert für fünf Minuten in sessionStorage – eine Anfrage je Besuch.
 */
interface Contact {
  name: string;
  phone: string | null;
  phone_e164: string | null;
  email: string | null;
  address_lines: string[];
}
interface Built { phone: string; e164: string; email: string; country: string }

const CACHE_KEY = 'inexxio_contact';
const TTL = 5 * 60 * 1000;

function cached(): Contact | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const { at, data } = JSON.parse(raw) as { at: number; data: Contact };
    return Date.now() - at < TTL ? data : null;
  } catch {
    return null;
  }
}

async function load(): Promise<Contact | null> {
  const hit = cached();
  if (hit) return hit;
  try {
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 4000);
    const res = await fetch('/api/v1/public/contact', { headers: { Accept: 'application/json' }, signal: ctrl.signal });
    window.clearTimeout(timer);
    if (!res.ok) return null;
    const data = (await res.json()) as Contact;
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data })); } catch { /* egal */ }
    return data;
  } catch {
    return null;
  }
}

/** Text in der Seite ersetzen – nicht in Skripten und nicht in festen Bereichen. */
function replaceText(from: string, to: string): void {
  if (!from || !to || from === to) return;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => {
      const p = n.parentElement;
      if (!p || p.closest('script, style, [data-erp-fixed]')) return NodeFilter.FILTER_REJECT;
      return n.nodeValue?.includes(from) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  const hits: Text[] = [];
  while (walker.nextNode()) hits.push(walker.currentNode as Text);
  for (const t of hits) t.nodeValue = (t.nodeValue ?? '').split(from).join(to);
}

function replaceHref(prefix: string, to: string): void {
  document.querySelectorAll<HTMLAnchorElement>(`a[href^="${prefix}"]`).forEach((a) => {
    if (a.closest('[data-erp-fixed]')) return;
    a.setAttribute('href', to + a.getAttribute('href')!.slice(prefix.length));
  });
}

export function apply(built: Built, c: Contact): void {
  if (c.phone && c.phone_e164) {
    replaceHref(`tel:${built.e164}`, `tel:${c.phone_e164}`);
    replaceText(built.phone, c.phone);
  }
  if (c.email) {
    replaceHref(`mailto:${built.email}`, `mailto:${c.email}`);
    replaceText(built.email, c.email);
  }
  const lines = c.address_lines.filter((l) => l.trim() && l.trim().toUpperCase() !== built.country.toUpperCase());
  if (c.name && lines.length) {
    document.querySelectorAll<HTMLElement>('[data-erp="address"]').forEach((el) => {
      if (el.closest('[data-erp-fixed]')) return;
      el.replaceChildren();
      [c.name, ...lines].forEach((line, i) => {
        if (i) el.append(document.createElement('br'));
        el.append(line);
      });
    });
  }
}

export function initContact(): void {
  const raw = document.body.dataset.contact;
  if (!raw) return;
  let built: Built;
  try {
    built = JSON.parse(raw) as Built;
  } catch {
    return;
  }
  void load().then((c) => { if (c) apply(built, c); });
}
