/**
 * Neutraler Mess-Helper. Standardmässig AUS: ohne konfigurierten Anbieter wird nichts
 * gesendet – das Ereignis geht nur als DOM-Event `ix:track` durch die Seite (prüfbar,
 * ohne dass Daten das Gerät verlassen).
 *
 * Ereignisse: form_start · form_submit (Typ, Dringlichkeit) · tel_click · pikett_click ·
 * mailto_click · abo_interest · part_inquiry
 */
export type TrackProps = Record<string, string | number | boolean | undefined>;

type Plausible = (event: string, opts?: { props?: TrackProps }) => void;

export function track(event: string, props: TrackProps = {}): void {
  const detail = { event, props: { page: location.pathname, ...props } };
  document.dispatchEvent(new CustomEvent('ix:track', { detail }));
  const provider = document.documentElement.dataset.analytics;
  const plausible = (window as unknown as { plausible?: Plausible }).plausible;
  if (provider === 'plausible' && typeof plausible === 'function') {
    plausible(event, { props: detail.props });
  }
}

export function initTracking(): void {
  document.addEventListener('click', (e) => {
    const el = (e.target as Element | null)?.closest<HTMLElement>('[data-track]');
    if (!el?.dataset.track) return;
    const extra: TrackProps = {};
    for (const [k, v] of Object.entries(el.dataset)) {
      if (k.startsWith('trackProp') && v) extra[k.slice(9).toLowerCase()] = v;
    }
    track(el.dataset.track, { href: el.getAttribute('href') ?? undefined, ...extra });
  });
  document.addEventListener('focusin', (e) => {
    const form = (e.target as Element | null)?.closest<HTMLFormElement>('form[data-form]');
    if (!form || form.dataset.started) return;
    form.dataset.started = '1';
    track('form_start', { form: form.dataset.form });
  });
}
