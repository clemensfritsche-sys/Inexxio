/**
 * Karussell (v4: Bereiche schmal, Ratgeber): eine waagrechte Spur mit Einrasten, Punkte
 * darunter, auf Wunsch Pfeile. Das Element in der Mitte ist `is-active` (es spielt, es ist
 * hell); `carousel:change` meldet den Wechsel.
 *   [data-carousel] (data-start = erster Eintrag in der Mitte)
 *     [data-track] > [data-item]…   [data-prev] [data-next]   [data-dots] (data-label)
 * Ohne JS bleibt es eine scrollbare Reihe.
 */
export function initCarousels(): void {
  document.querySelectorAll<HTMLElement>('[data-carousel]').forEach(setup);
}

function setup(root: HTMLElement): void {
  if (root.dataset.ready) return;
  const track = root.querySelector<HTMLElement>('[data-track]');
  if (!track) return;
  root.dataset.ready = '1';
  const items = Array.from(track.querySelectorAll<HTMLElement>('[data-item]'));
  const dots = root.querySelector<HTMLElement>('[data-dots]');
  const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const center = (el: HTMLElement) => el.offsetLeft + el.offsetWidth / 2;
  const go = (i: number, animate = smooth) => {
    const el = items[Math.max(0, Math.min(items.length - 1, i))];
    if (el) track.scrollTo({ left: center(el) - track.clientWidth / 2, behavior: animate ? 'smooth' : 'auto' });
  };
  const buttons = items.map((_, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cdot';
    b.setAttribute('aria-label', `${dots?.dataset.label ?? 'Eintrag'} ${i + 1}`);
    b.addEventListener('click', () => go(i));
    dots?.append(b);
    return b;
  });
  let active = -1;
  const update = () => {
    const mid = track.scrollLeft + track.clientWidth / 2;
    let best = 0;
    let dist = Infinity;
    items.forEach((el, i) => {
      const d = Math.abs(center(el) - mid);
      if (d < dist) { dist = d; best = i; }
    });
    if (best === active) return;
    active = best;
    items.forEach((el, i) => el.classList.toggle('is-active', i === best));
    buttons.forEach((b, i) => b.setAttribute('aria-current', String(i === best)));
    root.dispatchEvent(new CustomEvent('carousel:change', { detail: best }));
  };
  let ticking = false;
  track.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { ticking = false; update(); });
  }, { passive: true });
  root.querySelector('[data-prev]')?.addEventListener('click', () => go(active - 1));
  root.querySelector('[data-next]')?.addEventListener('click', () => go(active + 1));
  window.addEventListener('resize', () => { active = -1; update(); });
  requestAnimationFrame(() => {
    go(Number(root.dataset.start ?? 0), false);
    update();
  });
}
