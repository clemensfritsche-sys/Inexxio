/**
 * Videos (components/Media.astro) spielt der Browser selbst ab (autoplay, muted, playsinline).
 * Ihre Quelle trägt `media` = VIDEO_MEDIA: auf schmalen Bildschirmen und bei «reduzierter
 * Bewegung» passt sie nicht, und es bleibt beim Standbild (poster) – ohne Video zu laden.
 *
 * Hier geschieht nur zweierlei:
 *  1. Ein Browser, der `media` an `<source>` nicht kennt, hätte die Quelle trotzdem genommen –
 *     ihm wird sie wieder abgenommen (dieselbe Regel, kein zweiter Massstab).
 *  2. **Der Knopf der Bühne hält die Bewegung an** (WCAG 2.2.2): Video und langsamen Zoom. Er
 *     erscheint nur, wo sich wirklich etwas bewegt.
 */

/** Wann das Bühnenvideo geladen und gespielt wird – EINE Stelle für HTML und Skript. */
export const VIDEO_MEDIA = '(min-width: 768px) and (prefers-reduced-motion: no-preference)';

const STILL = 'is-still';

export function initMedia(): void {
  const fits = window.matchMedia(VIDEO_MEDIA).matches;
  if (!fits) {
    document.querySelectorAll<HTMLVideoElement>('video[data-media-video]').forEach((v) => {
      v.querySelectorAll('source').forEach((s) => s.remove());
      v.removeAttribute('autoplay');
      v.load();
    });
  }
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll<HTMLButtonElement>('button[data-motion-toggle]').forEach((btn) => {
    const scope = btn.closest<HTMLElement>('[data-motion]');
    if (!scope || reduced) return;
    const video = scope.querySelector<HTMLVideoElement>('video[data-media-video]');
    const moves = video ? fits : Boolean(scope.querySelector('.photo'));
    if (!moves) return;
    const show = (still: boolean): void => {
      scope.classList.toggle(STILL, still);
      btn.setAttribute('aria-pressed', String(still));
      btn.setAttribute('aria-label', (still ? btn.dataset.labelPlay : btn.dataset.labelPause) ?? '');
    };
    btn.hidden = false;
    btn.addEventListener('click', () => {
      const still = !scope.classList.contains(STILL);
      show(still);
      if (!video) return;
      if (still) video.pause();
      // Lässt der Browser das Abspielen nicht zu, steht es still – und der Knopf sagt es.
      else video.play().catch(() => show(true));
    });
  });
}
