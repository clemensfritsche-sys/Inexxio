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
 * Getauscht wird in jedem Bereich mit `data-contact` (die Vorgabe dieses Builds als JSON): auf
 * der Website ist das `<body>`, im Konto/ERP sind es Kopf und Fuss – derselbe Code an beiden
 * Orten (EIN Kopf, EIN Fuss). `data-erp="route"` bekommt den Routen-Link zur Anschrift.
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

/** Text ersetzen – nicht in Skripten und nicht in festen Bereichen. */
function replaceText(root: HTMLElement, from: string, to: string): void {
  if (!from || !to || from === to) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
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

function replaceHref(root: HTMLElement, prefix: string, to: string): void {
  root.querySelectorAll<HTMLAnchorElement>(`a[href^="${prefix}"]`).forEach((a) => {
    if (a.closest('[data-erp-fixed]')) return;
    a.setAttribute('href', to + a.getAttribute('href')!.slice(prefix.length));
  });
}

export function apply(built: Built, c: Contact, root: HTMLElement = document.body): void {
  if (c.phone && c.phone_e164) {
    replaceHref(root, `tel:${built.e164}`, `tel:${c.phone_e164}`);
    replaceText(root, built.phone, c.phone);
  }
  if (c.email) {
    replaceHref(root, `mailto:${built.email}`, `mailto:${c.email}`);
    replaceText(root, built.email, c.email);
  }
  const lines = c.address_lines.filter((l) => l.trim() && l.trim().toUpperCase() !== built.country.toUpperCase());
  if (lines.length) {
    // Route zur Anschrift aus dem ERP – öffnet in einem neuen Tab, die Website bleibt offen.
    const dest = encodeURIComponent(lines.join(', '));
    root.querySelectorAll<HTMLAnchorElement>('[data-erp="route"]').forEach((a) => {
      if (!a.closest('[data-erp-fixed]')) a.href = `https://www.google.com/maps/dir/?api=1&destination=${dest}`;
    });
    // Der Ort allein (z. B. im Fliesstext): die Zeile mit der Postleitzahl, ohne die Zahl.
    const city = lines.find((l) => /^\d{4,5}\s/.test(l.trim()))?.trim().replace(/^\d{4,5}\s+/, '');
    if (city) root.querySelectorAll<HTMLElement>('[data-erp="city"]').forEach((el) => {
      if (!el.closest('[data-erp-fixed]')) el.textContent = city;
    });
  }
  if (c.name && lines.length) {
    root.querySelectorAll<HTMLElement>('[data-erp="address"]').forEach((el) => {
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
  const roots = Array.from(document.querySelectorAll<HTMLElement>('[data-contact]'));
  if (!roots.length) return;
  void load().then((c) => {
    if (!c) return;
    for (const root of roots) {
      try {
        apply(JSON.parse(root.dataset.contact ?? '') as Built, c, root);
      } catch { /* unlesbare Vorgabe – dieser Bereich bleibt, wie er ist */ }
    }
  });
}
