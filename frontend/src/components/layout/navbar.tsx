'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X, Settings2, LogIn } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

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

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const isHome = pathname === '/';

  return (
    <>
      <header
        className={cn(
          'fixed top-0 left-0 right-0 z-40 transition-all duration-300',
          scrolled || !isHome
            ? 'bg-white border-b border-slate-200 shadow-sm'
            : 'bg-transparent',
        )}
      >
        <div className="container">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2 group">
              <div
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-lg',
                  'bg-blue-600 text-white group-hover:bg-blue-700 transition-colors',
                )}
              >
                <Settings2 className="h-4 w-4" />
              </div>
              <span
                className={cn(
                  'font-bold text-lg tracking-tight',
                  scrolled || !isHome ? 'text-slate-900' : 'text-white',
                )}
              >
                Inexxio AG
              </span>
            </Link>

            {/* Desktop nav */}
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    scrolled || !isHome
                      ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                      : 'text-white/80 hover:text-white hover:bg-white/10',
                    pathname === link.href && (scrolled || !isHome)
                      ? 'text-slate-900 bg-slate-100'
                      : '',
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Desktop right */}
            <div className="hidden md:flex items-center gap-3">
              {/* Language switcher */}
              <div
                className={cn(
                  'flex items-center gap-1 text-sm font-medium',
                  scrolled || !isHome ? 'text-slate-500' : 'text-white/70',
                )}
              >
                <button className={cn(scrolled || !isHome ? 'text-slate-900' : 'text-white', 'hover:underline')}>
                  DE
                </button>
                <span>|</span>
                <button className="hover:underline">EN</button>
              </div>

              <Link href="/login">
                <Button
                  variant={scrolled || !isHome ? 'primary' : 'secondary'}
                  size="sm"
                  leftIcon={<LogIn className="h-4 w-4" />}
                >
                  Anmelden
                </Button>
              </Link>
            </div>

            {/* Mobile hamburger */}
            <button
              className="md:hidden p-2 rounded-lg"
              onClick={() => setMobileOpen(true)}
              aria-label="Navigation öffnen"
            >
              <Menu
                className={cn(
                  'h-5 w-5',
                  scrolled || !isHome ? 'text-slate-700' : 'text-white',
                )}
              />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-white animate-fade-in">
          <div className="flex items-center justify-between px-4 h-16 border-b border-slate-200">
            <Link href="/" className="flex items-center gap-2" onClick={() => setMobileOpen(false)}>
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
                <Settings2 className="h-4 w-4" />
              </div>
              <span className="font-bold text-lg text-slate-900">Inexxio AG</span>
            </Link>
            <button
              className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100"
              onClick={() => setMobileOpen(false)}
              aria-label="Navigation schliessen"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <nav className="flex-1 flex flex-col px-4 py-6 gap-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'px-4 py-3 rounded-xl text-base font-medium text-slate-700 hover:bg-slate-100',
                  pathname === link.href && 'bg-slate-100 text-slate-900',
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="px-4 pb-8 flex flex-col gap-3">
            <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
              <button className="text-slate-900 font-semibold">DE</button>
              <span className="text-slate-300">|</span>
              <button>EN</button>
            </div>
            <Link href="/login" className="block">
              <Button variant="primary" size="lg" className="w-full" leftIcon={<LogIn className="h-4 w-4" />}>
                Anmelden
              </Button>
            </Link>
          </div>
        </div>
      )}
    </>
  );
}
