/**
 * Grosse Zahlen zählen hoch, sobald sie ins Bild kommen (wie bei Porsche): [data-count="1982"].
 * Im HTML steht der Endwert (Suchmaschinen, ohne JS, Drucken). Auf 0 gesetzt wird nur, was beim
 * Laden noch unter dem Bild liegt – nichts blitzt. Bei «reduzierter Bewegung»: nichts.
 */
export function initCountUp(): void {
  if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const els = Array.from(document.querySelectorAll<HTMLElement>('[data-count]'))
    .filter((el) => !el.dataset.countReady && /^\d+$/.test(el.dataset.count ?? ''));
  const DUR = 1600;
  const ease = (t: number) => 1 - Math.pow(1 - t, 3);
  const run = (el: HTMLElement) => {
    const end = Number(el.dataset.count);
    const t0 = performance.now();
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / DUR);
      el.textContent = String(Math.round(end * ease(p)));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      io.unobserve(e.target);
      run(e.target as HTMLElement);
    }
  }, { threshold: 0.6 });
  for (const el of els) {
    el.dataset.countReady = '1';
    if (el.getBoundingClientRect().top < window.innerHeight * 0.9) continue;
    el.textContent = '0';
    io.observe(el);
  }
}
