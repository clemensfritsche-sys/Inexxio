/**
 * Testnotizen – die reine Logik hinter dem Pin-Widget (siehe `docs/feedback.md`).
 *
 * Hier steht alles, was KEIN React braucht: den Anker am geklickten Element bestimmen,
 * die Umgebung einsammeln und die Notizen als Markdown exportieren. Das Widget
 * (`components/feedback/feedback-pin.tsx`) bleibt damit reine Darstellung.
 *
 * Leitgedanke: der Melder soll NICHTS dokumentieren müssen. Was die Entwicklung
 * braucht – wo war ich, welcher Datensatz, welches Element, was ist gekracht –
 * schneidet die Oberfläche selbst mit.
 */

import type { FeedbackAnchor, FeedbackContext, FeedbackNote } from '@/types';

/** Nur ausserhalb der Produktion – die Notizfunktion ist ein Werkzeug der Testumgebung. */
export const FEEDBACK_ENABLED = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development';

/** Build-Commit des Frontends (in der CI gesetzt) – beantwortet «welchen Stand hast du gesehen?». */
const BUILD = (process.env.NEXT_PUBLIC_COMMIT_SHA || '').slice(0, 12);

/** Markierung an unserer eigenen UI – deren Elemente sind nie Ziel einer Notiz. */
export const UI_MARKER = 'data-feedback-ui';

// Feldlängen wie im Backend-Schema (`schemas/feedback.py`) – hier gekappt, damit eine
// Notiz nie an einer Validierung scheitert, wenn jemand einen Roman-Knopf anklickt.
const MAX = { label: 200, tag: 40, selector: 500, html: 800, ua: 300, error: 300, section: 80 };

/**
 * ►►► **Eine Notiz enthält nur Text, den eine Datenbank auch aufnimmt** (#943). ◄◄◄
 *
 * Gemeldet war ein Speicherfehler: `unsupported Unicode escape sequence … \\u0000 cannot
 * be converted to text`. PostgreSQL nimmt in `text` **kein NUL** auf – und eine Notiz
 * erfasst rohen `outerHTML`, also alles, was irgendwo in der Oberfläche steht. Der
 * konkrete Auslöser war ein Platzhalter mit NUL-Byte und ist behoben; **die Regel gehört
 * trotzdem hierher**: was die Seite hergibt, entscheidet nicht die Seite.
 *
 * Gekappt wird jedes C0-Steuerzeichen ausser Tabulator und Zeilenumbruch – sie tragen in
 * einer Notiz keine Information, und keines davon überlebt die Speicherung.
 */
const clean = (s: string) => s.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
const cut = (s: string, n: number) => {
  const safe = clean(s);
  return safe.length > n ? safe.slice(0, n) : safe;
};
const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

/** Aktuelle Seite inkl. Query – die Route, an der die Notiz hängt. */
export function currentRoute(): string {
  if (typeof window === 'undefined') return '';
  return cut(window.location.pathname + window.location.search, 500);
}

// ─── Was ist gerade offen? ────────────────────────────────────────────────────
// Der ERP-Feed ist ein Master-Detail auf EINER Route: `/erp` bleibt `/erp`, egal
// welcher Datensatz geöffnet ist (`?open=` ist nur der Deep-Link von aussen). Ohne
// diese Meldung stand bei jeder Notiz aus dem Detailfenster KEINE Objektnummer –
// die Entwicklung musste den Datensatz aus dem Text erraten. Darum meldet die
// ERP-Seite ihre Auswahl hierher; das Widget liest sie beim Anheften.

let openRecord: { kind?: string | null; objectId?: number | null } = {};

/** Vom ERP-Feed gerufen, sobald sich die Auswahl ändert (null = Detail geschlossen). */
export function setOpenRecord(record: { kind?: string | null; objectId?: number | null } | null) {
  openRecord = record ?? {};
}

/**
 * Objektnummer des gerade geöffneten Datensatzes: zuerst die gemeldete Auswahl,
 * sonst der Deep-Link `?open=<Objektnr>` bzw. eine 9-stellige Nummer im Pfad
 * (100'000'001–999'999'999 ist eindeutig genug, um sie sicher zu erkennen).
 */
