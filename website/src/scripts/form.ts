/**
 * Anfrage-Formulare (Haupt- und Kurzformular) – Komfort auf einem Formular, das ohne JS
 * vollständig klassisch an den Server geht.
 *
 *  - Hauptformular: vier Schritte mit Fortschritt; «Weiter» prüft nur den aktuellen Schritt
 *  - Fehler erscheinen direkt am Feld (aria-invalid + aria-describedby); die Wörter kommen
 *    aus der Konfiguration (data-vocab) – der Server meldet wortgleich
 *  - Senden im Hintergrund; Erfolg ersetzt das Formular, ein Fehler lässt alle Eingaben
 *    stehen und bietet Telefon und einen vorausgefüllten mailto-Link an
 *  - Vorbelegung aus der Adresse: /kontakt?typ=teile&teil=…&fahrmischer=…, ?typ=kran&thema=pruefung,
 *    ?typ=abo&stufe=service, ?krane=3, ?dringend=1
 */
import { track } from './track';

type Errors = Record<string, string>;
interface Vocab {
  kind: Record<string, string>;
  kindSubject: Record<string, string>;
  need: Record<string, string>;
  urgency: Record<string, string>;
  urgencySubject: Record<string, string>;
  pref: Record<string, string>;
  tiers?: Record<string, string>;
  labels: [string, string][];
  messages: Record<string, string>;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const PHONE = /^[+()\d][\d\s/().-]{5,}$/;

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
  const isMain = form.dataset.form === 'haupt';
  const steps = Array.from(form.querySelectorAll<HTMLElement>('[data-step]'));
  const vocab: Vocab = JSON.parse(form.dataset.vocab ?? '{}');
  const loadedAt = Date.now();
  let current = 0;

  // ---------- Schritte ----------
  const prev = form.querySelector<HTMLButtonElement>('[data-prev]');
  const next = form.querySelector<HTMLButtonElement>('[data-next]');
  const submit = form.querySelector<HTMLButtonElement>('[data-submit]');
  const progress = form.querySelector<HTMLElement>('[data-progress]');
  const status = form.querySelector<HTMLElement>('[data-step-status]');
  const useSteps = isMain && steps.length > 1;

  const show = (index: number, moveFocus: boolean) => {
    current = Math.max(0, Math.min(steps.length - 1, index));
    steps.forEach((s, i) => s.classList.toggle('is-current', i === current));
    progress?.querySelectorAll<HTMLElement>('[data-progress-item]').forEach((li, i) => {
      li.classList.toggle('is-done', i < current);
      li.classList.toggle('is-current', i === current);
      if (i === current) li.setAttribute('aria-current', 'step');
      else li.removeAttribute('aria-current');
    });
    if (prev) prev.hidden = current === 0;
    if (next) next.hidden = current === steps.length - 1;
    if (submit) submit.hidden = current !== steps.length - 1;
    const title = steps[current].querySelector('.iform__legend .h3')?.textContent ?? '';
    if (status) status.textContent = `Schritt ${current + 1} von ${steps.length}: ${title}`;
    if (moveFocus) {
      const legend = steps[current].querySelector<HTMLElement>('.iform__legend');
      if (legend) {
        legend.tabIndex = -1;
        legend.focus({ preventScroll: true });
      }
      const top = form.getBoundingClientRect().top + window.scrollY - 120;
      if (form.getBoundingClientRect().top < 80) window.scrollTo({ top, behavior: 'smooth' });
    }
  };

  if (useSteps) {
    form.classList.add('iform--steps');
    show(0, false);
    next?.addEventListener('click', () => {
      const errors = validate(form, steps[current], isMain, vocab);
      if (render(form, errors)) show(current + 1, true);
    });
    prev?.addEventListener('click', () => show(current - 1, true));
  }

