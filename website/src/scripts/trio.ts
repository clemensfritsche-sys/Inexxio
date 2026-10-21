/**
 * Kran-Szenen in den Bereichskarten der Startseite (components/home/AreaTrio.astro) – Port der
 * Szenen aus dem früheren Laufkran im Seitenkopf, je Karte eine eigene Bühne.
 * Breit: spielt, solange der Zeiger (oder der Fokus) auf der Karte ist. Schmal: spielt die
 * Karte in der Mitte des Karussells, solange es im Bild ist.
 * Leistung: nur transform/opacity/height; läuft nur, solange eine Karte «an» ist.
 * Bei reduzierter Bewegung: nichts – das Foto bleibt stehen.
 */
type Frame = { t: number; x: number; y: number; a?: number };
type Card = HTMLElement & { on?: boolean; running?: boolean };

/** Keyframes je Szene in Bühnen-Koordinaten (380 × 200, y = Spitze des Hakens). */
const SCENES: Record<string, { dur: number; fr: Frame[] }> = {
  krantechnik: { dur: 5200, fr: [
    { t: 0, x: 190, y: -30, a: 0 }, { t: 0.12, x: 76, y: -30, a: 0 }, { t: 0.27, x: 76, y: 140, a: 0 },
    { t: 0.33, x: 76, y: 140, a: -40 }, { t: 0.47, x: 76, y: -20, a: -40 }, { t: 0.66, x: 280, y: -20, a: -40 },
    { t: 0.8, x: 280, y: 104, a: -40 }, { t: 0.86, x: 280, y: 104, a: 0 }, { t: 0.93, x: 280, y: -30, a: 0 },
    { t: 1, x: 150, y: -30, a: 0 } ] },
  fahrzeugtechnik: { dur: 7600, fr: [
    { t: 0, x: 190, y: -40 }, { t: 0.08, x: 245, y: -40 }, { t: 0.16, x: 245, y: 45 }, { t: 0.2, x: 245, y: 45 },
    { t: 0.32, x: 245, y: -30 }, { t: 0.42, x: 245, y: -38 }, { t: 0.52, x: 245, y: -38 },
    { t: 0.62, x: 245, y: -30 }, { t: 0.78, x: 245, y: 45 }, { t: 0.84, x: 245, y: 45 },
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

/** Spielt die Szene einer Karte, solange `card.on` wahr ist; danach blendet die Bühne aus. */
function play(card: Card): void {
  if (card.running) return;
  const id = card.dataset.scene ?? '';
  const def = SCENES[id];
  const stage = card.querySelector<HTMLElement>('.stg');
  if (!def || !stage) return;
  const $ = (s: string) => stage.querySelector<HTMLElement>(s);
  const inner = $('.stg-in'), trol = $('.trol'), line = $('.cline');
  if (!inner || !trol || !line) return;
  card.running = true;
  const ring = $('[data-tool="ring"]'), claws = $('[data-tool="claws"]');
  const clawL = $('[data-claw="l"]'), clawR = $('[data-claw="r"]');
  const L = { bale: $('[data-obj="bale"]'), old: $('[data-obj="old"]'), nu: $('[data-obj="new"]'), jib: $('[data-obj="jib"]') };
  const pad = window.matchMedia('(max-width: 959px)').matches ? 150 : 128;
  const place = (el: HTMLElement | null, x: number, y: number, s: number, o: number) => {
    if (!el) return;
    el.style.opacity = o.toFixed(3);
    el.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px) scale(${s.toFixed(3)})`;
  };
  const fade = (el: Element | null, o: number) => { if (el instanceof HTMLElement || el instanceof SVGElement) el.style.opacity = o.toFixed(2); };
  const grab = id === 'krantechnik';
  if (ring) ring.style.display = grab ? 'none' : 'block';
  if (claws) claws.style.display = grab ? 'block' : 'none';
  let p = 0, v = 0, last = 0, hold = 0, gearA = 0;
  // Masse einmal messen und nur bei Grössenänderung neu – nicht in jedem Bild: das Lesen von
  // clientWidth während die Karte breiter wird, erzwang je Bild ein Layout (Ruckeln).
  let W = stage.clientWidth, H = stage.clientHeight;
  const ro = new ResizeObserver(() => { W = stage.clientWidth; H = stage.clientHeight; });
  ro.observe(stage);
  const step = (t: number) => {
    const dt = last ? Math.min(64, t - last) : 16;
    last = t;
    const s = Math.max(0.7, Math.min(1.3, (W - 24) / 380)), ox = (W - 380 * s) / 2, oy = H - pad - 200 * s;
    const X = (x: number) => ox + x * s, Y = (y: number) => oy + y * s;
    v = card.on ? Math.min(1, v + dt / 350) : Math.max(0, v - dt / 350);
    stage.style.opacity = v.toFixed(3);
    inner.style.transform = `translate(${ox.toFixed(1)}px,${oy.toFixed(1)}px) scale(${s.toFixed(3)})`;
    if (v > 0.6) {
      if (p < 1) p = Math.min(1, p + dt / def.dur);
      else { hold += dt; if (hold > 1400 && card.on) { p = 0; hold = 0; } }
    }
    // Der Haken hängt nie höher als knapp unter der Katze (Flasche + Schaft + Werkzeug).
    const f = keyframe(def.fr, p), tipX = X(f.x), tipY = Math.max(Y(f.y), 68 + 46 + 12);
    trol.style.transform = `translateX(${(tipX - 44).toFixed(1)}px)`;
    line.style.height = `${Math.max(0, tipY - 68 - 46).toFixed(1)}px`;
    const ca = grab ? f.a ?? 0 : 0;
    if (clawL) clawL.style.transform = `rotate(${ca.toFixed(1)}deg)`;
    if (clawR) clawR.style.transform = `rotate(${(-ca).toFixed(1)}deg)`;
    const live = p > 0 && p < 1;
    if (id === 'krantechnik') {
      if (live && p >= 0.33 && p < 0.86) place(L.bale, tipX, tipY + 2 * s, s, 1);
      else if (p < 0.33) place(L.bale, X(76), Y(148), s, 0);
      else place(L.bale, X(280), Y(112 + 26 * seg(p, 0.86, 0.93)), s, 1 - seg(p, 0.88, 0.95));
      $('[data-heap="l"]')?.setAttribute('transform', `translate(76 168) scale(1 ${(1 - 0.3 * seg(p, 0.33, 0.42)).toFixed(3)})`);
      $('[data-heap="r"]')?.setAttribute('transform', `translate(280 187) scale(1 ${(1 + 0.16 * seg(p, 0.88, 0.96)).toFixed(3)})`);
      fade($('[data-b]'), seg(p, 0.86, 0.95));
    } else if (id === 'fahrzeugtechnik') {
      const carried = live && p >= 0.2 && p < 0.84;
      const oOld = 1 - seg(p, 0.42, 0.48), oNew = p < 0.84 ? seg(p, 0.46, 0.52) : 1;
      if (carried && p < 0.48) place(L.old, tipX, tipY, s, oOld);
      else if (p < 0.2) place(L.old, X(245), Y(45), s, oOld);
      else place(L.old, tipX, tipY, s, 0);
      if (carried && p >= 0.46) place(L.nu, tipX, tipY, s, oNew);
      else if (p >= 0.84) place(L.nu, X(245), Y(45), s, oNew);
      else place(L.nu, tipX, tipY, s, 0);
      fade($('[data-b]'), seg(p, 0.94, 1));
    } else {
      if (live && p >= 0.26 && p < 0.76) place(L.jib, tipX, tipY, s, 1);
      else if (p < 0.26) place(L.jib, X(75), Y(140), s, 1);
      else place(L.jib, X(296), Y(67), s, 1);
      gearA = p >= 0.78 ? gearA + dt * 0.0022 : 0;
      L.jib?.querySelector('[data-swing]')?.setAttribute('transform', `rotate(${(-9 * (1 - Math.cos(gearA))).toFixed(2)})`);
      L.jib?.querySelector('[data-sling]')?.setAttribute('opacity', (1 - seg(p, 0.76, 0.82)).toFixed(2));
      fade(stage.querySelector('[data-outline]'), p < 0.7 ? seg(p, 0, 0.1) : 1 - seg(p, 0.7, 0.78));
      fade(stage.querySelector('[data-dims]'), seg(p, 0.04, 0.14) * (1 - seg(p, 0.56, 0.66)));
      fade($('[data-b]'), seg(p, 0.84, 0.92));
    }
    if (!card.on && v <= 0) {
      card.running = false;
      ro.disconnect();
      p = 0;
      return;
    }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function initTrio(): void {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const cards = Array.from(document.querySelectorAll<Card>('.sc[data-scene]'));
  if (!cards.length) return;
  const narrow = window.matchMedia('(max-width: 959px)');
  const set = (c: Card, on: boolean) => { c.on = on; if (on) play(c); };
  for (const c of cards) {
    const enter = () => { if (!narrow.matches) set(c, true); };
    const leave = () => { if (!narrow.matches) set(c, false); };
    c.addEventListener('mouseenter', enter);
    c.addEventListener('mouseleave', leave);
    c.addEventListener('focus', enter);
    c.addEventListener('blur', leave);
  }
  // Schmal: die Karte in der Mitte spielt, solange das Karussell im Bild ist.
  const root = cards[0].closest<HTMLElement>('[data-carousel]');
  if (!root) return;
  let visible = false;
  const sync = () => {
    if (!narrow.matches) return;
    for (const c of cards) set(c, visible && !!c.closest('.is-active'));
  };
  root.addEventListener('carousel:change', sync);
  new IntersectionObserver((entries) => {
    visible = entries.some((e) => e.isIntersecting);
    sync();
  }, { threshold: 0.5 }).observe(root);
  narrow.addEventListener('change', () => { for (const c of cards) set(c, false); sync(); });
}
