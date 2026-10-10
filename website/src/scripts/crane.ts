/**
 * Laufkran im Seitenkopf der Startseite (HomeHero.astro).
 *
 * Zeiger: die Katze folgt ihm. Über einem Knopf ([data-tile="btn"]) senkt sich der Haken
 * und hängt ihn an (data-hooked). Über einem Bereich ([data-tile="0|1|2"]) fährt der Kran
 * an den Startpunkt der Szene und spielt sie im Bildfeld der Karte ab – Heu einlagern
 * (Greifer) · Mischtrommel tauschen · Ausleger montieren. Eine laufende Szene wird zu Ende
 * gespielt, ausser der Zeiger wählt einen anderen Bereich.
 * Ohne Zeiger (oder 4 s ohne Bewegung): stehen die Bereiche nebeneinander, fährt der Kran
 * sie nacheinander ab. Stehen sie untereinander (Handy), spielt er die Szene des Bereichs,
 * der beim Scrollen in den Blick kommt – einmal, und erneut, wenn man wiederkommt.
 *
 * Leistung: nur transform/opacity/height; die Lage der Karten wird höchstens alle 500 ms
 * gemessen; Elemente einmal gesucht; läuft nur, solange der Kopf im Bild ist.
 * Bei reduzierter Bewegung steht der Kran still (die Karten reagieren per CSS).
 */
type Frame = { t: number; x: number; y: number; a?: number };
type Tile = { el: HTMLElement; x: number; y: number; w: number; k: number };
type Scene = { p: number; v: number; run: boolean };

/** Keyframes je Szene in Bühnen-Koordinaten (380 × 200, y = Spitze des Hakens). */
const SCENES: Record<string, { dur: number; fr: Frame[] }> = {
  krantechnik: { dur: 5200, fr: [
    { t: 0, x: 190, y: -30, a: 0 }, { t: 0.12, x: 76, y: -30, a: 0 }, { t: 0.27, x: 76, y: 140, a: 0 },
    { t: 0.33, x: 76, y: 140, a: -40 }, { t: 0.47, x: 76, y: -20, a: -40 }, { t: 0.66, x: 280, y: -20, a: -40 },
    { t: 0.8, x: 280, y: 104, a: -40 }, { t: 0.86, x: 280, y: 104, a: 0 }, { t: 0.93, x: 280, y: -30, a: 0 },
    { t: 1, x: 150, y: -30, a: 0 } ] },
  fahrzeugtechnik: { dur: 7600, fr: [
    { t: 0, x: 190, y: -40 }, { t: 0.08, x: 245, y: -40 }, { t: 0.16, x: 245, y: 45 }, { t: 0.2, x: 245, y: 45 },
    { t: 0.32, x: 245, y: -115 }, { t: 0.42, x: 245, y: -125 }, { t: 0.52, x: 245, y: -125 },
    { t: 0.62, x: 245, y: -115 }, { t: 0.78, x: 245, y: 45 }, { t: 0.84, x: 245, y: 45 },
    { t: 0.94, x: 245, y: -40 }, { t: 1, x: 245, y: -40 } ] },
  spezialloesungen: { dur: 6400, fr: [
    { t: 0, x: 190, y: -40 }, { t: 0.1, x: 75, y: -40 }, { t: 0.22, x: 75, y: 140 }, { t: 0.26, x: 75, y: 140 },
    { t: 0.38, x: 75, y: -30 }, { t: 0.56, x: 296, y: -30 }, { t: 0.7, x: 296, y: 67 }, { t: 0.76, x: 296, y: 67 },
    { t: 0.88, x: 296, y: -40 }, { t: 1, x: 296, y: -40 } ] },
};

const sm = (u: number) => (u <= 0 ? 0 : u >= 1 ? 1 : u * u * (3 - 2 * u));
const seg = (p: number, a: number, b: number) => sm((p - a) / (b - a));

function keyframe(fr: Frame[], p: number): Frame {
  for (let i = 0; i < fr.length - 1; i++) {
    const a = fr[i], b = fr[i + 1];
    if (p <= b.t) {
      const e = sm((p - a.t) / (b.t - a.t || 1));
      return { t: p, x: a.x + (b.x - a.x) * e, y: a.y + (b.y - a.y) * e, a: (a.a ?? 0) + ((b.a ?? 0) - (a.a ?? 0)) * e };
    }
  }
  return fr[fr.length - 1];
}

/** Bühne → Kran-Rahmen: die Zeichnung ist 380 breit, unten bündig, skaliert 0.7–1.2. */
function geo(tl: Tile) {
  const s = Math.max(0.7, Math.min(1.2, tl.w / 380));
  const ox = (tl.w - 380 * s) / 2;
  return { s, ox, X: (x: number) => tl.x + ox + x * s, Y: (y: number) => tl.y + 200 - (200 - y) * s };
}