  if (isMain) prefill(form, vocab, (stepIndex) => useSteps && show(stepIndex, false));

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
    const errors = validate(form, form, isMain, vocab);
    if (!render(form, errors)) {
      if (useSteps) {
        const first = steps.findIndex((s) => Object.keys(errors).some((n) => s.querySelector(`[name="${n}"]`)));
        if (first >= 0 && first !== current) {
          show(first, false);
          render(form, errors);
        }
      }
      return;
    }

    // Ausfüllzeit in Millisekunden – gemessen mit der Uhr DIESES Geräts, also unabhängig
    // davon, ob sie mit der des Servers übereinstimmt.
    setValue(form, 't', String(Date.now() - loadedAt));
    const data = new FormData(form);
    prune(data);
    form.setAttribute('aria-busy', 'true');
    if (submit) submit.disabled = true;
    try {
      const res = await fetch(form.action, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
      const body = (await res.json().catch(() => ({}))) as { ok?: boolean; fields?: Errors; message?: string };
      if (res.ok && body.ok) {
        track('form_submit', { form: form.dataset.form, kind: str(data.get('kind')), urgency: str(data.get('urgency')) || 'keine' });
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
        if (useSteps) {
          const first = steps.findIndex((s) => Object.keys(body.fields!).some((n) => s.querySelector(`[name="${n}"]`)));
          if (first >= 0) {
            show(first, true);
            render(form, body.fields);
          }
        }
        return;
      }
      fail(form, failPanel, vocab, res.status, body.message);
    } catch {
      fail(form, failPanel, vocab, 0);
    } finally {
      form.removeAttribute('aria-busy');
      if (submit) submit.disabled = false;
    }
  });
}

// ------------------------------------------------------------------ Prüfen

function validate(form: HTMLFormElement, scope: Element, isMain: boolean, vocab: Vocab): Errors {
  const m = vocab.messages;
  const errors: Errors = {};
  const has = (name: string) => Boolean(scope.querySelector(`[name="${name}"]`));
  const kind = checked(form, 'kind') || value(form, 'kind');

  if (has('kind') && !kind) errors.kind = m.kind;
  if (isMain && has('need') && (kind === 'kran' || kind === 'fahrmischer') && !checked(form, 'need')) errors.need = m.need;
  if (has('part') && kind === 'teile' && !value(form, 'part')) errors.part = m.part;
  const cranesEl = scope.querySelector<HTMLInputElement>('[name="cranes"]');
  if (cranesEl && kind === 'abo') {
    const cranes = cranesEl.value.trim();
    if ((!cranes && cranesEl.required) || (cranes && !/^[1-9]\d{0,2}$/.test(cranes))) errors.cranes = m.cranes;
  }
  if (isMain && has('urgency') && !checked(form, 'urgency')) errors.urgency = m.urgency;
  const year = value(form, 'year');
  if (has('year') && year && !/^(19|20)\d{2}$/.test(year)) errors.year = m.year;
  if (has('place') && !value(form, 'place')) errors.place = m.place;
  if (!isMain && has('message') && !value(form, 'message')) errors.message = m.message;
  const photos = scope.querySelector<HTMLInputElement>('input[type="file"][name="photos"]');
  if (photos) Object.assign(errors, photoErrors(form, photos, vocab));

  if (has('name') && !value(form, 'name')) errors.name = m.name;
  if (has('phone') || has('email')) {
    const phone = value(form, 'phone');
    const email = value(form, 'email');
    const pref = checked(form, 'contact_pref');
    if (!phone && !email) {
      errors.phone = m.contact;
    } else {
      if (phone && !PHONE.test(phone)) errors.phone = m.phone;
      if (email && !EMAIL.test(email)) errors.email = m.email;
      if (pref === 'telefon' && !phone) errors.phone = m.prefPhone;
      if (pref === 'email' && !email) errors.email = m.prefEmail;
    }
  }
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
  const related = name === 'phone' || name === 'email' || name === 'contact_pref' ? ['phone', 'email'] : [name];
  for (const n of related) {
    const box = form.querySelector<HTMLElement>(`[data-error-for="${n}"]`);
    if (box) box.hidden = true;
    form.querySelectorAll(`[name="${n}"]`).forEach((el) => el.removeAttribute('aria-invalid'));
  }
}

