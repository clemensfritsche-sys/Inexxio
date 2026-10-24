/**
 * Kopfzeile – Komfort auf einer ohne JS voll funktionsfähigen Navigation:
 *  - ab 8 px Scroll `is-scrolled` (über der Bühne wird der Kopf dann zu Glas)
 *  - Kachelreihen (Hauptpunkte, Sprache, Konto): öffnen beim Zeigen und per Klick auf den
 *    Pfeil, schliessen erst beim Verlassen der Karte; Esc schliesst und gibt den Fokus zurück
 *  - Mobil-Menü (<details>): Scroll-Sperre, Esc, je Punkt eine aufklappende Reihe Karten
 *    (höchstens eine offen), schliesst bei Klick auf einen Link
 */
type Disclosure = { root: HTMLElement; toggle: HTMLButtonElement | null };

function initDisclosures(header: HTMLElement): void {
  const card = header.querySelector<HTMLElement>('[data-hd]') ?? header;
  const items: Disclosure[] = Array.from(header.querySelectorAll<HTMLElement>('[data-dd]')).map((root) => ({
    root, toggle: root.querySelector<HTMLButtonElement>('[data-dd-toggle]'),
  }));
  // EIN Zustand (.is-open). Geöffnet wird beim Zeigen auf einen Punkt, geschlossen erst, wenn
  // der Zeiger die ganze Karte verlässt (kurz verzögert) – nicht schon im Spalt zwischen dem
  // Punkt und seinem Panel. Darum geht unterwegs nichts verloren.
  const setOpen = (d: Disclosure, open: boolean) => {
    d.root.classList.toggle('is-open', open);
    d.toggle?.setAttribute('aria-expanded', String(open));
  };
  const closeAll = (except?: Disclosure) => items.filter((d) => d !== except).forEach((d) => setOpen(d, false));
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  let timer = 0;
  const cancel = () => window.clearTimeout(timer);

  for (const d of items) {
    d.toggle?.addEventListener('click', () => {
      const open = !d.root.classList.contains('is-open');
      closeAll(d);
      setOpen(d, open);
    });
    d.root.addEventListener('mouseenter', () => {
      if (!fine.matches) return;
      cancel();
      closeAll(d);
      setOpen(d, true);
    });
    d.root.addEventListener('focusout', (e) => {
      if (!d.root.contains(e.relatedTarget as Node | null)) setOpen(d, false);
    });
    d.root.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && d.root.classList.contains('is-open')) {
        setOpen(d, false);
        d.toggle?.focus();
      }
    });
  }
  // Zeigt man auf einen Punkt ohne Panel (ERP), schliesst das offene.
  header.querySelectorAll<HTMLElement>('.nav__item:not([data-dd])').forEach((el) => el.addEventListener('mouseenter', () => closeAll()));
  card.addEventListener('mouseenter', cancel);
  card.addEventListener('mouseleave', () => {
    cancel();
    timer = window.setTimeout(() => closeAll(), 150);
  });
  document.addEventListener('click', (e) => {
    for (const d of items) if (!d.root.contains(e.target as Node)) setOpen(d, false);
  });
}

function initMobile(header: HTMLElement, menu: HTMLDetailsElement): void {
  const root = document.documentElement;
  const groups = Array.from(menu.querySelectorAll<HTMLElement>('[data-mg]'));
  // Höchstens EIN Punkt offen; beim Öffnen des Menüs sind alle zu.
  const show = (id: string) => {
    for (const g of groups) {
      const open = g.dataset.mg === id;
      g.classList.toggle('is-open', open);
      g.querySelector('[data-mg-toggle]')?.setAttribute('aria-expanded', String(open));
    }
  };
  const sync = () => {
    root.classList.toggle('menu-open', menu.open);
    if (!menu.open) show('');
  };
  menu.addEventListener('toggle', sync);
  // Ein Punkt klappt seine Karten auf, statt die Seite zu öffnen (ohne JS bleibt es ein Link).
  menu.addEventListener('click', (e) => {
    const target = e.target as Element;
    const toggle = target.closest<HTMLElement>('[data-mg-toggle]');
    const group = toggle?.closest<HTMLElement>('[data-mg]');
    if (toggle && group) {
      e.preventDefault();
      show(group.classList.contains('is-open') ? '' : group.dataset.mg ?? '');
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
  // Das Konto-Symbol im schmalen Kopf öffnet das Menü mit aufgeklapptem Konto.
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
