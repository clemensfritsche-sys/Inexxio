/**
 * Laufkran im Seitenkopf der Startseite (HomeHero.astro).
 *
 * Mit Maus: die Katze folgt dem Zeiger; steht sie über einem [data-tile] (Bereich oder
 * Knopf), senkt sich der Haken bis auf dessen Oberkante, und das Element bekommt
 * data-hooked. Ohne Bewegung (4 s) oder ohne Maus fährt der Kran die Bereiche
 * ([data-tile="area"]) der ersten Reihe nacheinander an, dazwischen eine Parkposition;
 * stehen die Bereiche untereinander (Handy), bleibt er in der Parkposition.
 *
 * Nur transform/height, läuft nur, solange der Kopf im Bild ist. Bei reduzierter Bewegung
 * bleibt der Kran stehen (die Karten reagieren dann per CSS auf das Zeigen).
 */
export function initCrane(): void {
  const hero = document.querySelector<HTMLElement>('[data-crane]');
  if (!hero) return;
  const trolley = hero.querySelector<HTMLElement>('[data-crane-trolley]');
  const rope = hero.querySelector<HTMLElement>('[data-crane-rope]');
  const line = hero.querySelector<HTMLElement>('[data-crane-line]');
  if (!trolley || !rope || !line) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  hero.classList.add('is-live');

  const HALF = trolley.offsetWidth / 2; // Seil hängt mittig unter der Katze
  const BASE_L = 60; // Seillänge in Ruhe
  const HOOK_H = 40; // Flasche + Schaft + Öse, der Rest greift in die Öse der Last
  const STEP = 1000 / 60; // Physik in festen 60-Hz-Schritten – gleich schnell auf jedem Bildschirm
  const PATROL_MS = 2800;
  const IDLE_MS = 4000;

  const sim = { x: 160, vx: 0, L: BASE_L, ang: 0 };
  let mouse: { x: number; y: number } | null = null;
  let lastMove = 0;
  let patrolIdx = 0;
  let patrolT = 0;
  let hooked: HTMLElement | null = null;
  let raf = 0;
  let last = 0;
  let acc = 0;

  hero.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse') return;
    const r = hero.getBoundingClientRect();
    mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
    lastMove = performance.now();
  });
  hero.addEventListener('pointerleave', () => { mouse = null; });

  const setHooked = (el: HTMLElement | null) => {
    if (el === hooked) return;
    hooked?.removeAttribute('data-hooked');
    el?.setAttribute('data-hooked', '');
    hooked = el;
  };

  const tick = (t: number) => {
    raf = requestAnimationFrame(tick);
    const hr = hero.getBoundingClientRect();
    const tiles = Array.from(hero.querySelectorAll<HTMLElement>('[data-tile]')).map((el) => {
      const r = el.getBoundingClientRect();
      return { el, x: r.left - hr.left, y: r.top - hr.top, w: r.width, area: el.dataset.tile === 'area' };
    });
    const originY = trolley.offsetTop + rope.offsetTop;

    let tx = sim.x;
    let target: (typeof tiles)[number] | null = null;
    if (mouse && t - lastMove < IDLE_MS) {
      const m = mouse;
      tx = m.x - HALF;
      // Spätere Treffer gewinnen: die Bereiche stehen unter den Knöpfen.
      for (const tl of tiles) if (m.x >= tl.x && m.x <= tl.x + tl.w && m.y > tl.y - 140) target = tl;
    } else {
      const areas = tiles.filter((tl) => tl.area);
      // Nur die erste Reihe, und nur wenn sie nebeneinander steht – gestapelt (Handy) läge
      // die Last weit unter dem Bild, das Seil liefe quer durch den ganzen Text.
      let row = areas.filter((tl) => Math.abs(tl.y - areas[0].y) < 10);
      if (row.length < 2) row = [];
      if (t - patrolT > PATROL_MS) { patrolT = t; patrolIdx = (patrolIdx + 1) % (row.length + 1); }
      const tl = row[patrolIdx];
      if (tl) {
        tx = tl.x + tl.w / 2 - HALF;
        if (Math.abs(sim.x - tx) < 12) target = tl;
      } else tx = hr.width / 2 - HALF;
    }
    const tL = target ? Math.max(BASE_L, target.y - originY - HOOK_H + 2) : BASE_L;

    acc = Math.min(acc + (last ? t - last : STEP), STEP * 5);
    last = t;
    for (; acc >= STEP; acc -= STEP) {
      sim.vx = (sim.vx + (tx - sim.x) * 0.01) * 0.88;
      sim.x += sim.vx;
      sim.L += (tL - sim.L) * 0.07;
      sim.ang += (Math.max(-20, Math.min(20, -sim.vx * 1.4)) - sim.ang) * 0.12;
    }

    trolley.style.transform = `translateX(${sim.x.toFixed(1)}px)`;
    rope.style.transform = `rotate(${sim.ang.toFixed(2)}deg)`;
    line.style.height = `${sim.L.toFixed(1)}px`;
    setHooked(target && Math.abs(sim.L - tL) < 14 ? target.el : null);
  };

  const start = () => { if (!raf) { last = 0; raf = requestAnimationFrame(tick); } };
  const stop = () => { cancelAnimationFrame(raf); raf = 0; };
  new IntersectionObserver(([entry]) => (entry.isIntersecting ? start() : stop())).observe(hero);
}
