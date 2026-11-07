/**
 * Das Anfrage-Formular (überall dasselbe, #1107/#1129) – Komfort auf einem Formular, das
 * ohne JS vollständig klassisch an den Server geht.
 *
 *  - EIN Feld für das Anliegen, Anhänge, wer fragt an (Rückmeldung 04.10.2026) – in zwei
 *    Schritten (v4): «Weiter» prüft das Anliegen, dann folgen die Kontaktangaben
 *  - Fehler erscheinen direkt am Feld (aria-invalid + aria-describedby); die Wörter kommen
 *    aus der Konfiguration (data-vocab) – der Server meldet wortgleich
 *  - Senden im Hintergrund; Erfolg ersetzt das Formular, ein Fehler lässt alle Eingaben
 *    stehen und bietet Telefon und einen vorausgefüllten mailto-Link an
 *  - Vorbelegung aus der Adresse: /kontakt?teil=… (Teile-Katalog) schreibt das Teil ins Anliegen
 *  - Vorbelegung aus dem Konto (Auftrag 11.1): ist jemand angemeldet, stehen Name, Firma,
 *    Telefon und E-Mail schon da – gelesen aus dem Anzeige-Cache (scripts/account.ts),
 *    nur in leere Felder, änderbar wie jede Eingabe
 */
import { accountInfo } from './account';
import { subjectOf } from '../lib/inquiry-subject.mjs';

type Errors = Record<string, string>;
/** `formVocab()` (src/lib/inquiry-vocab.mjs) – dasselbe Objekt, das der Server bekommt. */
interface Vocab {
  labels: [string, string][];
  messages: Record<string, string>;
  patterns: { email: string; phone: string };
  subject: { word: string; max: number };
}

/** Längste Wartezeit auf den Server, dann der Ausweg (Telefon, mailto). */
const SEND_TIMEOUT = 60_000;

export function initInquiryForms(): void {
  document.querySelectorAll<HTMLFormElement>('form[data-inquiry]').forEach(setup);
}

function setup(form: HTMLFormElement): void {
  if (form.dataset.ready) return;
  form.dataset.ready = '1';
  form.noValidate = true;

  const root = form.closest<HTMLElement>('[data-inquiry-root]') ?? form.parentElement!;
  const okPanel = root.querySelector<HTMLElement>('[data-result="ok"]');
  const failPanel = root.querySelector<HTMLElement>('[data-result="fail"]');
  const submit = form.querySelector<HTMLButtonElement>('[data-submit]');
  const vocab: Vocab = JSON.parse(form.dataset.vocab ?? '{}');
  const loadedAt = Date.now();

  prefill(form);
  prefillAccount(form);
  const step = steps(form, vocab);
  root.querySelector<HTMLButtonElement>('[data-reset]')?.addEventListener('click', () => {
    form.reset();
    listFiles(form, form.querySelector<HTMLInputElement>('input[type="file"]')!);
    prefillAccount(form);
    if (okPanel) okPanel.hidden = true;
    form.hidden = false;
    step(1);
  });

  // ---------- Live: Fehler verschwinden beim Korrigieren ----------
  form.addEventListener('input', (e) => clearError(form, (e.target as HTMLInputElement).name));
  form.addEventListener('change', (e) => {
    const input = e.target as HTMLInputElement;
    clearError(form, input.name);
    if (input.type === 'file') {
      listFiles(form, input);
      render(form, photoErrors(form, input, vocab), false);
    }
  });

  // ---------- Senden ----------
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const errors = validate(form, vocab);
    if (errors.message || errors.photos) step(1);
    if (!render(form, errors)) return;

    // Ausfüllzeit in Millisekunden – gemessen mit der Uhr DIESES Geräts.
    setValue(form, 't', String(Date.now() - loadedAt));
    const data = new FormData(form);
    prune(data);
    form.setAttribute('aria-busy', 'true');
    if (submit) submit.disabled = true;
    // Ein hängender Server darf den Knopf nicht minutenlang sperren: nach SEND_TIMEOUT kommt
    // der Ausweg (Telefon, mailto). Grosszügig bemessen – Fotos über ein schwaches Netz
    // brauchen Zeit, und ein zu früher Abbruch lädt zum doppelten Senden ein.
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), SEND_TIMEOUT);
    try {
      const res = await fetch(form.action, { method: 'POST', body: data, headers: { Accept: 'application/json' }, signal: ctrl.signal });
      const body = (await res.json().catch(() => ({}))) as { ok?: boolean; fields?: Errors; message?: string };
      if (res.ok && body.ok) {
        form.hidden = true;
        if (failPanel) failPanel.hidden = true;
        if (okPanel) {
          okPanel.hidden = false;
          okPanel.focus();
          okPanel.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
        return;
      }
      if (res.status === 422 && body.fields) {
        render(form, body.fields);
        return;
      }
      fail(form, failPanel, vocab, res.status, body.message);
    } catch {
      fail(form, failPanel, vocab, 0);
    } finally {
      window.clearTimeout(timer);
      form.removeAttribute('aria-busy');
      if (submit) submit.disabled = false;
    }
  });
}

