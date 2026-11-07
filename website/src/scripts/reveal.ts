/**
 * Einblenden beim Hineinscrollen – einmal, nur transform/opacity, nie bei reduzierter
 * Bewegung. Was beim Laden schon sichtbar ist, bleibt unangetastet (kein Aufblitzen).
 * Ohne JS ist alles sofort da: die Ausgangslage setzt erst dieses Skript.
 *
 * [data-reveal]          einzelnes Element
 * [data-reveal-stagger]  die ersten vier Kinder um je 60 ms versetzt
 * [data-kranbahn]        die Kranbahn-Linie zeichnet sich einmal ein
 */
export function initReveal(): void {
  if (!('IntersectionObserver' in window)) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const lines = document.querySelectorAll<HTMLElement>('[data-kranbahn]');
  if (reduced) {
    lines.forEach((l) => l.classList.add('is-drawn'));
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const el = entry.target as HTMLElement;
        if (el.hasAttribute('data-kranbahn')) {
          el.classList.remove('is-armed');
          el.classList.add('is-drawn');
        } else {
          el.classList.add('reveal-in');
          el.classList.remove('reveal-pending');
        }
        io.unobserve(el);
      }
    },
    { rootMargin: '0px 0px -6% 0px', threshold: 0.05 },
  );

  const below = (el: Element) => el.getBoundingClientRect().top > window.innerHeight * 0.92;

  document.querySelectorAll<HTMLElement>('[data-reveal]').forEach((el) => {
    if (!below(el)) return;
    el.classList.add('reveal-pending');
    io.observe(el);
  });
  document.querySelectorAll<HTMLElement>('[data-reveal-stagger]').forEach((group) => {
    Array.from(group.children).forEach((child, i) => {
      if (!(child instanceof HTMLElement) || !below(child)) return;
      child.style.transitionDelay = `${Math.min(i, 3) * 60}ms`;
      child.classList.add('reveal-pending');
      io.observe(child);
    });
  });
  lines.forEach((line) => {
    if (!below(line)) {
      line.classList.add('is-drawn');
      return;
    }
    line.classList.add('is-armed');
    io.observe(line);
  });
}