export function currentObjectId(): number | null {
  if (typeof window === 'undefined') return null;
  if (openRecord.objectId != null) return openRecord.objectId;
  const fromQuery = new URLSearchParams(window.location.search).get('open');
  const candidate = fromQuery ?? (window.location.pathname.match(/\b(\d{9})\b/)?.[1] ?? '');
  const n = Number(candidate);
  return Number.isInteger(n) && n >= 100_000_001 && n <= 999_999_999 ? n : null;
}

/** «Artikel · Prozess» – Datensatzart plus aktiver Reiter (aus dem DOM, eine Quelle). */
function currentView(): string {
  const tab = document.querySelector('[data-fb-tab]')?.getAttribute('data-fb-tab') ?? '';
  return cut([openRecord.kind, tab].filter(Boolean).join(' · '), MAX.section);
}

/**
 * Umgebender Abschnitt des geklickten Elements: der nächste Vorfahr, der einen
 * Abschnittskopf enthält (`PanelHeader`/`SectionTitle` markieren sich mit
 * `data-fb-section`). Genau das trägt bei den dynamischen Listen des Prozess-
 * Editors die Bedeutung, die eine `nth-of-type`-Kette nicht mehr hergibt:
 * «Abschnitt: Bewegung» sagt, um welches Schritt-Panel es geht.
 */
function sectionOf(el: Element): string {
  let cur: Element | null = el;
  for (let i = 0; cur && i < 8; i++, cur = cur.parentElement) {
    const head = cur.querySelector?.('[data-fb-section]');
    if (head) return cut(head.getAttribute('data-fb-section') ?? '', MAX.section);
  }
  return '';
}

const tidy = (s: string) => s.replace(/\s+/g, ' ').trim();

/**
 * ►►► **Was ein Element IST – nicht, was alles darin steht.** ◄◄◄
 *
 * Die frühere Fassung nahm `textContent` des Elements bzw. seiner Vorfahren. An einem
 * Knopf stimmt das; an allem anderen nicht, und zwei Fälle machten die Notiz unbrauchbar:
 *
 * - ein `<select>` lieferte den Text **aller Optionen** («—EXW · Ab WerkFCA · Frei
 *   FrachtführerCPT · …»), also die Liste statt der Wahl;
 * - ein Container lieferte alles, was darin steht – bei einer ganzen Karte eine Wand aus
 *   Text, in der die eigentliche Stelle untergeht.
 *
 * Gefragt wird darum in der Reihenfolge, in der eine Oberfläche ihre Bedeutung trägt:
 * die **ausdrückliche** Benennung (`aria-label`, `title`, `placeholder`), bei einem
 * Bedienelement seine **Wahl**, sonst der **eigene** Text (nur direkte Textknoten), dann
 * die zugehörige `<label>`-Beschriftung, und erst zuletzt – und **nur wenn er kurz ist** –
 * der Text der Nachfahren. Eine Wand aus Text sagt weniger als ein ehrliches «—».
 */
function elementLabel(el: Element): string {
  const explicit = tidy(
    el.getAttribute('aria-label') || el.getAttribute('data-tip')
    || el.getAttribute('title') || (el as HTMLInputElement).placeholder || '',
  );
  if (explicit) return cut(explicit, MAX.label);

  const chosen = controlValue(el);
  if (chosen) return cut(chosen, MAX.label);

  // **Nur die eigenen Textknoten** – das ist die Beschriftung dieses Elements, nicht die
  // seiner Kinder.
  const own = tidy(Array.from(el.childNodes)
    .filter((n) => n.nodeType === Node.TEXT_NODE)
    .map((n) => n.textContent ?? '').join(' '));
  if (own) return cut(own, MAX.label);

  const labelled = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
  const named = tidy(labelled?.textContent ?? el.closest('label')?.textContent ?? '');
  if (named) return cut(named, MAX.label);

  const deep = tidy(el.textContent ?? '');
  return deep.length <= 60 ? deep : '';
}

/** Der **Wert** eines Bedienelements – bei einem `<select>` die gewählte Zeile, nie die Liste. */
function controlValue(el: Element): string {
  if (el instanceof HTMLSelectElement) {
    return tidy(el.selectedOptions[0]?.textContent ?? el.value);
  }
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    return tidy(el.value);
  }
  return '';
}

