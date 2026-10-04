'use client';

import { useState, useEffect, useCallback, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ArrowRight, ChevronDown, CircleUser, LayoutDashboard, LogOut, Menu, Phone, Siren, User as UserIcon, X,
} from 'lucide-react';
import { isStaff } from '@/lib/record-status';
import { onAuthChange, logout } from '@/lib/firebase';
import { ROLE_KEY, NAME_KEY, rememberContact, clearAccountCache } from '@/lib/account-cache';
import { LoginDialog } from '@/components/auth/login-dialog';
import { api } from '@/lib/api';
import shell from '@/lib/site-shell.json';
import type { User } from 'firebase/auth';

/**
 * ►►► Der Kopf des Konto-/ERP-Bereichs – ein Spiegel der Website-Kopfzeile. ◄◄◄
 *
 * Dieselbe Struktur wie `website/src/components/Header.astro` (Auftrag Kap. 7.1/6.2):
 * dunkle **Servicezeile** (Ankündigung · Notfall · Telefon · Anmelden bzw. Profilmenü) und weisse **Hauptzeile** (Logo · drei Bereiche und Service als Dropdowns ·
 * Über uns · Kontakt · «Anfrage stellen»). Die Inhalte kommen aus `lib/site-shell.json`,
 * generiert aus `website/src/config/site.mjs` – hier steht kein eigenes Wort.
 *
 * **Geändert ist nur die Darstellung.** Anmeldung, Rolle und Abmelden laufen wie vorher:
 * dieselbe Anmeldeprüfung, derselbe `/auth/me`, derselbe Anmeldedialog. Neu ist eine
 * Zeile, die die Kontaktangaben für das Anfrage-Formular der Website merkt (S2), und dass
 * beim Abmelden der ganze Anzeige-Cache geräumt wird (S3).
 *
 * Seiten der Website sind schlichte `<a>` – der Router kennt sie nicht.
 *
 * Für Personal steht darüber die **Arbeitsleiste** (`WorkBar`) – dieselbe wie auf der
 * Website; einen ERP-Knopf in Servicezeile oder Profilmenü gibt es nicht mehr.
 */

