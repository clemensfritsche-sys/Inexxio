/**
 * Die Website-Statistik (Backend `services/site_stats`) – jede Seite meldet sich selbst.
 *
 * - Ohne Cookie und ohne Speicher im Browser: jede Meldung ist ein kurzer `sendBeacon` an
 *   `/api/v1/public/page`; den Besuch erkennt der Server für einen Tag, ohne die IP zu speichern.
 * - Gemeldet wird: die Ansicht (mit Herkunft und Kampagne der Adresse), die sichtbare Lesezeit,
 *   ein Klick auf Telefon, Mail oder Route, die Schritte des Anfrage-Formulars und die Ladezeit
 *   (LCP, CLS – wie Google sie misst). Die Anfrage selbst zählt der Server.
 * - Nur auf der Website (`html[data-site]`) – Kopf und Fuss reisen mit ins ERP, die Statistik nicht.
 *   Wer als Personal angemeldet ist (`html[data-account="staff"]`), zählt nicht.
 */
const URL_ = '/api/v1/public/page';

type Hit = { k: string; v?: number; r?: string; h?: string; q?: string };

function counts(): boolean {
  const root = document.documentElement;
  return root.hasAttribute('data-site') && root.dataset.account !== 'staff'
    && !/^(localhost|127\.|\[::1\])/.test(location.hostname);
}

function send(hit: Hit): void {
  if (!counts()) return;
  const body = JSON.stringify({ ...hit, p: location.pathname });
  try {
    if (navigator.sendBeacon?.(URL_, body)) return;
  } catch { /* weiter mit fetch */ }
  fetch(URL_, { method: 'POST', body, keepalive: true, credentials: 'omit' }).catch(() => undefined);
}

function view(): void {
  send({ k: 'view', r: document.referrer, h: location.hostname, q: location.search });
}

/** Sichtbare Lesezeit: gemeldet bei jedem Verlassen (Tab, Seite), immer nur der neue Teil. */
function readingTime(): void {
  let since = document.visibilityState === 'visible' ? performance.now() : 0;
  let shown = 0;
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      since = performance.now();
      return;
    }
    if (since) shown += performance.now() - since;
    since = 0;
    const s = Math.round(shown / 1000);
    if (s >= 1) send({ k: 'leave', v: Math.min(s, 1800) });
    shown = 0;
  });
}

function clicks(): void {
  document.addEventListener('click', (e) => {
    const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
    if (!a) return;
    const href = a.getAttribute('href') ?? '';
    if (href.startsWith('tel:')) send({ k: 'call' });
    else if (href.startsWith('mailto:')) send({ k: 'mail' });
    else if (/google\.[a-z.]+\/maps|maps\.google\.|maps\.apple\.com|goo\.gl\/maps/.test(href)) send({ k: 'route' });
  }, { capture: true });
}

/** Das Anfrage-Formular: gesehen · angefangen · Schritt 2 (gesendet zählt der Server). */
function form(): void {
  const forms = document.querySelectorAll<HTMLFormElement>('form[data-inquiry]');
  if (!forms.length) return;
  const once = new Set<string>();
  const mark = (k: string) => { if (!once.has(k)) { once.add(k); send({ k }); } };
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      if (entries.some((x) => x.isIntersecting)) { mark('form_view'); io.disconnect(); }
    }, { threshold: 0.4 });
    forms.forEach((f) => io.observe(f));
  }
  forms.forEach((f) => {
    f.addEventListener('input', () => mark('form_start'), { once: true });
    new MutationObserver(() => { if (f.dataset.step === '2') mark('form_step'); })
      .observe(f, { attributes: true, attributeFilter: ['data-step'] });
  });
}

/** Ladezeit: grösstes Bild/Text sichtbar (LCP) und Verrutschen (CLS), gemeldet beim ersten Verlassen. */
function speed(): void {
  if (!('PerformanceObserver' in window)) return;
  let lcp = 0;
  let cls = 0;
  try {
    new PerformanceObserver((l) => { const e = l.getEntries(); lcp = e[e.length - 1]?.startTime ?? lcp; })
      .observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => {
      for (const e of l.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]) {
        if (!e.hadRecentInput) cls += e.value;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  } catch { return; }
  const report = () => {
    if (document.visibilityState !== 'hidden') return;
    document.removeEventListener('visibilitychange', report);
    if (lcp > 0) send({ k: 'lcp', v: Math.round(Math.min(lcp, 60_000)) });
    send({ k: 'cls', v: Math.round(Math.min(cls, 5) * 1000) });
  };
  document.addEventListener('visibilitychange', report);
}

export function initStats(): void {
  if (!counts()) return;
  view();
  readingTime();
  clicks();
  form();
  speed();
  // Zurück aus dem Verlauf (bfcache) ist eine neue Ansicht.
  addEventListener('pageshow', (e) => { if ((e as PageTransitionEvent).persisted) view(); });
}