/**
 * ►►► **Woher im Haus kommt das?** ◄◄◄
 *
 * Eine `nth-of-type`-Kette sagt, **wo** ein Element im Baum hängt – nicht, **was** es
 * ist. Die Oberfläche weiss das aber: Abschnitte, Reiter und Modul-Karten markieren sich
 * mit `data-fb-*`. Eingesammelt wird die ganze Kette bis zur Wurzel, und daraus wird ein
 * lesbarer Pfad («Zahlung › Positionen»). Für die Entwicklung ist das die eine Angabe,
 * die ohne Raten zur richtigen Komponente führt.
 */
function originOf(el: Element): string {
  const parts: string[] = [];
  let cur: Element | null = el;
  while (cur && cur !== document.body) {
    for (const attr of Array.from(cur.attributes)) {
      if (attr.name.startsWith('data-fb-') && attr.value) parts.unshift(tidy(attr.value));
    }
    cur = cur.parentElement;
  }
  // Doppelte Nennungen (derselbe Abschnitt an zwei Ebenen) sind keine Zusatzinformation.
  return cut(parts.filter((p, i) => parts.indexOf(p) === i).join(' › '), MAX.section);
}

/**
 * Selektor-Kette zum Wiederfinden des Elements (Pin-Position beim nächsten Besuch).
 * Bewusst OHNE Klassennamen: Tailwind-Klassen enthalten `:` und `/` und ändern sich
 * bei jedem Redesign – Tag + Position ist stabiler und immer querySelector-tauglich.
 */
function cssPath(el: Element): string {
  const parts: string[] = [];
  let cur: Element | null = el;
  // ►►► **Die Kette braucht einen ANKER, keine feste Länge.** ◄◄◄ Nach fünf Ebenen
  // abgeschnitten war sie **relativ** und traf irgendein `div` irgendwo auf der Seite –
  // der Pin sass beim nächsten Besuch falsch oder gar nicht. Gelaufen wird darum, bis
  // etwas Benanntes kommt (`id` oder eine `data-fb-*`-Markierung) und sonst bis `body`.
  // Das bindet den Pfad **und** hält ihn kurz.
  for (let i = 0; cur && i < 40 && cur !== document.body; i++) {
    const node: Element = cur;
    const anchor = anchorFor(node);
    if (anchor) { parts.unshift(anchor); return cut(parts.join(' > '), MAX.selector); }
    const tag = node.tagName.toLowerCase();
    const parent: HTMLElement | null = node.parentElement;
    if (!parent) { parts.unshift(tag); break; }
    const twins = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
    parts.unshift(twins.length > 1 ? `${tag}:nth-of-type(${twins.indexOf(node) + 1})` : tag);
    cur = parent;
  }
  return cut(['body', ...parts].join(' > '), MAX.selector);
}

/** Ein benannter Halt in der Kette – `id` oder eine `data-fb-*`-Markierung des Hauses. */
function anchorFor(node: Element): string {
  if (node.id) return `#${CSS.escape(node.id)}`;
  for (const attr of Array.from(node.attributes)) {
    if (attr.name.startsWith('data-fb-') && attr.value) {
      return `[${attr.name}="${CSS.escape(attr.value)}"]`;
    }
  }
  return '';
}

/** WO: alles, was das angeklickte Element beschreibt. */
export function describeAnchor(el: Element, clientX: number, clientY: number): FeedbackAnchor {
  const rect = el.getBoundingClientRect();
  const origin = originOf(el);
  const section = sectionOf(el);
  return {
    label: elementLabel(el),
    tag: cut(el.tagName.toLowerCase(), MAX.tag),
    selector: cssPath(el),
    html: cut(el.outerHTML.replace(/\s+/g, ' '), MAX.html),
    // **Die Herkunft ist die bessere Auskunft** – wo eine steht, steht sie hier; sonst
    // bleibt der Abschnittskopf. Zwei Felder dafür wären zwei Wahrheiten über dieselbe
    // Frage, und das Backend-Schema kennt eines.
    section: origin || section,
    rx: rect.width ? clamp01((clientX - rect.left) / rect.width) : 0.5,
    ry: rect.height ? clamp01((clientY - rect.top) / rect.height) : 0.5,
  };
}

/** WOMIT: Umgebung + die letzten Laufzeitfehler dieser Sitzung. */
export function describeContext(role: string): FeedbackContext {
  return {
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    ua: cut(navigator.userAgent, MAX.ua),
    role,
    version: BUILD,
    view: currentView(),
    errors: recentErrors(),
  };
}