type Group = (typeof shell.areas)[number];
const GROUPS: Group[] = [...shell.areas, shell.service];
const TEL = `tel:${shell.phone.e164}`;

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [compact, setCompact] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [loginOpen, setLoginOpen] = useState(false);
  const pathname = usePathname();
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  /** Öffnet `id` – oder schliesst es, aber nur, wenn gerade es offen ist. */
  const toggle = useCallback((id: string) => (o: boolean) =>
    setOpen((cur) => (o ? id : cur === id ? null : cur)), []);

  useScrollState(setScrolled, setCompact);

  useEffect(() => {
    setMobileOpen(false);
    setOpen(null);
  }, [pathname]);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (firebaseUser) => {
      setUser(firebaseUser);
      setAuthLoaded(true);
      if (firebaseUser) {
        const cachedRole = localStorage.getItem(ROLE_KEY);
        if (cachedRole) setUserRole(cachedRole);
        const cachedName = localStorage.getItem(NAME_KEY);
        if (cachedName) setProfileName(cachedName);
        try {
          const token = await firebaseUser.getIdToken();
          api.setToken(token);
          const profile = await api.getMe();
          setUserRole(profile.role);
          localStorage.setItem(ROLE_KEY, profile.role);
          rememberContact(profile);
          const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ');
          if (fullName) {
            localStorage.setItem(NAME_KEY, fullName);
            setProfileName(fullName);
          }
        } catch {
          // keep cached values
        }
      } else {
        setUserRole(null);
        setProfileName('');
        clearAccountCache();
      }
    });
    return unsubscribe;
  }, []);

  // Klick daneben schliesst Dropdown und Profilmenü.
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Element | null;
      if (!target?.closest('[data-disclosure]')) setOpen(null);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    function onNameUpdate(e: Event) {
      const name = (e as CustomEvent<string>).detail;
      setProfileName(name);
      localStorage.setItem(NAME_KEY, name);
    }
    window.addEventListener('inexxio:profile-name-updated', onNameUpdate);
    return () => window.removeEventListener('inexxio:profile-name-updated', onNameUpdate);
  }, []);

  async function handleLogout() {
    setOpen(null);
    setMobileOpen(false);
    await logout();
    // Hart: «/» ist die Website, keine Next-Seite (`lib/login-target`).
    window.location.assign('/');
  }

  /**
   * **Anmelden öffnet ein Pop-up, es navigiert nicht** (Notiz vom 28.8.): der Dialog legt
   * sich über die Seite, und nach der Anmeldung bleibt man, wo man war (`fallback`).
   */
  const openLogin = () => setLoginOpen(true);

  const nameForDisplay = profileName || user?.displayName || '';
  const initials = nameForDisplay
    ? nameForDisplay.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() || 'IX';
  const displayName = nameForDisplay || user?.email?.split('@')[0] || 'Benutzer';
  const staff = isStaff(userRole);
  const busy = open !== null || mobileOpen;

  const account: Account = {
    loaded: authLoaded, user: !!user, staff, initials, displayName,
    email: user?.email ?? '', onLogin: openLogin, onLogout: handleLogout,
  };

  return (
    <>
      {staff && <WorkBar />}
      <header
        className={['sh', scrolled && 'is-scrolled', compact && !busy && 'is-compact'].filter(Boolean).join(' ')}
        onFocus={() => setCompact(false)}
      >
        <ServiceBar account={account} pmOpen={open === 'pm'} onPm={toggle('pm')} />
        <div className="sh-main">
          <div className="site-wrap sh-main-in">
            <a href="/" className="sh-home" aria-label={`${shell.brand.full} – zur Startseite`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={shell.logo.dark} alt={shell.brand.full} className="site-lockup" />
            </a>
            <nav className="sh-nav" aria-label="Hauptnavigation">
              <ul className="sh-nav-list">
                {GROUPS.map((g, i) => (
                  <Dropdown
                    key={g.href}
                    group={g}
                    end={i === GROUPS.length - 1}
                    open={open === g.href}
                    onOpen={toggle(g.href)}
                  />
                ))}
                {shell.menu.map((m) => (
                  <li key={m.href} className="sh-item"><a href={m.href} className="sh-nav-link">{m.label}</a></li>
                ))}
              </ul>
            </nav>
            <div className="sh-actions">
              <a className="sh-tel" href={TEL} aria-label={`${shell.phone.display} anrufen`}><Phone size={20} /></a>
              <a className="sh-cta" href={shell.cta.href}>{shell.cta.label} <ArrowRight size={18} /></a>
              <button type="button" className="sh-burger" onClick={() => setMobileOpen(true)} aria-label="Menü öffnen" aria-expanded={mobileOpen}>
                <Menu size={24} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {mobileOpen && <MobileMenu account={account} pathname={pathname} onClose={closeMobile} />}

      {/* **Dasselbe Fenster wie auf `/login`** – nur schliesst es hier, statt zur
          Startseite zu gehen: die Seite dahinter ist ja noch da. */}
      {loginOpen && (
        <LoginDialog onClose={() => setLoginOpen(false)} fallback={pathname} />
      )}
    </>
  );
}

type Account = {
  loaded: boolean; user: boolean; staff: boolean; initials: string; displayName: string; email: string;
  onLogin: () => void; onLogout: () => void;
};

/**
 * Arbeitsleiste für Personal – scrollt mit der Seite weg, sticky bleibt der Kopf.
 * Schlichte `<a>`: `?typ=` liest das ERP beim Laden; ein Router-Wechsel auf derselben
 * Route liesse den Filter stehen.
 */
function WorkBar() {
  const work = shell.account.workbar;
  return (
    <nav className="sh-work" aria-label="Arbeitsleiste">
      <div className="site-wrap sh-work-in">
        <a className="sh-work-home" href={work.href}><LayoutDashboard size={16} /> {work.label}</a>
        <ul className="sh-work-list">
          {work.links.map((l) => <li key={l.href}><a href={l.href}>{l.label}</a></li>)}
        </ul>
      </div>
    </nav>
  );
}

