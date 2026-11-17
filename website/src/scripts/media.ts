/**
 * Videos (components/Media.astro) spielt der Browser selbst ab (autoplay, muted, playsinline).
 * Ihre Quellen tragen `media`: schmale Bildschirme bekommen die Hochkant-Fassung (VIDEO_NARROW),
 * alle anderen die breite; bei «reduzierter Bewegung» passt keine (VIDEO_MOTION) und es bleibt
 * beim Standbild, ohne dass Video geladen wird.
 *
 * Hier geschieht dreierlei:
 *  1. Ein Browser, der `media` an `<source>` nicht kennt, bekommt die Quellen abgenommen, die
 *     nicht passen (dieselbe Regel, kein zweiter Massstab).
 *  2. **Der Knopf der Bühne zeigt, was wirklich geschieht** (WCAG 2.2.2): er folgt den Ereignissen
 *     des Videos (`playing` · `pause`), nicht einer Annahme. Verweigert der Browser das
 *     automatische Abspielen (Stromsparmodus, Datensparen), steht ▶ da und spielt auf Druck.
 *  3. **Abspielen auf Abruf** auch bei «reduzierter Bewegung»: dann setzt der Knopf die passende
 *     Quelle erst beim Drücken (`data-src-*`) – vorher wird nichts geladen.
 */

/** Wann das Bühnenvideo von selbst spielt – EINE Stelle für HTML und Skript. */
export const VIDEO_MOTION = '(prefers-reduced-motion: no-preference)';
/** Wann die Hochkant-Fassung gilt. */
export const VIDEO_NARROW = '(max-width: 767px)';

const STILL = 'is-still';

/** Die Adresse der Fassung, die zu diesem Bildschirm passt. */
function srcFor(video: HTMLVideoElement): string | undefined {
  const narrow = window.matchMedia(VIDEO_NARROW).matches ? video.dataset.srcNarrow : undefined;
  return narrow ?? video.dataset.srcWide;
}

/** Quellen, deren `media` nicht passt, abnehmen (für Browser ohne `media` an `<source>`). */
function dropUnfit(video: HTMLVideoElement): void {
  let chosen = false;
  video.querySelectorAll('source').forEach((s) => {
    if (!s.media || window.matchMedia(s.media).matches) return;
    if (video.currentSrc && video.currentSrc === s.src) chosen = true;
    s.remove();
  });
  // Nur neu laden, wenn der Browser eine unpassende Quelle schon gewählt hatte.
  if (chosen) video.load();
}

function bindToggle(btn: HTMLButtonElement, scope: HTMLElement, video: HTMLVideoElement | null): void {
  const show = (still: boolean): void => {
    scope.classList.toggle(STILL, still);
    btn.setAttribute('aria-pressed', String(still));
    btn.setAttribute('aria-label', (still ? btn.dataset.labelPlay : btn.dataset.labelPause) ?? '');
  };
  btn.hidden = false;
  if (!video) {
    btn.addEventListener('click', () => show(!scope.classList.contains(STILL)));
    return;
  }
  video.addEventListener('playing', () => show(false));
  video.addEventListener('pause', () => show(true));
  show(video.paused);
  // Ein verweigertes automatisches Abspielen meldet sich hier – der Knopf zeigt dann ▶.
  if (video.autoplay && video.querySelector('source')) video.play().catch(() => show(true));
  btn.addEventListener('click', () => {
    if (!video.paused) { video.pause(); return; }
    if (!video.currentSrc) {
      const src = srcFor(video);
      if (!src) return;
      video.src = src;
    }
    video.play().catch(() => show(true));
  });
}

export function initMedia(): void {
  const videos = document.querySelectorAll<HTMLVideoElement>('video[data-media-video]');
  videos.forEach(dropUnfit);
  const reduced = !window.matchMedia(VIDEO_MOTION).matches;
  document.querySelectorAll<HTMLButtonElement>('button[data-motion-toggle]').forEach((btn) => {
    const scope = btn.closest<HTMLElement>('[data-motion]');
    if (!scope) return;
    const video = scope.querySelector<HTMLVideoElement>('video[data-media-video]');
    // Ein Foto zoomt nur ohne «reduzierte Bewegung»; ein Video lässt sich immer abspielen.
    if (!video && (reduced || !scope.querySelector('.photo'))) return;
    bindToggle(btn, scope, video);
  });
}