/** Element einer Notiz auf der aktuellen Seite wiederfinden (für die Pin-Position). */
export function locateAnchor(note: FeedbackNote): DOMRect | null {
  const sel = note.anchor?.selector;
  if (!sel) return null;
  try {
    const el = document.querySelector(sel);
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return rect.width || rect.height ? rect : null;
  } catch {
    return null;   // veralteter/ungültiger Selektor → kein Pin, nie ein Absturz
  }
}

// ─── Fehler-Ringpuffer ────────────────────────────────────────────────────────
// Genau der Teil, den man von Hand nie dokumentiert. Bewusst nur Listener (kein
// Monkey-Patching von console.*) – null Risiko für die laufende Anwendung.

const errors: { text: string; count: number }[] = [];
let capturing = false;

/**
 * ►►► **Derselbe Fehler ist EIN Fehler, und wie oft er kam, ist die Auskunft.** ◄◄◄
 *
 * Der Ringpuffer hielt fünf Einträge; ein Fehler in einer Render-Schleife füllte ihn
 * fünfmal mit derselben Zeile, und die Notiz meldete «… | … | … | … | …». Damit war der
 * Puffer voll, bevor der **zweite, andere** Fehler kam – also ausgerechnet der, den man
 * gebraucht hätte. Gezählt statt wiederholt bleibt beides erhalten.
 */
function push(message: string) {
  const text = cut(tidy(message), MAX.error);
  const seen = errors.find((e) => e.text === text);
  if (seen) { seen.count += 1; return; }
  errors.push({ text, count: 1 });
  if (errors.length > 5) errors.shift();
}

export function startErrorCapture(): () => void {
  if (capturing || typeof window === 'undefined') return () => {};
  capturing = true;
  const onError = (e: ErrorEvent) =>
    push(`${e.message} (${(e.filename || '').split('/').pop()}:${e.lineno})`);
  const onRejection = (e: PromiseRejectionEvent) => push(`Unhandled: ${String(e.reason)}`);
  window.addEventListener('error', onError);
  window.addEventListener('unhandledrejection', onRejection);
  return () => {
    window.removeEventListener('error', onError);
    window.removeEventListener('unhandledrejection', onRejection);
    capturing = false;
  };
}

function recentErrors(): string[] {
  return errors.map((e) => (e.count > 1 ? `${e.text} ×${e.count}` : e.text));
}

// ─── Export für die Weiterverarbeitung ────────────────────────────────────────

/**
 * Offene Notizen als Markdown – das Briefing, das in eine Entwicklungs-Sitzung
 * eingefügt wird. Format bewusst stabil (siehe `docs/feedback.md`), damit es
 * maschinell wie menschlich lesbar bleibt.
 */
export function notesToMarkdown(notes: FeedbackNote[]): string {
  const open = notes.filter((n) => n.status === 'open');
  if (!open.length) return '# Testnotizen\n\nKeine offenen Notizen.\n';
  const lines = [`# Testnotizen (${open.length} offen)`, ''];
  for (const n of open) lines.push(...noteToMarkdown(n), '');
  return lines.join('\n');
}

function noteToMarkdown(n: FeedbackNote): string[] {
  const a = n.anchor;
  const c = n.context;
  const out = [`## #${n.id} · ${n.route || '—'}`, '', `> ${n.body.replace(/\n/g, '\n> ')}`, ''];
  if (c?.view) out.push(`- **Ansicht:** ${c.view}`);
  if (a?.section) out.push(`- **Abschnitt:** ${a.section}`);
  if (a?.label) out.push(`- **Element:** «${a.label}» (\`${a.tag}\`)`);
  if (a?.selector) out.push(`- **Selektor:** \`${a.selector}\``);
  if (n.target_object_id) out.push(`- **Datensatz:** ${n.target_object_id}`);
  const env = [c?.role && `Rolle ${c.role}`, c?.viewport, c?.version && `Build ${c.version}`]
    .filter(Boolean).join(' · ');
  if (env) out.push(`- **Umgebung:** ${env}`);
  if (c?.errors?.length) out.push(`- **Fehler:** ${c.errors.join(' | ')}`);
  out.push(`- **Gemeldet:** ${n.author_name || 'unbekannt'}, ${new Date(n.created_at).toLocaleString('de-CH')}`);
  return out;
}
