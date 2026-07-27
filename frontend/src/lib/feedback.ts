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

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n) : s);
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
  return [openRecord.kind, tab].filter(Boolean).join(' · ').slice(0, 80);
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

/** Sichtbarer Text des Elements – in einer deutschsprachigen UI der beste Anker im Code. */
function visibleLabel(el: Element): string {
  let cur: Element | null = el;
  for (let i = 0; cur && i < 3; i++, cur = cur.parentElement) {
    const explicit = cur.getAttribute('aria-label') || cur.getAttribute('title')
      || (cur as HTMLInputElement).placeholder || '';
    const text = explicit || (cur.textContent || '');
    const clean = text.replace(/\s+/g, ' ').trim();
    if (clean) return cut(clean, MAX.label);
  }
  return '';
}

/**
 * Selektor-Kette zum Wiederfinden des Elements (Pin-Position beim nächsten Besuch).
 * Bewusst OHNE Klassennamen: Tailwind-Klassen enthalten `:` und `/` und ändern sich
 * bei jedem Redesign – Tag + Position ist stabiler und immer querySelector-tauglich.
 */
function cssPath(el: Element): string {
  const parts: string[] = [];
  let cur: Element | null = el;
  for (let i = 0; cur && i < 5 && cur !== document.body; i++) {
    const node: Element = cur;
    if (node.id) { parts.unshift(`#${CSS.escape(node.id)}`); break; }
    const tag = node.tagName.toLowerCase();
    const parent: HTMLElement | null = node.parentElement;
    if (!parent) { parts.unshift(tag); break; }
    const twins = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
    parts.unshift(twins.length > 1 ? `${tag}:nth-of-type(${twins.indexOf(node) + 1})` : tag);
    cur = parent;
  }
  return cut(parts.join(' > '), MAX.selector);
}

/** WO: alles, was das angeklickte Element beschreibt. */
export function describeAnchor(el: Element, clientX: number, clientY: number): FeedbackAnchor {
  const rect = el.getBoundingClientRect();
  return {
    label: visibleLabel(el),
    tag: cut(el.tagName.toLowerCase(), MAX.tag),
    selector: cssPath(el),
    html: cut(el.outerHTML.replace(/\s+/g, ' '), MAX.html),
    section: sectionOf(el),
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

const errors: string[] = [];
let capturing = false;

function push(message: string) {
  errors.push(cut(message.replace(/\s+/g, ' ').trim(), MAX.error));
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
  return errors.slice(-5);
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
