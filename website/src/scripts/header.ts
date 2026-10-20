/**
 * Kopfzeile – Komfort auf einer ohne JS voll funktionsfähigen Navigation:
 *  - ab 8 px Scroll `is-scrolled` (über der Bühne wird der Kopf dann zu Glas)
 *  - Kachelreihen (Hauptpunkte, Sprache, Konto): öffnen beim Zeigen und per Klick auf den
 *    Pfeil, Esc schliesst und gibt den Fokus zurück, Klick daneben schliesst
 *  - Mobil-Menü (<details>): Scroll-Sperre, Esc, zweite Ebene je Punkt, schliesst bei Klick
 *    auf einen Link
 */
type Disclosure = { root: HTMLElement; toggle: HTMLButtonElement | null };

function initDisclosures(header: HTMLElement): void {
  const items: Disclosure[] = Array.from(header.querySelectorAll<HTMLElement>('[data-dd]')).map((root) => ({
    root, toggle: root.querySelector<HTMLButtonElement>('[data-dd-toggle]'),
  }));
  const setOpen = (d: Disclosure, open: boolean, closedByUser = false) => {
    d.root.classList.toggle('is-open', open);
    // Wer per Klick schliesst, während der Zeiger noch darauf steht, will es zu haben.
    d.root.classList.toggle('is-closed', !open && closedByUser);
    d.toggle?.setAttribute('aria-expanded', String(open));
  };
  const closeAll = (except?: Disclosure) => items.filter((d) => d !== except).forEach((d) => setOpen(d, false));

  for (const d of items) {
    d.toggle?.addEventListener('click', () => {
      const open = !d.root.classList.contains('is-open');
      closeAll(d);
      setOpen(d, open, !open);
    });
    d.root.addEventListener('mouseenter', () => {
      closeAll(d);
      d.root.classList.remove('is-closed');
      d.toggle?.setAttribute('aria-expanded', 'true');
    });
    d.root.addEventListener('mouseleave', () => setOpen(d, false));
    d.root.addEventListener('focusout', (e) => {
      if (!d.root.contains(e.relatedTarget as Node | null)) setOpen(d, false);
    });
    d.root.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && d.toggle?.getAttribute('aria-expanded') === 'true') {
        setOpen(d, false, true);
        d.toggle.focus();
      }
    });
  }
  document.addEventListener('click', (e) => {
    for (const d of items) if (!d.root.contains(e.target as Node)) setOpen(d, false);
  });
}

function initMobile(header: HTMLElement, menu: HTMLDetailsElement): void {
  const root = document.documentElement;
  const levels = menu.querySelector<HTMLElement>('[data-mnav-levels]');
  const panels = Array.from(menu.querySelectorAll<HTMLElement>('[data-mnav-panel]'));
  const show = (id: string) => {
    if (levels) levels.dataset.level = id;
    for (const p of panels) p.hidden = p.dataset.mnavPanel !== id;
    panels.find((p) => !p.hidden)?.querySelector<HTMLElement>('[data-mnav-back]')?.focus({ preventScroll: true });
  };
  const sync = () => {
    root.classList.toggle('menu-open', menu.open);
    if (!menu.open) show('');
  };
  menu.addEventListener('toggle', sync);
  // Zuerst: ein Punkt mit zweiter Ebene öffnet sie, statt der Seite (ohne JS bleibt es ein Link).
  menu.addEventListener('click', (e) => {
    const target = e.target as Element;
    const sub = target.closest<HTMLElement>('[data-mnav-sub]');
    if (sub && panels.some((p) => p.dataset.mnavPanel === sub.dataset.mnavSub)) {
      e.preventDefault();
      show(sub.dataset.mnavSub ?? '');
      return;
    }
    if (target.closest('[data-mnav-back]')) {
      show('');
      return;
    }
    if (target.closest('a') && !e.defaultPrevented) menu.open = false;
  });
  menu.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && menu.open) {
      menu.open = false;
      menu.querySelector<HTMLElement>('summary')?.focus();
    }
  });
  // Das Konto-Symbol im schmalen Kopf öffnet das Menü auf der Konto-Ebene.
  header.querySelectorAll<HTMLAnchorElement>('[data-mnav-open]').forEach((a) => {
    a.addEventListener('click', (e) => {
      if (window.matchMedia('(min-width: 1200px)').matches) return;
      e.preventDefault();
      menu.open = true;
      show(a.dataset.mnavOpen ?? '');
    });
  });
  const wide = window.matchMedia('(min-width: 1200px)');
  wide.addEventListener('change', () => {
    if (wide.matches) menu.open = false;
  });
  sync();
}

export function initHeader(): void {
  const header = document.querySelector<HTMLElement>('[data-header]');
  // Einmal je Kopf: im Konto/ERP kann ihn React nach einem Seitenwechsel neu einsetzen –
  // dann ist es ein neues Element ohne `data-ready`, und es wird erneut verdrahtet.
  if (!header || header.dataset.ready) return;
  header.dataset.ready = '1';

  initDisclosures(header);

  let ticking = false;
  const onScroll = () => {
    header.classList.toggle('is-scrolled', window.scrollY > 8);
    ticking = false;
  };
  window.addEventListener('scroll', () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(onScroll);
    }
  }, { passive: true });
  onScroll();

  const menu = header.querySelector<HTMLDetailsElement>('[data-mnav]');
  if (menu) initMobile(header, menu);
}
