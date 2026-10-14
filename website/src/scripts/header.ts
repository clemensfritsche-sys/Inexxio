/**
 * Kopfzeile – Komfort auf einer ohne JS voll funktionsfähigen Navigation:
 *  - ab 8 px Scroll eine Linie unten
 *  - Mega-Dropdowns und Profilmenü: öffnen per Klick (Dropdowns auch beim Zeigen), Esc
 *    schliesst und gibt den Fokus zurück, Klick daneben schliesst
 *  - Mobil-Menü (<details>): Scroll-Sperre, Esc, schliesst bei Klick auf einen Link
 */
type Disclosure = { root: HTMLElement; toggle: HTMLButtonElement | null; hover: boolean };

export function initHeader(): void {
  const header = document.querySelector<HTMLElement>('[data-header]');
  // Einmal je Kopf: im Konto/ERP kann ihn React nach einem Seitenwechsel neu einsetzen –
  // dann ist es ein neues Element ohne `data-ready`, und es wird erneut verdrahtet.
  if (!header || header.dataset.ready) return;
  header.dataset.ready = '1';
  const menu = header.querySelector<HTMLDetailsElement>('[data-mnav]');

  // ---------- Aufklappbares (Dropdowns + Profilmenü) ----------
  const items: Disclosure[] = [
    ...Array.from(header.querySelectorAll<HTMLElement>('[data-dd]')).map((root) => ({
      root, toggle: root.querySelector<HTMLButtonElement>('[data-dd-toggle]'), hover: true,
    })),
    ...Array.from(header.querySelectorAll<HTMLElement>('[data-pm]')).map((root) => ({
      root, toggle: root.querySelector<HTMLButtonElement>('[data-pm-toggle]'), hover: false,
    })),
  ];
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
    if (d.hover) {
      d.root.addEventListener('mouseenter', () => {
        closeAll(d);
        d.root.classList.remove('is-closed');
        d.toggle?.setAttribute('aria-expanded', 'true');
      });
      d.root.addEventListener('mouseleave', () => setOpen(d, false));
    }
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

  // ---------- Scrollen ----------
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

  // ---------- Mobil-Menü ----------
  if (menu) {
    const root = document.documentElement;
    const sync = () => root.classList.toggle('menu-open', menu.open);
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
