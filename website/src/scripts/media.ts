/**
 * Videos (components/Media.astro): bei «reduzierter Bewegung» angehalten – dann bleibt das
 * erste Bild stehen. Ausserhalb des Bildes pausiert, damit nichts im Hintergrund rechnet.
 */
export function initMedia(): void {
  const videos = Array.from(document.querySelectorAll<HTMLVideoElement>('video[data-media-video]'));
  if (!videos.length) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    for (const v of videos) { v.removeAttribute('autoplay'); v.pause(); }
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      const v = e.target as HTMLVideoElement;
      if (e.isIntersecting) void v.play().catch(() => { /* Autoplay verweigert – Standbild bleibt */ });
      else v.pause();
    }
  });
  for (const v of videos) io.observe(v);
}
