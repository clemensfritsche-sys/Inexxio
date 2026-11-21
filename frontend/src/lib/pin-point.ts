/**
 * ►►► **Die Stecknadel** – auf eine Stelle der Oberfläche zeigen und sie in Worte fassen. ◄◄◄
 *
 * Eine Rückmeldung zur Software ist eine gewöhnliche Erfassung (`docs/konzept/lernende-firma.md`):
 * die Stecknadel im «+» lässt auf ein Element zeigen; daraus wird **eine Zeile Text** («Stelle:
 * …») vor dem, was man schreibt oder sagt, und der Hinweis ist der Artikel, der die Software ist
 * – «ERP» auf `/erp`, sonst «Website» (`PIN_HOMES`). Die KI legt ab wie jede Erfassung: eine
 * Notiz an diesem Artikel, Teil der lernenden Firma. Es gibt keine eigene Tabelle dafür.
 *
 * Die Oberfläche benennt ihre Orte selbst: Abschnitte, Reiter und Modul-Karten tragen
 * `data-where-*` (`detail-frame`, `detail-tabs`, `module-card`, `beleg/shared`). Daraus wird
 * die Herkunft «Zahlung › Positionen» – die eine Angabe, die ohne Raten zur Stelle führt.
 */

/** Unsere eigene Oberfläche (das «+», seine Knöpfe) ist nie das Ziel der Stecknadel. */
export const PIN_UI = 'data-pin-ui';

/** Die Artikel, an denen Rückmeldungen zur Software hängen – je nach Seite. */
const PIN_HOMES = { erp: 'ERP', website: 'Website' } as const;

/**
 * Die Farben der Stecknadel als Werte, nicht als Tokens: sie zeichnet auch im Dokument der
 * Website (hinter dem eingebetteten «+»), und dort heissen die Tokens anders. Rot der Marke,
 * Tinte der Leiste.
 */
const PIN_RED = 'rgb(229 26 20)';
const PIN_INK = 'rgb(14 17 22)';

/** So viel Platz hat eine Angabe in der Zeile «Stelle: …». */
const MAX = { label: 120, origin: 80, path: 120 };

/**
 * ►►► **Nur Text, den eine Datenbank aufnimmt** (#943). ◄◄◄ PostgreSQL nimmt in `text` kein
 * NUL; was die Seite hergibt, entscheidet nicht, ob eine Erfassung speicherbar ist. Gekappt wird
 * jedes C0-Steuerzeichen ausser Tabulator und Zeilenumbruch (der Server putzt noch einmal,
 * `talk.clean`).
 */
const clean = (s: string) => s.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
const cut = (s: string, n: number) => {
  const safe = clean(s);
  return safe.length > n ? `${safe.slice(0, n - 1)}…` : safe;
};
const tidy = (s: string) => s.replace(/\s+/g, ' ').trim();

/** Das Element ist ein Feld? Nach dem Namen gefragt, nicht mit `instanceof` – auf der Website
 *  stammt es aus dem Fenster hinter dem eingebetteten «+», und dessen Klassen sind andere. */
const FIELDS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/** Der **Wert** eines Bedienelements – bei einem `<select>` die gewählte Zeile, nie die Liste. */
function controlValue(el: Element): string {
  if (el.tagName === 'SELECT') {
    const sel = el as HTMLSelectElement;
    return tidy(sel.selectedOptions[0]?.textContent ?? sel.value);
  }
  return FIELDS.has(el.tagName) ? tidy((el as HTMLInputElement).value ?? '') : '';
}

/**
 * ►►► **Was ein Element IST – nicht, was alles darin steht.** ◄◄◄ Die ausdrückliche
 * Benennung (`aria-label`, `data-tip`, `title`, `placeholder`), bei einem Bedienelement seine
 * Wahl, sonst der eigene Text (nur direkte Textknoten), die zugehörige `<label>`, und erst
 * zuletzt – nur wenn er kurz ist – der Text der Nachfahren. Eine Wand aus Text sagt weniger
 * als nichts.
 */
function labelOf(el: Element): string {
  const explicit = tidy(el.getAttribute('aria-label') || el.getAttribute('data-tip')
    || el.getAttribute('title') || (el as HTMLInputElement).placeholder || '');
  if (explicit) return explicit;
  const chosen = controlValue(el);
  if (chosen) return chosen;
  const own = tidy(Array.from(el.childNodes).filter((n) => n.nodeType === Node.TEXT_NODE)
    .map((n) => n.textContent ?? '').join(' '));
  if (own) return own;
  const labelled = el.id ? el.ownerDocument.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
  const named = tidy(labelled?.textContent ?? el.closest('label')?.textContent ?? '');
  if (named) return named;
  const deep = tidy(el.textContent ?? '');
  return deep.length <= 60 ? deep : '';
}

/** Die Herkunft «Zahlung › Positionen» – alle `data-where-*` von der Wurzel bis zum Element. */
function originOf(el: Element): string {
  const parts: string[] = [];
  for (let cur: Element | null = el; cur && cur !== el.ownerDocument.body; cur = cur.parentElement) {
    for (const attr of Array.from(cur.attributes)) {
      if (attr.name.startsWith('data-where-') && attr.value) parts.unshift(tidy(attr.value));
    }
  }
  return parts.filter((p, i) => parts.indexOf(p) === i).join(' › ');
}

/** Ein Wort für die Art des Elements – «Knopf», «Feld», sonst nichts. */
function kindOf(el: Element): string {
  if (el.closest('button, [role="button"]')) return 'Knopf';
  if (FIELDS.has(el.tagName)) return 'Feld';
  if (el.closest('a[href]')) return 'Link';
  return '';
}