export function initCrane(): void {
  const hero = document.querySelector<HTMLElement>('[data-crane]');
  if (!hero) return;
  const $ = (sel: string, root: ParentNode = hero) => root.querySelector<HTMLElement>(sel);
  const trolley = $('[data-crane-trolley]');
  const rope = $('[data-crane-rope]');
  const line = $('[data-crane-line]');
  if (!trolley || !rope || !line) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  hero.classList.add('is-live');

  const HALF = trolley.offsetWidth / 2; // Seil hängt mittig unter der Katze
  const BASE_L = 60; // Seillänge in Ruhe
  const TOOL = 46; // Flasche + Schaft + Öse/Greifer bis zur Spitze
  const STEP = 1000 / 60; // Physik in festen 60-Hz-Schritten – gleich schnell auf jedem Bildschirm
  const IDLE_MS = 4000;
  const HOLD_MS = 1600; // nach einer Szene so lange stehen bleiben

  const ring = $('[data-tool="ring"]');
  const claws = $('[data-tool="claws"]');
  const clawL = $('[data-claw="l"]');
  const clawR = $('[data-claw="r"]');
  const obj = (n: string) => $(`[data-obj="${n}"]`);
  const loads = { bale: obj('bale'), old: obj('old'), new: obj('new'), jib: obj('jib') };

  const sim = { x: 160, vx: 0, L: BASE_L, ang: 0 };
  const anim: Scene[] = [];
  let mouse: { x: number; y: number } | null = null;
  let lastMove = 0;
  let wasMouse = false;
  let lock: number | null = null;
  let autoIdx = 0;
  let autoHold = 0;
  let gearA = 0;
  let hooked: HTMLElement | null = null;
  let raf = 0;
  let last = 0;
  let acc = 0;
  let tiles: Tile[] = [];
  let tilesT = -1e9;
  let originY = 0;

  const onPointer = (e: PointerEvent) => {
    // Touch steuert nicht: ein Tippen öffnet die Karte, und beim Scrollen gilt der Blick.
    if (e.pointerType === 'touch') return;
    const r = hero.getBoundingClientRect();
    mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
    lastMove = performance.now();
  };
  hero.addEventListener('pointermove', onPointer, { passive: true });
  hero.addEventListener('pointerdown', onPointer, { passive: true });
  hero.addEventListener('pointerleave', () => { mouse = null; });
  window.addEventListener('resize', () => { tilesT = -1e9; }, { passive: true });

  // Welcher Bereich ist im Blick? Sichtbarer Anteil je Karte – für die gestapelte Ansicht.
  const seen = new Map<Element, number>();
  const watch = new IntersectionObserver(
    (entries) => { for (const e of entries) seen.set(e.target, e.isIntersecting ? e.intersectionRatio : 0); },
    { threshold: [0, 0.25, 0.5, 0.6, 0.75, 1] },
  );
  hero.querySelectorAll('[data-tile]').forEach((el) => { if (/^\d+$/.test((el as HTMLElement).dataset.tile ?? '')) watch.observe(el); });
  const inFocus = (areas: Tile[]) => {
    let best: Tile | null = null;
    let ratio = 0.5; // mindestens die Hälfte der Karte im Bild
    for (const tl of areas) {
      const r = seen.get(tl.el) ?? 0;
      if (r > ratio) { ratio = r; best = tl; }
    }
    return best;
  };

  const measure = (t: number) => {
    if (t - tilesT < 500) return;
    tilesT = t;
    const hr = hero.getBoundingClientRect();
    tiles = Array.from(hero.querySelectorAll<HTMLElement>('[data-tile]')).map((el) => {
      const r = el.getBoundingClientRect();
      const id = el.dataset.tile ?? '';
      return { el, x: r.left - hr.left, y: r.top - hr.top, w: r.width, k: /^\d+$/.test(id) ? Number(id) : -1 };
    });
    originY = trolley.offsetTop + rope.offsetTop;
  };

  const setHooked = (el: HTMLElement | null) => {
    if (el === hooked) return;
    hooked?.removeAttribute('data-hooked');
    el?.setAttribute('data-hooked', '');
    hooked = el;
  };

  const place = (el: HTMLElement | null, x: number, y: number, rot: number, s: number, o: number) => {
    if (!el) return;
    el.style.opacity = o.toFixed(3);
    el.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px) rotate(${rot.toFixed(2)}deg) scale(${s.toFixed(3)})`;
  };
  const fade = (el: Element | null, o: number) => { if (el) (el as HTMLElement).style.opacity = o.toFixed(2); };

  /** Eine Szene zeichnen: Bühne einblenden, Lasten setzen, Zustände der Zeichnung. */
  const draw = (tl: Tile, sc: Scene, live: boolean, tipX: number, tipY: number, dt: number) => {
    const id = tl.el.dataset.sceneId;
    if (!id) return;
    const { p, v } = sc;
    const g = geo(tl);
    const stage = $('[data-scene]', tl.el);
    if (!stage) return;
    stage.style.opacity = v.toFixed(3);
    const inner = $('[data-stagein]', stage);
    if (inner) inner.style.transform = `translate(${g.ox.toFixed(1)}px,${(200 - 200 * g.s).toFixed(1)}px) scale(${g.s.toFixed(3)})`;
    const q = (sel: string) => $(sel, stage);
    if (id === 'krantechnik') {
      if (live && p >= 0.33 && p < 0.86) place(loads.bale, tipX, tipY + 2 * g.s, sim.ang, g.s, v);
      else if (p < 0.33) place(loads.bale, g.X(76), g.Y(148), 0, g.s, 0);
      else place(loads.bale, g.X(280), g.Y(112 + 26 * seg(p, 0.86, 0.93)), 0, g.s, v * (1 - seg(p, 0.88, 0.95)));
      q('[data-heap="l"]')?.setAttribute('transform', `translate(76 168) scale(1 ${(1 - 0.3 * seg(p, 0.33, 0.42)).toFixed(3)})`);
      q('[data-heap="r"]')?.setAttribute('transform', `translate(280 187) scale(1 ${(1 + 0.16 * seg(p, 0.88, 0.96)).toFixed(3)})`);
      fade(q('[data-b]'), seg(p, 0.86, 0.95));
    } else if (id === 'fahrzeugtechnik') {
      const carried = live && p >= 0.2 && p < 0.84;
      const oOld = v * (1 - seg(p, 0.42, 0.48));
      const oNew = v * (p < 0.84 ? seg(p, 0.46, 0.52) : 1);
      if (carried && p < 0.48) place(loads.old, tipX, tipY, sim.ang, g.s, oOld);
      else if (p < 0.2) place(loads.old, g.X(245), g.Y(45), 0, g.s, oOld);
      else place(loads.old, tipX, tipY, sim.ang, g.s, 0);
      if (carried && p >= 0.46) place(loads.new, tipX, tipY, sim.ang, g.s, oNew);
      else if (p >= 0.84) place(loads.new, g.X(245), g.Y(45), 0, g.s, oNew);
      else place(loads.new, tipX, tipY, sim.ang, g.s, 0);
      fade(q('[data-b]'), seg(p, 0.94, 1));
    } else if (id === 'spezialloesungen') {
      if (live && p >= 0.26 && p < 0.76) place(loads.jib, tipX, tipY, sim.ang, g.s, v);
      else if (p < 0.26) place(loads.jib, g.X(75), g.Y(140), 0, g.s, v);
      else place(loads.jib, g.X(296), g.Y(67), 0, g.s, v);
      gearA = p >= 0.78 ? gearA + dt * 0.0022 : 0;
      loads.jib?.querySelector('[data-swing]')?.setAttribute('transform', `rotate(${(-9 * (1 - Math.cos(gearA))).toFixed(2)})`);
      loads.jib?.querySelector('[data-sling]')?.setAttribute('opacity', (1 - seg(p, 0.76, 0.82)).toFixed(2));
      fade(q('[data-outline]'), p < 0.7 ? seg(p, 0, 0.1) : 1 - seg(p, 0.7, 0.78));
      fade(q('[data-dims]'), seg(p, 0.04, 0.14) * (1 - seg(p, 0.56, 0.66)));
      fade(q('[data-b]'), seg(p, 0.84, 0.92));
    }
  };

  const tick = (t: number) => {
    raf = requestAnimationFrame(tick);
    const dt = last ? Math.min(64, t - last) : STEP;
    measure(t);
    const areas = tiles.filter((tl) => tl.k >= 0);
    const minY = Math.min(...areas.map((a) => a.y));
    // Gestapelt (Handy): die Szene greift nie über die Oberkante ihrer Karte hinaus – sonst
    // schwebt die Last über der Überschrift bzw. der Karte darüber.
    const stacked = areas.some((a) => a.y > minY + 10);
    const yC = (_tl: Tile, y: number) => (stacked ? Math.max(y, 8) : y);
    const sceneOf = (tl: Tile) => SCENES[tl.el.dataset.sceneId ?? ''];

    const mouseOn = !!mouse && t - lastMove < IDLE_MS;
    let target: Tile | null = null;
    if (mouse && mouseOn) {
      // Spätere Treffer gewinnen: die Bereiche stehen unter den Knöpfen.
      for (const tl of tiles) if (mouse.x >= tl.x && mouse.x <= tl.x + tl.w && mouse.y > tl.y - 140) target = tl;
    }
    const lockSc = lock != null ? anim[lock] : null;
    const lockBusy = !!lockSc && lockSc.run && lockSc.p < 1;
    if (!mouseOn && areas.length && stacked) {
      // Gestapelt: die Karte im Blick – sie gewinnt auch gegen eine laufende Szene, denn
      // wer weiterscrollt, will die nächste sehen. Ist keine im Blick, wartet der Kran.
      target = inFocus(areas);
    } else if (lockBusy && !(target && target.k !== lock)) {
      target = areas.find((tl) => tl.k === lock) ?? target;
    } else if (!mouseOn && areas.length) {
      if (wasMouse && lock != null) {
        const li = areas.findIndex((tl) => tl.k === lock);
        if (li >= 0) autoIdx = li;
        autoHold = 0;
      }
      target = areas[autoIdx % areas.length];
      const sc0 = anim[target.k];
      if (!sceneOf(target) || (sc0 && sc0.p >= 1)) {
        autoHold += dt;
        if (autoHold > HOLD_MS) { autoHold = 0; autoIdx++; }
      }
    }
    wasMouse = mouseOn;

    let tx = mouse && mouseOn ? mouse.x - HALF : sim.x;
    let tL = BASE_L;
    let scene = false;
    let attached: HTMLElement | null = null;
    let f: Frame | null = null;
    let k = -1;
    const def = target ? sceneOf(target) : undefined;
    if (target && target.k >= 0 && def) {
      k = target.k;
      const sc = (anim[k] ??= { p: 0, v: 0, run: false });
      const g = geo(target);
      if (!sc.run) {
        const f0 = def.fr[0];
        tx = g.X(f0.x) - HALF;
        tL = g.Y(yC(target, f0.y)) - originY - TOOL;
        if (Math.abs(sim.x - tx) < 10 && Math.abs(sim.L - tL) < 10) sc.run = true;
      }
      if (sc.run) {
        lock = k;
        sc.p = Math.min(1, sc.p + dt / def.dur);
        f = keyframe(def.fr, sc.p);
        tx = g.X(f.x) - HALF;
        tL = g.Y(yC(target, f.y)) - originY - TOOL;
        scene = true;
        attached = target.el;
      }
    } else if (target) {
      if (!mouseOn) tx = target.x + target.w / 2 - HALF;
      tL = Math.max(BASE_L, target.y - originY - TOOL + 8);
    }

    acc = Math.min(acc + dt, STEP * 5);
    last = t;
    for (; acc >= STEP; acc -= STEP) {
      if (scene) {
        const nx = sim.x + (tx - sim.x) * 0.3;
        sim.vx = sim.vx * 0.6 + (nx - sim.x) * 0.4;
        sim.x = nx;
      } else {
        sim.vx = (sim.vx + (tx - sim.x) * 0.01) * 0.88;
        sim.x += sim.vx;
      }
      sim.L += (tL - sim.L) * (scene ? 0.3 : 0.07);
      sim.ang += (Math.max(-20, Math.min(20, -sim.vx * (scene ? 0.9 : 1.4))) - sim.ang) * 0.12;
    }
    if (target && !scene && Math.abs(sim.L - tL) < 14 && (target.k < 0 || !def)) attached = target.el;

    trolley.style.transform = `translateX(${sim.x.toFixed(1)}px)`;
    rope.style.transform = `rotate(${sim.ang.toFixed(2)}deg)`;
    line.style.height = `${Math.max(0, sim.L).toFixed(1)}px`;

    const d = sim.L + TOOL;
    const th = (sim.ang * Math.PI) / 180;
    const tipX = sim.x + HALF - Math.sin(th) * d;
    const tipY = originY + Math.cos(th) * d;
    const grab = target?.el.dataset.sceneId === 'krantechnik' && k >= 0;
    if (ring) ring.style.display = grab ? 'none' : 'block';
    if (claws) claws.style.display = grab ? 'block' : 'none';
    const ca = grab && f ? f.a ?? 0 : 0;
    if (clawL) clawL.style.transform = `rotate(${ca.toFixed(1)}deg)`;
    if (clawR) clawR.style.transform = `rotate(${(-ca).toFixed(1)}deg)`;

    for (const tl of areas) {
      const sc = (anim[tl.k] ??= { p: 0, v: 0, run: false });
      const isT = tl.k === k;
      if (!isT) sc.run = false;
      sc.v += ((isT && sc.run ? 1 : 0) - sc.v) * 0.12;
      if (!isT && sc.v < 0.03) sc.p = 0;
      draw(tl, sc, isT && sc.run, tipX, tipY, dt);
    }
    setHooked(attached);
  };

  const start = () => { if (!raf) { last = 0; raf = requestAnimationFrame(tick); } };
  const stop = () => { cancelAnimationFrame(raf); raf = 0; };
  new IntersectionObserver(([entry]) => (entry.isIntersecting ? start() : stop())).observe(hero);
}