/** Ab 8 px eine Linie unten; beim Runterscrollen klappt die Servicezeile weg (wie die Website). */
function useScrollState(setScrolled: (v: boolean) => void, setCompact: (v: boolean) => void) {
  useEffect(() => {
    let lastY = window.scrollY;
    let ticking = false;
    const update = () => {
      const y = Math.max(0, window.scrollY);
      setScrolled(y > 8);
      if (y > lastY + 2 && y > 120) setCompact(true);
      else if (y < lastY - 2 || y <= 120) setCompact(false);
      lastY = y;
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    update();
    return () => window.removeEventListener('scroll', onScroll);
  }, [setScrolled, setCompact]);
}

/** Esc schliesst und gibt den Fokus an den Knopf zurück. */
function escCloses(isOpen: boolean, close: () => void) {
  return (e: ReactKeyboardEvent<HTMLElement>) => {
    if (e.key !== 'Escape' || !isOpen) return;
    close();
    e.currentTarget.querySelector<HTMLButtonElement>('button[aria-expanded]')?.focus();
  };
}

function ServiceBar({ account, pmOpen, onPm }: { account: Account; pmOpen: boolean; onPm: (open: boolean) => void }) {
  return (
    <div className="sh-service">
      <div className="site-wrap sh-service-in">
        {shell.announcement && (
          <p className="sh-news">
            <span>{shell.announcement.text}</span>
            <a href={shell.announcement.link.href}>{shell.announcement.link.label} <ArrowRight size={14} /></a>
          </p>
        )}
        <ul className="sh-links">
          {shell.notfall && (
            <li>
              <a className="sh-link sh-notfall" href={`tel:${shell.notfall.e164}`}>
                <Siren size={16} /> Notfall <span className="sh-tnum">{shell.notfall.display}</span>
              </a>
            </li>
          )}
          <li>
            <a className="sh-link" href={TEL}><Phone size={16} /> <span className="sh-tnum">{shell.phone.display}</span></a>
          </li>
          {!account.loaded ? (
            // Der Platz ist reserviert, bis die Sitzung bekannt ist – nichts springt.
            <li aria-hidden className="sh-link" style={{ visibility: 'hidden' }}><CircleUser size={16} /> {shell.account.login.label}</li>
          ) : account.user ? (
            <ProfileMenu account={account} open={pmOpen} onOpen={onPm} />
          ) : (
            <li>
              <button type="button" className="sh-link" onClick={account.onLogin}>
                <CircleUser size={16} /> {shell.account.login.label}
              </button>
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}

function ProfileMenu({ account, open, onOpen }: { account: Account; open: boolean; onOpen: (open: boolean) => void }) {
  return (
    <li className="sh-pm" data-disclosure onKeyDown={escCloses(open, () => onOpen(false))}>
      <button
        type="button"
        className="sh-link sh-pm-toggle"
        aria-expanded={open}
        aria-controls="profilmenu"
        onClick={() => onOpen(!open)}
      >
        <span className="sh-initials" aria-hidden>{account.initials}</span>
        <span className="sr-only">Profilmenü</span>
        <ChevronDown size={14} className="sh-chev" />
      </button>
      {open && (
        <div className="sh-pm-panel" id="profilmenu">
          <p className="sh-pm-who">
            <strong>{account.displayName}</strong>
            {account.email && <span>{account.email}</span>}
          </p>
          <ul className="sh-pm-list">
            <li><Link href={shell.account.profile.href}><UserIcon size={18} /> {shell.account.profile.label}</Link></li>
            <li className="sh-pm-sep">
              <button type="button" onClick={account.onLogout}><LogOut size={18} /> {shell.account.logout.label}</button>
            </li>
          </ul>
        </div>
      )}
    </li>
  );
}

/**
 * Ein Bereich als Dropdown: öffnet beim Zeigen und per Klick, Esc schliesst. Wer per Klick
 * schliesst, während der Zeiger noch darauf steht, will es zu haben (`closedByUser`).
 */
function Dropdown({ group, end, open, onOpen }: { group: Group; end: boolean; open: boolean; onOpen: (open: boolean) => void }) {
  const [hover, setHover] = useState(false);
  const [closedByUser, setClosedByUser] = useState(false);
  const shown = open || (hover && !closedByUser);
  return (
    <li
      className={['sh-item', end && 'sh-dd-end'].filter(Boolean).join(' ')}
      data-disclosure
      onMouseEnter={() => { setHover(true); setClosedByUser(false); }}
      onMouseLeave={() => { setHover(false); setClosedByUser(false); onOpen(false); }}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onOpen(false); }}
      onKeyDown={escCloses(shown, () => { setClosedByUser(true); onOpen(false); })}
    >
      <button
        type="button"
        className="sh-nav-link"
        aria-expanded={shown}
        onClick={() => { const next = !open; setClosedByUser(!next); onOpen(next); }}
      >
        {group.label} <ChevronDown size={16} className="sh-chev" />
      </button>
      {shown && (
        <div className="sh-dd-panel">
          <ul className="sh-dd-list">
            {group.children.map((c) => (
              <li key={c.href}>
                <a href={c.href} className="sh-dd-link">
                  <span className="sh-dd-label">{c.label}</span>
                  <span className="sh-dd-text">{c.text}</span>
                </a>
              </li>
            ))}
          </ul>
          <a href={group.href} className="sh-dd-overview">{group.overview} <ArrowRight size={16} /></a>
        </div>
      )}
    </li>
  );
}

/** Vollbild-Menü unter 1200 px: Bereiche als Akkordeons, dann Konto, Notfall, Aktionen. */
function MobileMenu({ account, pathname, onClose }: { account: Account; pathname: string; onClose: () => void }) {
  useEffect(() => {
    const root = document.documentElement;
    root.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => { root.style.overflow = ''; window.removeEventListener('keydown', onKey); };
  }, [onClose]);
  const more = shell.company.filter((c) => !shell.menu.some((m) => m.href === c.href));
  return (
    <div className="sh-m" role="dialog" aria-modal="true" aria-label="Menü">
      <div className="site-wrap sh-m-top">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={shell.logo.dark} alt={shell.brand.full} className="site-lockup" />
        <button type="button" className="sh-burger" onClick={onClose} aria-label="Menü schliessen" autoFocus><X size={24} /></button>
      </div>
      <nav className="site-wrap sh-m-nav" aria-label="Hauptnavigation (mobil)">
        {GROUPS.map((g) => (
          <details key={g.href}>
            <summary className="sh-m-link">{g.label} <ChevronDown size={20} /></summary>
            <ul className="sh-m-sub">
              {g.children.map((c) => <li key={c.href}><a href={c.href}>{c.label}<span>{c.text}</span></a></li>)}
              <li><a href={g.href} className="sh-m-overview">{g.overview}</a></li>
            </ul>
          </details>
        ))}
        {shell.menu.map((m) => <a key={m.href} href={m.href} className="sh-m-link">{m.label}</a>)}
        <ul className="sh-m-more">{more.map((c) => <li key={c.href}><a href={c.href}>{c.label}</a></li>)}</ul>
        <MobileAccount account={account} pathname={pathname} onClose={onClose} />
        {shell.notfall && (
          <p className="sh-m-notfall">
            <Siren size={18} /> Notfall bei Stillstand:
            <a href={`tel:${shell.notfall.e164}`} className="sh-tnum">{shell.notfall.display}</a>
          </p>
        )}
      </nav>
      <div className="sh-m-actions">
        <a className="sh-m-btn" href={TEL}><Phone size={18} /> Anrufen</a>
        <a className="sh-m-btn sh-m-btn-primary" href={shell.cta.href}>Anfrage <ArrowRight size={18} /></a>
      </div>
    </div>
  );
}

function MobileAccount({ account, pathname, onClose }: { account: Account; pathname: string; onClose: () => void }) {
  if (!account.loaded) return null;
  if (!account.user) {
    return (
      <ul className="sh-m-account">
        <li><button type="button" onClick={() => { onClose(); account.onLogin(); }}><CircleUser size={20} /> {shell.account.login.label}</button></li>
      </ul>
    );
  }
  return (
    <ul className="sh-m-account">
      <li>
        <Link href={shell.account.profile.href} onClick={onClose} aria-current={pathname === shell.account.profile.href ? 'page' : undefined}>
          <UserIcon size={20} /> {shell.account.profile.label} <span className="sh-m-who">{account.displayName}</span>
        </Link>
      </li>
      <li><button type="button" onClick={account.onLogout}><LogOut size={20} /> {shell.account.logout.label}</button></li>
    </ul>
  );
}