// ------------------------------------------------------------------ Schritte

/** Schritt 1 (Anliegen) ↔ 2 (Kontakt). Gibt die Funktion zurück, die den Schritt setzt. */
function steps(form: HTMLFormElement, vocab: Vocab): (n: 1 | 2) => void {
  const recap = form.querySelector<HTMLElement>('[data-recap]');
  // Die Fläche ist so hoch wie der GEZEIGTE Schritt und gleitet beim Wechsel weich auf die
  // neue Höhe – das Feld bleibt klein, und nichts darunter springt.
  const box = form.querySelector<HTMLElement>('.iform__steps');
  const fit = () => {
    const shown = form.querySelector<HTMLElement>(`.iform__step--${form.dataset.step ?? '1'}`);
    if (box && shown) box.style.height = `${shown.offsetHeight}px`;
  };
  if (box && 'ResizeObserver' in window) {
    const ro = new ResizeObserver(fit);
    form.querySelectorAll('.iform__step').forEach((el) => ro.observe(el));
  }
  const go = (n: 1 | 2, focus = false) => {
    form.dataset.step = String(n);
    fit();
    if (recap) {
      const msg = value(form, 'message').replace(/\s+/g, ' ');
      recap.textContent = msg.length > 80 ? `${msg.slice(0, 79)}…` : msg;
    }
    if (focus) form.querySelector<HTMLElement>(n === 1 ? '[name="message"]' : '[name="name"]')?.focus({ preventScroll: true });
  };
  form.querySelector('[data-step-next]')?.addEventListener('click', () => {
    const all = validate(form, vocab);
    const errors: Errors = {};
    if (all.message) errors.message = all.message;
    if (all.photos) errors.photos = all.photos;
    if (render(form, errors)) go(2, true);
  });
  form.querySelector('[data-edit]')?.addEventListener('click', () => go(1, true));
  return (n) => go(n);
}

// ------------------------------------------------------------------ Prüfen

function validate(form: HTMLFormElement, vocab: Vocab): Errors {
  const m = vocab.messages;
  const errors: Errors = {};
  if (!value(form, 'message')) errors.message = m.message;
  const photos = form.querySelector<HTMLInputElement>('input[type="file"][name="photos"]');
  if (photos) Object.assign(errors, photoErrors(form, photos, vocab));
  if (!value(form, 'name')) errors.name = m.name;
  const phone = value(form, 'phone');
  const email = value(form, 'email');
  if (!email) errors.email = m.emailMissing;
  else if (!new RegExp(vocab.patterns.email).test(email)) errors.email = m.email;
  if (phone && !new RegExp(vocab.patterns.phone).test(phone)) errors.phone = m.phone;
  return errors;
}

/** «{max} Zeichen» → «4000 Zeichen» */
const fill = (text: string, values: Record<string, string | number>) =>
  text.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ''));

function photoErrors(form: HTMLFormElement, input: HTMLInputElement, vocab: Vocab): Errors {
  const m = vocab.messages;
  const files = Array.from(input.files ?? []);
  if (!files.length) return {};
  const max = Number(form.dataset.maxFiles ?? 3);
  const maxBytes = Number(form.dataset.maxBytes ?? 10 * 1024 * 1024);
  const exts = (form.dataset.extensions ?? '').split(',');
  if (files.length > max) return { photos: fill(m.photosCount, { max, count: files.length }) };
  const wrong = files.find((f) => !exts.some((x) => f.name.toLowerCase().endsWith(x)));
  if (wrong) return { photos: fill(m.photosType, { name: wrong.name }) };
  const total = files.reduce((s, f) => s + f.size, 0);
  if (total > maxBytes) return { photos: fill(m.photosSize, { size: mb(total), max: mb(maxBytes) }) };
  return {};
}

/** Fehler anzeigen; true = keine Fehler. */
function render(form: HTMLFormElement, errors: Errors, focus = true): boolean {
  let first: HTMLElement | null = null;
  for (const [name, message] of Object.entries(errors)) {
    const box = form.querySelector<HTMLElement>(`[data-error-for="${name}"]`);
    if (box) {
      box.textContent = message;
      box.hidden = false;
    }
    form.querySelectorAll<HTMLInputElement>(`[name="${name}"]`).forEach((el) => {
      el.setAttribute('aria-invalid', 'true');
      first ??= el;
    });
  }
  if (first && focus) (first as HTMLElement).focus();
  return Object.keys(errors).length === 0;
}

function clearError(form: HTMLFormElement, name: string): void {
  if (!name) return;
  const box = form.querySelector<HTMLElement>(`[data-error-for="${name}"]`);
  if (box) box.hidden = true;
  form.querySelectorAll(`[name="${name}"]`).forEach((el) => el.removeAttribute('aria-invalid'));
}

