/**
 * Kopfzeile – Komfort auf einer ohne JS voll funktionsfähigen Navigation:
 *  - ab 8 px Scroll weisser Hintergrund mit Linie, beim Runterscrollen ausblenden
 *  - Dropdowns per Klick auf den Pfeil, Esc schliesst, Klick daneben schliesst
 *  - Mobil-Menü (<details>): Scroll-Sperre, Esc, schliesst bei Klick auf einen Link
 */
export function initHeader(): void {
  const header = document.querySelector<HTMLElement>('[data-header]');
  if (!header) return;
  const menu = header.querySelector<HTMLDetailsElement>('[data-mnav]');

  // ---------- Scrollen ----------
  let lastY = window.scrollY;
  let ticking = false;
  const onScroll = () => {
    const y = Math.max(0, window.scrollY);
    header.classList.toggle('is-scrolled', y > 8);
    const down = y > lastY + 2;
    const up = y < lastY - 2;
    const busy = Boolean(menu?.open) || header.contains(document.activeElement) && document.activeElement !== document.body;
    if (down && y > 160 && !busy) header.classList.add('is-hidden');
    else if (up || y <= 160 || busy) header.classList.remove('is-hidden');
    lastY = y;
    ticking = false;
  };
  window.addEventListener('scroll', () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(onScroll);
    }
  }, { passive: true });
  onScroll();

  // ---------- Dropdowns ----------
  const dropdowns = Array.from(header.querySelectorAll<HTMLElement>('[data-dd]'));
  const reset = (dd: HTMLElement) => {
    dd.classList.remove('is-open', 'is-closed');
    dd.querySelector('[data-dd-toggle]')?.setAttribute('aria-expanded', 'false');
  };
  const open = (dd: HTMLElement) => {
    dropdowns.filter((d) => d !== dd).forEach(reset);
    dd.classList.add('is-open');
    dd.classList.remove('is-closed');
    dd.querySelector('[data-dd-toggle]')?.setAttribute('aria-expanded', 'true');
  };
  const close = (dd: HTMLElement) => {
    dd.classList.remove('is-open');
    dd.classList.add('is-closed');
    dd.querySelector('[data-dd-toggle]')?.setAttribute('aria-expanded', 'false');
  };

  for (const dd of dropdowns) {
    const toggle = dd.querySelector<HTMLButtonElement>('[data-dd-toggle]');
    toggle?.addEventListener('click', () => {
      if (dd.classList.contains('is-open')) close(dd);
      else open(dd);
    });
    dd.addEventListener('mouseenter', () => {
      dd.classList.remove('is-closed');
      dd.querySelector('[data-dd-toggle]')?.setAttribute('aria-expanded', 'true');
    });
    dd.addEventListener('mouseleave', () => reset(dd));
    dd.addEventListener('focusout', (e) => {
      if (!dd.contains(e.relatedTarget as Node | null)) reset(dd);
    });
    dd.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        close(dd);
        toggle?.focus();
      }
    });
  }
  document.addEventListener('click', (e) => {
    for (const dd of dropdowns) if (!dd.contains(e.target as Node)) reset(dd);
  });

  // ---------- Mobil-Menü ----------
  if (menu) {
    const root = document.documentElement;
    const sync = () => {
      root.classList.toggle('menu-open', menu.open);
      if (menu.open) header.classList.remove('is-hidden');
    };
    menu.addEventListener('toggle', sync);
    menu.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && menu.open) {
        menu.open = false;
        menu.querySelector<HTMLElement>('summary')?.focus();
      }
    });
    menu.addEventListener('click', (e) => {
      const link = (e.target as Element).closest('a');
      if (link && !e.defaultPrevented) menu.open = false;
    });
    const wide = window.matchMedia('(min-width: 1200px)');
    wide.addEventListener('change', () => {
      if (wide.matches) menu.open = false;
    });
    sync();
  }
}
