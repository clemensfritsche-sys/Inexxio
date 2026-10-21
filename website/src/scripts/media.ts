/**
 * Videos (components/Media.astro) spielt der Browser selbst ab (autoplay, muted, playsinline).
 * Nur bei «reduzierter Bewegung» halten wir sie an – dann bleibt das Standbild (poster).
 */
export function initMedia(): void {
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.querySelectorAll<HTMLVideoElement>('video[data-media-video]').forEach((v) => {
    v.removeAttribute('autoplay');
    v.pause();
  });
}
