/**
 * Karussell (v4: Bereiche schmal, Felder schmal, Ratgeber): eine waagrechte Spur mit Einrasten,
 * Punkte darunter, auf Wunsch Pfeile. Das Element in der Mitte ist `is-active` (es spielt, es ist
 * hell); `carousel:change` meldet den Wechsel.
 *   [data-carousel] (beginnt immer beim mittleren Eintrag)
 *     [data-rail] > [data-item]…   [data-prev] [data-next]   [data-dots] (data-label)
 *
 * **Endlos** (Rückmeldung 22.11.2026): vor und hinter die Einträge kommt je eine Kopie der ganzen
 * Reihe (`data-clone`, für Screenreader und Tastatur unsichtbar). Kommt die Spur auf einer Kopie zur
 * Ruhe, springt sie ohne Animation auf das Original an derselben Stelle – man sieht es nicht, und
 * nach dem letzten kommt wieder der erste. Die Kopien gibt es nur, solange die Spur wirklich scrollt
 * (`is-loop`); breit, wo die Einträge nebeneinander stehen, bleiben sie verborgen.
 *
 * Mit der Maus lässt sich die Spur ziehen (Touch und Trackpad scrollen ohnehin selbst); nach
 * dem Loslassen rastet sie am nächsten Eintrag ein, ein Zug klickt nicht versehentlich.
 * Ohne JS bleibt es eine scrollbare Reihe.
 */
export function initCarousels(): void {
  document.querySelectorAll<HTMLElement>('[data-carousel]').forEach(setup);
}

/** Eine Kopie eines Eintrags: ohne Ids, nicht fokussierbar, für Screenreader nicht da. */
function cloneOf(el: HTMLElement): HTMLElement {
  const c = el.cloneNode(true) as HTMLElement;
  c.dataset.clone = '';
  c.removeAttribute('id');
  c.setAttribute('aria-hidden', 'true');
  c.querySelectorAll('[id]').forEach((n) => n.removeAttribute('id'));
  c.querySelectorAll<HTMLElement>('a, button, input, select, textarea, [tabindex]').forEach((n) => n.setAttribute('tabindex', '-1'));
  return c;
}

function setup(root: HTMLElement): void {
  if (root.dataset.ready) return;
  const track = root.querySelector<HTMLElement>('[data-rail]');
  if (!track) return;
  root.dataset.ready = '1';
  const real = Array.from(track.querySelectorAll<HTMLElement>('[data-item]'));
  const n = real.length;
  if (!n) return;
  const before = real.map(cloneOf);
  const after = real.map(cloneOf);
  track.prepend(...before);
  track.append(...after);
  const all = [...before, ...real, ...after];
  const dots = root.querySelector<HTMLElement>('[data-dots]');
  const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const center = (el: HTMLElement) => el.offsetLeft + el.offsetWidth / 2;
  const looping = () => root.classList.contains('is-loop');
  const to = (el: HTMLElement, behavior: ScrollBehavior) =>
    track.scrollTo({ left: center(el) - track.clientWidth / 2, behavior });
  /** Ein Platz in der ganzen Spur (mit Kopien); ohne Schleife nur die Originale. */
  const go = (i: number, animate = smooth) => {
    const list = looping() ? all : real;
    const at = looping() ? i : i - n;
    const el = list[Math.max(0, Math.min(list.length - 1, at))];
    if (el) to(el, animate ? 'smooth' : 'instant');
  };
  const buttons = real.map((_, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cdot';
    b.setAttribute('aria-label', `${dots?.dataset.label ?? 'Eintrag'} ${i + 1}`);
    b.addEventListener('click', () => go(n + i));
    dots?.append(b);
    return b;
  });
  let active = -1; // Platz in `all`
  const update = () => {
    const mid = track.scrollLeft + track.clientWidth / 2;
    let best = n;
    let dist = Infinity;
    (looping() ? all : real).forEach((el) => {
      const d = Math.abs(center(el) - mid);
      if (d < dist) { dist = d; best = all.indexOf(el); }
    });
    if (best === active) return;
    active = best;
    all.forEach((el, i) => el.classList.toggle('is-active', i === best));
    buttons.forEach((b, i) => b.setAttribute('aria-current', String(i === best % n)));
    root.dispatchEvent(new CustomEvent('carousel:change', { detail: best % n }));
  };
  /** In Ruhe auf einer Kopie: still auf das Original an derselben Stelle. */
  const settle = () => {
    if (!looping() || track.classList.contains('is-dragging')) return;
    update();
    if (active >= n && active < 2 * n) return;
    const twin = real[active % n];
    const shift = center(twin) - center(all[active]);
    track.scrollTo({ left: track.scrollLeft + shift, behavior: 'instant' });
    update();
  };
  let ticking = false;
  let rest = 0;
  track.addEventListener('scroll', () => {
    window.clearTimeout(rest);
    rest = window.setTimeout(settle, 140); // Rückfall, wo es kein `scrollend` gibt
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { ticking = false; update(); });
  }, { passive: true });
  track.addEventListener('scrollend', () => { window.clearTimeout(rest); settle(); });
  root.querySelector('[data-prev]')?.addEventListener('click', () => go(active - 1));
  drag(track, () => active, go);
  root.querySelector('[data-next]')?.addEventListener('click', () => go(active + 1));
  /** Schleife nur, wenn die Originale allein nicht hineinpassen; bleibt beim selben Eintrag. */
  const measure = () => {
    const keep = active < 0 ? Math.floor((n - 1) / 2) : active % n;
    root.classList.remove('is-loop');
    if (track.scrollWidth > track.clientWidth + 1) root.classList.add('is-loop');
    active = -1;
    to(real[keep], 'instant');
    update();
  };
  window.addEventListener('resize', measure);
  // Regel der Website: jedes Karussell beginnt in der Mitte – links und rechts liegt je ein Nachbar.
  requestAnimationFrame(measure);
}

/** Ziehen mit der Maus: die Spur folgt dem Zeiger, danach rastet sie ein. */
function drag(track: HTMLElement, current: () => number, go: (i: number) => void): void {
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
    go(to);
  };
  track.addEventListener('pointerup', end);
  track.addEventListener('pointercancel', end);
  // Ein Zug ist kein Klick auf den Artikel darunter.
  track.addEventListener('click', (e) => {
    if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
  }, true);
}
