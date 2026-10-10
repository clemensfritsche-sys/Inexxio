/** Mobile Aktionsleiste erst zeigen, wenn der Seitenkopf aus dem Bild gescrollt ist. */
export function initMobileBar(): void {
  const bar = document.querySelector<HTMLElement>('[data-mobilebar]');
  if (!bar) return;
  const hero = document.querySelector('[data-hero]');
  if (!hero || !('IntersectionObserver' in window)) {
    bar.classList.add('is-visible');
    return;
  }
  new IntersectionObserver(([entry]) => {
    bar.classList.toggle('is-visible', !entry.isIntersecting);
  }).observe(hero);
}