// ------------------------------------------------------------------ Hilfen

function value(form: HTMLFormElement, name: string): string {
  const el = form.querySelector<HTMLInputElement>(`[name="${name}"]:not([type="radio"]):not([type="file"])`);
  return el?.value.trim() ?? '';
}
function checked(form: HTMLFormElement, name: string): string {
  return form.querySelector<HTMLInputElement>(`input[name="${name}"]:checked`)?.value ?? '';
}
function setValue(form: HTMLFormElement, name: string, v: string): void {
  const el = form.querySelector<HTMLInputElement | HTMLTextAreaElement>(`[name="${name}"]`);
  if (el) el.value = v;
}
const str = (v: FormDataEntryValue | null) => (typeof v === 'string' ? v : '');
const mb = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;

/** Angaben, die zum gewählten Anliegen nicht passen, gar nicht erst senden. */
function prune(data: FormData): void {
  const kind = str(data.get('kind'));
  if (kind !== 'kran' && kind !== 'fahrmischer') data.delete('need');
  if (kind !== 'teile') {
    data.delete('part');
    data.delete('mixer');
  }
  if (kind !== 'abo') data.delete('cranes');
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

function prefill(form: HTMLFormElement, vocab: Vocab, goTo: (stepIndex: number) => void): void {
  const q = new URLSearchParams(location.search);
  const pick = (name: string, v: string | null) => {
    if (!v) return false;
    const radio = form.querySelector<HTMLInputElement>(`input[name="${name}"][value="${CSS.escape(v)}"]`);
    if (radio) radio.checked = true;
    return Boolean(radio);
  };
  const kindSet = pick('kind', q.get('typ'));
  pick('need', q.get('thema'));
  if (q.get('dringend') === '1') pick('urgency', 'dringend');
  if (q.get('teil')) setValue(form, 'part', q.get('teil')!.slice(0, 200));
  if (q.get('fahrmischer')) setValue(form, 'mixer', q.get('fahrmischer')!.slice(0, 160));
  if (q.get('krane') && /^[1-9]\d{0,2}$/.test(q.get('krane')!)) setValue(form, 'cranes', q.get('krane')!);
  const tier = vocab.tiers?.[q.get('stufe') ?? ''];
  if (tier && !value(form, 'message')) setValue(form, 'message', `Interesse an der Abo-Stufe «${tier}».`);
  if (kindSet) goTo(1);
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

/** mailto-Link mit allen Eingaben – derselbe Betreff und dieselben Wörter wie die E-Mail des Servers. */
function mailto(form: HTMLFormElement, vocab: Vocab): string {
  const data = new FormData(form);
  prune(data);
  const get = (n: string) => str(data.get(n)).trim();
  const kind = get('kind');
  const urgency = get('urgency');
  const who = get('company') || get('name');
  const tags = ['Anfrage', vocab.kindSubject?.[kind] ?? kind, urgency ? vocab.urgencySubject?.[urgency] : ''].filter(Boolean);
  const subject = `${tags.map((t) => `[${t}]`).join('')} ${who}${get('place') ? ` – ${get('place')}` : ''}`.trim();
  const shown: Record<string, string> = {
    kind: vocab.kind?.[kind] ?? kind,
    need: vocab.need?.[get('need')] ?? '',
    urgency: vocab.urgency?.[urgency] ?? '',
    contact_pref: vocab.pref?.[get('contact_pref')] ?? '',
    message: get('message').slice(0, 1200),
  };
  const lines = vocab.labels.map(([field, label]) => [label, field in shown ? shown[field] : get(field)] as const);
  const photos = form.querySelector<HTMLInputElement>('input[type="file"]')?.files?.length ?? 0;
  const body = lines.filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join('\n') +
    (photos ? `\n\nFotos: bitte ${photos === 1 ? 'das Foto' : `die ${photos} Fotos`} an diese E-Mail anhängen.` : '');
  const to = form.dataset.mail ?? '';
  return `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
