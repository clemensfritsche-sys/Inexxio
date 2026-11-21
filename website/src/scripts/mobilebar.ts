/** Mobile Aktionsleiste erst zeigen, wenn der Seitenkopf aus dem Bild gescrollt ist. */
export function initMobileBar(): void {
  const bar = document.querySelector<HTMLElement>('[data-mobilebar]');
  if (!bar) return;
  // «Anfrage» springt zur Anfrage dieser Seite, wenn es eine gibt (ContactSection, #anfrage) – sonst /kontakt.
  const cta = bar.querySelector<HTMLAnchorElement>('[data-mobilebar-cta]');
  if (cta && document.getElementById('anfrage')) cta.setAttribute('href', '#anfrage');
  const hero = document.querySelector('[data-hero]');
  if (!hero || !('IntersectionObserver' in window)) {
    bar.classList.add('is-visible');
    return;
  }
  new IntersectionObserver(([entry]) => {
    bar.classList.toggle('is-visible', !entry.isIntersecting);
  }).observe(hero);
}
