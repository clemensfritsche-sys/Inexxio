'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X, LogIn } from 'lucide-react';
import { cn } from '@/lib/utils';

const navLinks = [
  { href: '/ueber-uns', label: 'Über uns' },
  { href: '/kontakt', label: 'Kontakt' },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

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
            <nav style={{ display: 'flex', alignItems: 'center', gap: 28 }} className="hidden md:flex">
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
            </nav>

            {/* Desktop right */}
            <div className="hidden md:flex" style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, font: '500 14px var(--font-body)', color: 'var(--fg-3)' }}>
                <button style={{ color: 'var(--fg-1)', fontWeight: 600 }}>DE</button>
                <span style={{ color: 'var(--border-2)' }}>|</span>
                <button style={{ color: 'var(--fg-3)' }}>EN</button>
              </div>
              <Link
                href="/login"
                className="ix-btn ix-btn-primary"
                style={{ padding: '10px 20px', fontSize: 14 }}
              >
                <LogIn style={{ width: 15, height: 15 }} />
                Anmelden
              </Link>
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
              padding: '8px 40px 28px',
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
            <div style={{ paddingTop: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, font: '500 14px var(--font-body)', color: 'var(--fg-3)' }}>
                <button style={{ color: 'var(--fg-1)', fontWeight: 600 }}>DE</button>
                <span>|</span>
                <button>EN</button>
              </div>
              <Link href="/login" className="ix-btn ix-btn-primary" style={{ justifyContent: 'center' }}>
                <LogIn style={{ width: 16, height: 16 }} />
                Anmelden
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* Full-screen mobile overlay */}
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
