/**
 * Karussell (v4: Bereiche schmal, Ratgeber): eine waagrechte Spur mit Einrasten, Punkte
 * darunter, auf Wunsch Pfeile. Das Element in der Mitte ist `is-active` (es spielt, es ist
 * hell); `carousel:change` meldet den Wechsel.
 *   [data-carousel] (data-start = erster Eintrag in der Mitte)
 *     [data-rail] > [data-item]…   [data-prev] [data-next]   [data-dots] (data-label)
 * Mit der Maus lässt sich die Spur ziehen (Touch und Trackpad scrollen ohnehin selbst); nach
 * dem Loslassen rastet sie am nächsten Eintrag ein, ein Zug klickt nicht versehentlich.
 * Ohne JS bleibt es eine scrollbare Reihe.
 */
export function initCarousels(): void {
  document.querySelectorAll<HTMLElement>('[data-carousel]').forEach(setup);
}

function setup(root: HTMLElement): void {
  if (root.dataset.ready) return;
  const track = root.querySelector<HTMLElement>('[data-rail]');
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
  drag(track, items, () => active, go);
  root.querySelector('[data-next]')?.addEventListener('click', () => go(active + 1));
  window.addEventListener('resize', () => { active = -1; update(); });
  requestAnimationFrame(() => {
    go(Number(root.dataset.start ?? 0), false);
    update();
  });
}

/** Ziehen mit der Maus: die Spur folgt dem Zeiger, danach rastet sie ein. */
function drag(track: HTMLElement, items: HTMLElement[], current: () => number, go: (i: number) => void): void {
  let start: { x: number; left: number; from: number; id: number } | null = null;
  let moved = false;
  track.addEventListener('dragstart', (e) => e.preventDefault());
  track.addEventListener('pointerdown', (e) => {
    if (e.pointerType !== 'mouse' || e.button !== 0 || track.scrollWidth <= track.clientWidth) return;
    start = { x: e.clientX, left: track.scrollLeft, from: current(), id: e.pointerId };
    moved = false;
  });
  track.addEventListener('pointermove', (e) => {
    if (!start || e.pointerId !== start.id) return;
    const dx = e.clientX - start.x;
    if (!moved && Math.abs(dx) < 6) return;
    if (!moved) {
      moved = true;
      track.classList.add('is-dragging');
      track.setPointerCapture(start.id);
    }
    track.scrollLeft = start.left - dx;
  });
  const end = (e: PointerEvent) => {
    if (!start || e.pointerId !== start.id) return;
    const dx = e.clientX - start.x;
    const from = start.from;
    start = null;
    if (!moved) return;
    track.classList.remove('is-dragging');
    let to = current();
    // Ein kurzer, kräftiger Zug blättert auch dann eine Karte weiter, wenn die Mitte noch nicht erreicht ist.
    if (to === from && Math.abs(dx) > 80) to = from - Math.sign(dx);
    go(Math.max(0, Math.min(items.length - 1, to)));
  };
  track.addEventListener('pointerup', end);
  track.addEventListener('pointercancel', end);
  // Ein Zug ist kein Klick auf den Artikel darunter.
  track.addEventListener('click', (e) => {
    if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
  }, true);
}