/** Gehört diese Seite zum ERP? Sonst ist es die Website (auch Konto, Anmelden, Beleg). */
export function pinHome(path = typeof window === 'undefined' ? '' : window.location.pathname): string {
  return path === '/erp' || path.startsWith('/erp/') ? PIN_HOMES.erp : PIN_HOMES.website;
}

/**
 * ►►► **Die Stelle in einer Zeile** – Seite, offener Datensatz, Herkunft, Element. ◄◄◄
 * «Stelle: /erp · Datensatz 100000005 · Zahlung › Positionen · Knopf «Prüfen und freigeben»».
 * `cut` ist die eine Kapp-Funktion – jede Angabe läuft durch sie (und damit durch `clean`).
 * `win` ist das Fenster, in dem gezeigt wurde (die Website hinter dem eingebetteten «+»).
 */
export function describePlace(el: Element, openRecord?: number | null, win: Window = window): string {
  const parts = [cut(win.location.pathname + win.location.search, MAX.path)];
  if (openRecord) parts.push(`Datensatz ${openRecord}`);
  const origin = cut(originOf(el), MAX.origin);
  if (origin) parts.push(origin);
  const label = cut(labelOf(el), MAX.label);
  const kind = kindOf(el);
  if (label) parts.push(`${kind ? `${kind} ` : ''}«${label}»`);
  else if (kind) parts.push(kind);
  return `Stelle: ${parts.join(' · ')}`;
}

/** Die kleine Leiste während des Zeigens – im Dokument, in dem gezeigt wird, ohne Stilblatt. */
function hintBar(doc: Document, onCancel: () => void): HTMLElement {
  const bar = doc.createElement('div');
  bar.setAttribute(PIN_UI, 'true');
  bar.setAttribute('role', 'status');
  bar.style.cssText = ['position:fixed', 'left:50%', 'bottom:calc(16px + env(safe-area-inset-bottom,0px))',
    'transform:translateX(-50%)', 'z-index:2147483647', 'display:flex', 'align-items:center', 'gap:12px',
    'padding:10px 10px 10px 16px', 'border-radius:999px', `background:${PIN_INK}`, 'color:#fff',
    'font:500 14px/1.2 Inter,system-ui,sans-serif', 'box-shadow:0 10px 30px rgba(0,0,0,.3)', 'cursor:default'].join(';');
  const text = doc.createElement('span');
  text.textContent = 'Auf die Stelle tippen';
  const cancel = doc.createElement('button');
  cancel.type = 'button';
  cancel.textContent = 'Abbrechen';
  cancel.style.cssText = 'border:0;border-radius:999px;padding:7px 12px;background:rgba(255,255,255,.14);'
    + 'color:#fff;font:600 13px/1 Inter,system-ui,sans-serif;cursor:pointer';
  cancel.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); onCancel(); });
  bar.append(text, cancel);
  doc.body.appendChild(bar);
  return bar;
}

/**
 * ►►► **Auf eine Stelle zeigen** – der nächste Klick ausserhalb unserer Oberfläche wählt das
 * Element; er löst dort **nichts** aus (abgefangen, bevor die Seite ihn sieht). Esc oder
 * «Abbrechen» bricht ab. `doc` ist das Dokument, in dem gezeigt wird. Gibt eine Funktion
 * zurück, die das Zeigen beendet (Aufräumen in jedem Fall). ◄◄◄
 */
export function pickPlace(doc: Document, onPicked: (el: Element) => void, onCancel: () => void): () => void {
  const ours = (el: Element | null) => !!el?.closest(`[${PIN_UI}]`);
  let mark: HTMLElement | null = null;
  const highlight = (el: Element | null) => {
    if (mark === el) return;
    mark?.style.removeProperty('outline');
    mark?.style.removeProperty('outline-offset');
    mark = el && 'style' in el ? el as HTMLElement : null;
    mark?.style.setProperty('outline', `2px dashed ${PIN_RED}`);
    mark?.style.setProperty('outline-offset', '2px');
  };
  const target = (e: MouseEvent) => {
    const el = doc.elementFromPoint(e.clientX, e.clientY);
    return el && !ours(el) ? el : null;
  };
  const move = (e: PointerEvent) => highlight(target(e));
  // Die Seite sieht weder Druck noch Klick – sonst löste die Stecknadel aus, worauf sie zeigt.
  const swallow = (e: Event) => {
    if (ours(e.target as Element | null)) return;
    e.preventDefault();
    e.stopPropagation();
  };
  const click = (e: MouseEvent) => {
    if (ours(e.target as Element | null)) return;
    e.preventDefault();
    e.stopPropagation();
    const el = target(e);
    stop();
    if (el) onPicked(el); else onCancel();
  };
  const key = (e: KeyboardEvent) => {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    stop();
    onCancel();
  };
  let done = false;
  const bar = hintBar(doc, () => { stop(); onCancel(); });
  function stop() {
    if (done) return;
    done = true;
    highlight(null);
    bar.remove();
    doc.removeEventListener('pointermove', move, true);
    doc.removeEventListener('pointerdown', swallow, true);
    doc.removeEventListener('mousedown', swallow, true);
    doc.removeEventListener('click', click, true);
    doc.removeEventListener('keydown', key, true);
    doc.documentElement.style.removeProperty('cursor');
  }
  doc.addEventListener('pointermove', move, true);
  doc.addEventListener('pointerdown', swallow, true);
  doc.addEventListener('mousedown', swallow, true);
  doc.addEventListener('click', click, true);
  doc.addEventListener('keydown', key, true);
  doc.documentElement.style.setProperty('cursor', 'crosshair');
  return stop;
}
