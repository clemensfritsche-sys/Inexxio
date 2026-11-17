/**
 * Schemata spielen, wenn man sie sieht – nicht beim Laden der Seite.
 *
 * Die Bewegungen der Schemata (Garantie, INEXXIO 365, Weg mit Punkt, Standort-Puls) laufen
 * zweimal und halten dann im Endzustand an (WCAG 2.2.2). Als CSS-Animation begannen sie beim
 * Laden – wer erst nach 20 s hinscrollte, sah nur noch den Endzustand. Darum gilt:
 *
 *   [data-play]  ohne .is-playing steht alles darin still (global.css), mit läuft es von vorn.
 *
 * Kommt der Bereich ins Bild, beginnt die Bewegung; verlässt er es, wird sie zurückgesetzt, beim
 * nächsten Hinsehen läuft sie wieder. `replay` startet sie von vorn (z. B. eine Frage wird
 * geöffnet und zeigt ihr Bild). Ohne JS steht der Endzustand – er trägt die Aussage allein.
 */
const PLAYING = 'is-playing';

export function replay(el: HTMLElement): void {
  el.classList.remove(PLAYING);
  void el.offsetWidth; // erzwingt den Neustart der Animation
  el.classList.add(PLAYING);
}

export function initPlay(): void {
  const all = document.querySelectorAll<HTMLElement>('[data-play]');
  if (!all.length) return;
  if (!('IntersectionObserver' in window)) {
    all.forEach((el) => el.classList.add(PLAYING));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) (e.target as HTMLElement).classList.toggle(PLAYING, e.isIntersecting);
  }, { threshold: 0.15 });
  all.forEach((el) => io.observe(el));
}
