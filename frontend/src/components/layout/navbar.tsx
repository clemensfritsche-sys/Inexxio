'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Menu, X, LogIn, LayoutGrid, LogOut, ChevronDown, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { onAuthChange, logout } from '@/lib/firebase';
import { api } from '@/lib/api';
import type { User } from 'firebase/auth';

const ROLE_KEY = 'inexxio_user_role';
const NAME_KEY = 'inexxio_user_fullname';

const navLinks = [
  { href: '/ueber-uns', label: 'Über uns' },
  { href: '/kontakt', label: 'Kontakt' },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [roleFetched, setRoleFetched] = useState(false);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [profileName, setProfileName] = useState('');
  const pathname = usePathname();
  const router = useRouter();
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setUserMenuOpen(false);
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
          const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ');
          if (fullName) {
            localStorage.setItem(NAME_KEY, fullName);
            setProfileName(fullName);
          }
        } catch {
          // keep cached values
        } finally {
          setRoleFetched(true);
        }
      } else {
        setUserRole(null);
        setRoleFetched(true);
        setProfileName('');
        localStorage.removeItem(ROLE_KEY);
        localStorage.removeItem(NAME_KEY);
      }
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
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
    setUserMenuOpen(false);
    setMobileOpen(false);
    await logout();
    router.push('/');
  }

  const loginHref = pathname.startsWith('/login')
    ? '/login'
    : `/login?from=${encodeURIComponent(pathname)}`;

  const nameForDisplay = profileName || user?.displayName || '';
  const initials = nameForDisplay
    ? nameForDisplay.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() || 'IX';

  const displayName = nameForDisplay || user?.email?.split('@')[0] || 'Benutzer';

  // Show ERP when role allows, or when role is unknown (still loading / backend down).
  // The ERP layout is the real security gate — it redirects customer/supplier away.
  const canAccessERP = userRole === 'employee' || userRole === 'admin' || userRole === null;

  return (
    <>
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: scrolled ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,0.88)',
          backdropFilter: 'blur(12px) saturate(1.2)',
          borderBottom: '1px solid var(--border-1)',
          boxShadow: scrolled ? 'var(--shadow-sm)' : 'var(--shadow-xs)',
          transition: 'box-shadow 0.3s',
        }}
      >
        <div className="ix-wrap">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 72 }}>

            {/* Logo */}
            <Link href="/" style={{ display: 'flex', alignItems: 'center' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/logo.png"
                alt="Inexxio AG"
                style={{ height: 28, width: 'auto', display: 'block' }}
              />
            </Link>

            {/* Desktop nav */}
            <nav style={{ alignItems: 'center', gap: 28 }} className="hidden md:flex">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn('ix-nav-link', pathname === link.href && 'ix-nav-link-active')}
                  style={pathname === link.href ? { color: 'var(--ix-red)' } : {}}
                >
                  {link.label}
                </Link>
              ))}
              {authLoaded && user && canAccessERP && (
                <Link
                  href="/erp"
                  className={cn('ix-nav-link', pathname.startsWith('/erp') || pathname.startsWith('/admin') ? 'ix-nav-link-active' : '')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    ...(pathname.startsWith('/erp') || pathname.startsWith('/admin') ? { color: 'var(--ix-red)' } : {}),
                  }}
                >
                  <LayoutGrid style={{ width: 13, height: 13 }} />
                  ERP
                </Link>
              )}
            </nav>

            {/* Desktop right */}
            <div className="hidden md:flex" style={{ alignItems: 'center', gap: 16 }}>
              {/* Language selector */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, font: '500 14px var(--font-body)', color: 'var(--fg-3)' }}>
                <button style={{ color: 'var(--fg-1)', fontWeight: 600 }}>DE</button>
                <span style={{ color: 'var(--border-2)' }}>|</span>
                <button style={{ color: 'var(--fg-3)' }}>EN</button>
              </div>

              {authLoaded && (
                user ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div ref={userMenuRef} style={{ position: 'relative' }}>
                      <button
                        onClick={() => setUserMenuOpen((o) => !o)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          background: 'none',
                          border: '1px solid var(--border-1)',
                          borderRadius: 40,
                          padding: '5px 10px 5px 5px',
                          cursor: 'pointer',
                          transition: 'background 0.15s',
                        }}
                        className="hover:bg-slate-50"
                      >
                        {user.photoURL ? (
                          /* eslint-disable-next-line @next/next/no-img-element */
                          <img
                            src={user.photoURL}
                            alt={initials}
                            style={{ width: 28, height: 28, borderRadius: '50%', display: 'block' }}
                          />
                        ) : (
                          <div style={{
                            width: 28,
                            height: 28,
                            borderRadius: '50%',
                            background: 'var(--ix-red, #E51A14)',
                            color: '#fff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 11,
                            fontWeight: 700,
                            letterSpacing: '0.02em',
                          }}>
                            {initials}
                          </div>
                        )}
                        <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-1)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {displayName}
                        </span>
                        <ChevronDown style={{ width: 13, height: 13, color: 'var(--fg-3)', transition: 'transform 0.2s', transform: userMenuOpen ? 'rotate(180deg)' : 'none' }} />
                      </button>

                      {userMenuOpen && (
                        <div style={{
                          position: 'absolute',
                          right: 0,
                          top: 'calc(100% + 8px)',
                          background: '#fff',
                          border: '1px solid var(--border-1)',
                          borderRadius: 12,
                          boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
                          padding: '6px',
                          minWidth: 220,
                          zIndex: 100,
                        }}>
                          <div style={{ padding: '8px 10px 10px', borderBottom: '1px solid var(--border-1)', marginBottom: 4 }}>
                            <p style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)', margin: 0 }}>{displayName}</p>
                            <p style={{ font: '12px var(--font-body)', color: 'var(--fg-3)', margin: '2px 0 0' }}>{user.email}</p>
                          </div>
                          <Link
                            href="/konto"
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '8px 10px',
                              borderRadius: 8,
                              font: '500 13px var(--font-body)',
                              color: 'var(--fg-2)',
                              textDecoration: 'none',
                            }}
                            className="hover:bg-slate-50"
                          >
                            <Settings style={{ width: 14, height: 14 }} />
                            Kontoeinstellungen
                          </Link>
                          <div style={{ margin: '4px 10px', borderTop: '1px solid var(--border-1)' }} />
                          <button
                            onClick={handleLogout}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              width: '100%',
                              padding: '8px 10px',
                              background: 'none',
                              border: 'none',
                              borderRadius: 8,
                              cursor: 'pointer',
                              font: '500 13px var(--font-body)',
                              color: 'var(--fg-2)',
                              textAlign: 'left',
                            }}
                            className="hover:bg-slate-50"
                          >
                            <LogOut style={{ width: 14, height: 14 }} />
                            Abmelden
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <Link
                    href={loginHref}
                    className="ix-btn ix-btn-primary"
                    style={{ padding: '10px 20px', fontSize: 14 }}
                  >
                    <LogIn style={{ width: 15, height: 15 }} />
                    Anmelden
                  </Link>
                )
              )}
            </div>

            {/* Mobile hamburger */}
            <button
              className="md:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Navigation öffnen"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8, color: 'var(--fg-1)' }}
            >
              <Menu style={{ width: 22, height: 22 }} />
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              padding: '8px 20px 28px',
              borderTop: '1px solid var(--border-1)',
              background: '#fff',
            }}
          >
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                style={{
                  font: '600 19px/1 var(--font-display)',
                  letterSpacing: '-0.02em',
                  padding: '14px 0',
                  borderBottom: '1px solid var(--border-1)',
                  color: pathname === link.href ? 'var(--ix-red)' : 'var(--fg-1)',
                  textDecoration: 'none',
                }}
              >
                {link.label}
              </Link>
            ))}

            {authLoaded && user && canAccessERP && (
              <Link
                href="/erp"
                style={{
                  font: '600 19px/1 var(--font-display)',
                  letterSpacing: '-0.02em',
                  padding: '14px 0',
                  borderBottom: '1px solid var(--border-1)',
                  color: pathname.startsWith('/erp') || pathname.startsWith('/admin') ? 'var(--ix-red)' : 'var(--fg-1)',
                  textDecoration: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <LayoutGrid style={{ width: 16, height: 16 }} />
                ERP
              </Link>
            )}

            <div style={{ paddingTop: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, font: '500 14px var(--font-body)', color: 'var(--fg-3)' }}>
                <button style={{ color: 'var(--fg-1)', fontWeight: 600 }}>DE</button>
                <span>|</span>
                <button>EN</button>
              </div>

              {authLoaded && (
                user ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {user.photoURL ? (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img src={user.photoURL} alt={initials} style={{ width: 32, height: 32, borderRadius: '50%' }} />
                      ) : (
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--ix-red, #E51A14)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>
                          {initials}
                        </div>
                      )}
                      <div>
                        <p style={{ margin: 0, font: '600 14px var(--font-body)', color: 'var(--fg-1)' }}>{displayName}</p>
                        <p style={{ margin: 0, font: '12px var(--font-body)', color: 'var(--fg-3)' }}>{user.email}</p>
                      </div>
                    </div>
                    <Link
                      href="/konto"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        border: '1px solid var(--border-1)',
                        borderRadius: 8,
                        padding: '10px 16px',
                        font: '500 14px var(--font-body)',
                        color: 'var(--fg-2)',
                        textDecoration: 'none',
                      }}
                    >
                      <Settings style={{ width: 15, height: 15 }} />
                      Kontoeinstellungen
                    </Link>
                    <button
                      onClick={handleLogout}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        background: 'none',
                        border: '1px solid var(--border-1)',
                        borderRadius: 8,
                        padding: '10px 16px',
                        cursor: 'pointer',
                        font: '500 14px var(--font-body)',
                        color: 'var(--fg-2)',
                      }}
                    >
                      <LogOut style={{ width: 15, height: 15 }} />
                      Abmelden
                    </button>
                  </div>
                ) : (
                  <Link href={loginHref} className="ix-btn ix-btn-primary" style={{ justifyContent: 'center' }}>
                    <LogIn style={{ width: 16, height: 16 }} />
                    Anmelden
                  </Link>
                )
              )}
            </div>
          </div>
        )}
      </header>

      {mobileOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 49,
            background: 'rgba(0,0,0,0.3)',
            backdropFilter: 'blur(4px)',
          }}
          onClick={() => setMobileOpen(false)}
        />
      )}
      {mobileOpen && (
        <button
          onClick={() => setMobileOpen(false)}
          aria-label="Navigation schliessen"
          style={{
            position: 'fixed',
            top: 20,
            right: 20,
            zIndex: 51,
            background: '#fff',
            border: 'none',
            borderRadius: '50%',
            width: 40,
            height: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: 'var(--shadow-md)',
          }}
        >
          <X style={{ width: 18, height: 18 }} />
        </button>
      )}
    </>
  );
}