// ------------------------------------------------------------------ Hilfen

function value(form: HTMLFormElement, name: string): string {
  const el = form.querySelector<HTMLInputElement>(`[name="${name}"]:not([type="file"])`);
  return el?.value.trim() ?? '';
}
function setValue(form: HTMLFormElement, name: string, v: string): void {
  const el = form.querySelector<HTMLInputElement | HTMLTextAreaElement>(`[name="${name}"]`);
  if (el) el.value = v;
}
const str = (v: FormDataEntryValue | null) => (typeof v === 'string' ? v : '');
const mb = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;

/** Leere Datei-Felder nicht senden (ein Browser schickt sonst eine leere Datei mit). */
function prune(data: FormData): void {
  for (const [k, v] of Array.from(data.entries())) {
    if (v instanceof File && v.size === 0) data.delete(k);
  }
}

function listFiles(form: HTMLFormElement, input: HTMLInputElement): void {
  const list = form.querySelector<HTMLElement>('[data-file-list]');
  if (!list) return;
  const files = Array.from(input.files ?? []);
  list.replaceChildren(
    ...files.map((f) => {
      const li = document.createElement('li');
      const name = document.createElement('span');
      name.textContent = f.name;
      const size = document.createElement('span');
      size.textContent = mb(f.size);
      li.append(name, size);
      return li;
    }),
  );
  list.hidden = files.length === 0;
}

/** /kontakt?teil=Auslaufrinne (aus dem Teile-Katalog) – das Teil steht schon im Anliegen. */
function prefill(form: HTMLFormElement): void {
  const part = new URLSearchParams(location.search).get('teil');
  if (part) setValue(form, 'message', `Anfrage zu: ${part.slice(0, 200)}\n`);
}

/** Kontaktangaben aus dem Konto – nur in leere Felder (Schnittstelle S2, nur lesend). */
function prefillAccount(form: HTMLFormElement): void {
  const info = accountInfo();
  if (!info) return;
  const fill = (name: string, v: unknown) => {
    if (typeof v !== 'string' || !v.trim()) return;
    const el = form.querySelector<HTMLInputElement>(`input[name="${name}"]`);
    if (el && !el.value) el.value = v.trim().slice(0, el.maxLength > 0 ? el.maxLength : 200);
  };
  fill('name', info.name);
  fill('company', info.contact.company);
  fill('phone', info.contact.phone);
  fill('email', info.contact.email);
}

/**
 * Fehlerfläche. `status` 0 = keine Antwort (Netz weg). Eine Ablehnung des Servers (4xx)
 * nennt ihren Grund – z. B. «zu schnell abgeschickt» –, eine Störung (5xx, Netz) die
 * Grundtexte; die Fläche wird wiederverwendet, also werden diese einmal gemerkt.
 */
function fail(form: HTMLFormElement, panel: HTMLElement | null, vocab: Vocab, status: number, serverMessage?: string): void {
  if (!panel) return;
  const title = panel.querySelector<HTMLElement>('[data-fail-title]');
  const text = panel.querySelector<HTMLElement>('[data-fail-text]');
  for (const el of [title, text]) if (el && el.dataset.default === undefined) el.dataset.default = el.textContent ?? '';
  if (title) title.textContent = status === 429 ? 'Zu viele Anfragen in kurzer Zeit.' : title.dataset.default ?? '';
  if (text) text.textContent = status >= 400 && status < 500 && serverMessage ? serverMessage : text.dataset.default ?? '';
  const mail = panel.querySelector<HTMLAnchorElement>('[data-mailto]');
  if (mail) mail.href = mailto(form, vocab);
  panel.hidden = false;
  panel.focus();
  panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

/**
 * mailto-Link mit allen Eingaben und den Beschriftungen des Formulars – unter demselben
 * Betreff wie die Nachricht im ERP («Anfrage: erster Satz»), denn die E-Mail landet im
 * Postfach derselben Gesellschaft.
 */
function mailto(form: HTMLFormElement, vocab: Vocab): string {
  const data = new FormData(form);
  prune(data);
  const get = (n: string) => str(data.get(n)).trim();
  const subject = subjectOf(get('message'), vocab.subject);
  const lines = vocab.labels.map(([field, label]) => [label, field === 'message' ? get(field).slice(0, 1200) : get(field)] as const);
  const photos = form.querySelector<HTMLInputElement>('input[type="file"]')?.files?.length ?? 0;
  const body = lines.filter(([, v]) => v).map(([l, v]) => `${l}: ${v}`).join('\n') +
    (photos ? `\n\nDateien: bitte ${photos === 1 ? 'die Datei' : `die ${photos} Dateien`} an diese E-Mail anhängen.` : '');
  return `mailto:${form.dataset.mail ?? ''}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
