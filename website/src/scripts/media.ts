/**
 * Videos (components/Media.astro): bei «reduzierter Bewegung» angehalten – dann bleibt das
 * erste Bild stehen. Ausserhalb des Bildes pausiert, damit nichts im Hintergrund rechnet.
 * Verweigert das Handy das automatische Abspielen, startet es bei der ersten Berührung.
 */
export function initMedia(): void {
  const videos = Array.from(document.querySelectorAll<HTMLVideoElement>('video[data-media-video]'));
  if (!videos.length) return;
  // Erst zeigen, wenn es läuft (CSS: video[data-media-video] ist bis dahin unsichtbar).
  const show = (v: HTMLVideoElement) => v.classList.add('is-playing');
  for (const v of videos) {
    v.muted = true; // Safari prüft die Eigenschaft, nicht nur das Attribut
    v.addEventListener('playing', () => show(v));
    // Lief es schon, bevor dieses Skript kam (Autoplay aus dem Cache, Handy), ist «playing»
    // bereits vorbei – dann jetzt zeigen, sonst bliebe es unsichtbar unter dem Foto.
    if (!v.paused && v.readyState > 2) show(v);
  }
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    for (const v of videos) { v.removeAttribute('autoplay'); v.pause(); }
    return;
  }
  const visible = new Set<HTMLVideoElement>();
  const play = (v: HTMLVideoElement) => v.play().then(() => show(v), () => { armRetry(); });
  // Ein abgelehntes Abspielen darf eine Geste nachholen (Stromsparmodus, Datensparen).
  let armed = false;
  const armRetry = () => {
    if (armed) return;
    armed = true;
    const retry = () => {
      for (const ev of ['touchend', 'click', 'keydown']) document.removeEventListener(ev, retry, true);
      armed = false;
      for (const v of visible) if (v.paused) void play(v);
    };
    for (const ev of ['touchend', 'click', 'keydown']) document.addEventListener(ev, retry, { capture: true, passive: true });
  };
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      const v = e.target as HTMLVideoElement;
      if (e.isIntersecting) { visible.add(v); void play(v); }
      else { visible.delete(v); v.pause(); }
    }
  });
  for (const v of videos) io.observe(v);
}
