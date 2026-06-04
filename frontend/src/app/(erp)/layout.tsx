'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Settings2, LayoutGrid, Package, Layers, Wrench, Building2, Settings,
  Users, Bell, LogOut, Search, ChevronRight, Menu, X,
} from 'lucide-react';
import { onAuthChange, logout } from '@/lib/firebase';
import { api } from '@/lib/api';
import { Navbar } from '@/components/layout/navbar';
import { Footer } from '@/components/layout/footer';
import type { User } from 'firebase/auth';

const navItems = [
  { href: '/erp', icon: LayoutGrid, label: 'ERP Feed', exact: true },
  { href: '/erp/artikel', icon: Package, label: 'Artikel' },
  { href: '/erp/stuecklisten', icon: Layers, label: 'Stücklisten' },
  { href: '/erp/arbeitspläne', icon: Wrench, label: 'Arbeitspläne' },
  { href: '/erp/firmen', icon: Building2, label: 'Firmen' },
];

const adminNavItems = [
  { href: '/admin/einstellungen', icon: Settings, label: 'Einstellungen' },
  { href: '/admin/benutzer', icon: Users, label: 'Benutzer' },
];

// Navbar height in px — must match the value in navbar.tsx (height: 72)
const NAVBAR_HEIGHT = 72;

export default function ERPLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (firebaseUser) => {
      if (!firebaseUser) {
        const currentPath = window.location.pathname;
        router.replace(`/login?from=${encodeURIComponent(currentPath)}`);
        return;
      }
      const token = await firebaseUser.getIdToken();
      api.setToken(token);
      setUser(firebaseUser);
      setLoading(false);
    });
    return unsubscribe;
  }, [router]);

  async function handleLogout() {
    await logout();
    router.push('/');
  }

  if (loading) {
    return (
      <>
        <Navbar />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: `calc(100vh - ${NAVBAR_HEIGHT}px - 280px)` }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ display: 'inline-block', height: 32, width: 32, borderRadius: '50%', border: '4px solid #2563eb', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite' }} />
            <p style={{ marginTop: 8, fontSize: 14, color: '#64748b' }}>Wird geladen…</p>
          </div>
        </div>
        <Footer />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </>
    );
  }

  const initials = user?.displayName
    ? user.displayName.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() || 'IX';

  function isActive(item: { href: string; exact?: boolean }) {
    if (item.exact) return pathname === item.href;
    return pathname === item.href || pathname.startsWith(item.href + '/');
  }

  const currentLabel = [...navItems, ...adminNavItems].find((i) =>
    i.href !== '/erp' ? pathname.startsWith(i.href) : pathname === i.href
  )?.label;

  return (
    <>
      <Navbar />

      <div style={{ display: 'flex', position: 'relative', background: '#f8fafc' }}>
        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-20 bg-black/30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`
            fixed left-0 z-30 w-60 flex-shrink-0
            bg-white border-r border-slate-200
            flex flex-col overflow-y-auto
            transition-transform duration-300 ease-in-out
            lg:sticky lg:self-start lg:translate-x-0
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          `}
          style={{ top: NAVBAR_HEIGHT, height: `calc(100vh - ${NAVBAR_HEIGHT}px)` }}
        >
          {/* Logo / ERP badge */}
          <div className="flex h-14 items-center justify-between px-4 border-b border-slate-200">
            <Link href="/erp" className="flex items-center gap-2 group">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white group-hover:bg-blue-700 transition-colors">
                <Settings2 className="h-3.5 w-3.5" />
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
                ERP-System
              </span>
            </Link>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
            {navItems.map((item) => {
              const active = isActive(item);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <item.icon className={`h-4 w-4 ${active ? 'text-blue-600' : 'text-slate-400'}`} />
                  {item.label}
                </Link>
              );
            })}

            <div className="pt-4 pb-1">
              <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Administration
              </p>
            </div>

            {adminNavItems.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <item.icon className={`h-4 w-4 ${active ? 'text-blue-600' : 'text-slate-400'}`} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* User info + logout */}
          <div className="border-t border-slate-200">
            <div className="flex items-center gap-3 px-4 py-3">
              {user?.photoURL ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.photoURL} alt={initials} className="h-8 w-8 rounded-full ring-2 ring-slate-200" />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                  {initials}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">
                  {user?.displayName || user?.email?.split('@')[0] || 'Benutzer'}
                </p>
                <p className="truncate text-xs text-slate-500">{user?.email}</p>
              </div>
              <button
                onClick={handleLogout}
                title="Abmelden"
                className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex flex-1 flex-col min-w-0">
          {/* ERP top bar — sticks below the website navbar */}
          <header
            className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4"
            style={{ position: 'sticky', top: NAVBAR_HEIGHT, zIndex: 10 }}
          >
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Breadcrumb */}
            <nav className="flex items-center gap-1 text-sm text-slate-500">
              <Link href="/erp" className="hover:text-slate-900 transition-colors">ERP</Link>
              {pathname !== '/erp' && currentLabel && (
                <>
                  <ChevronRight className="h-4 w-4 text-slate-300" />
                  <span className="font-medium text-slate-900">{currentLabel}</span>
                </>
              )}
            </nav>

            <div className="flex-1" />

            {/* Search */}
            <button className="hidden sm:flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100 transition-colors">
              <Search className="h-4 w-4" />
              Suchen…
              <kbd className="ml-1 rounded border border-slate-200 bg-white px-1 text-xs text-slate-400">
                ⌘K
              </kbd>
            </button>

            {/* Notifications */}
            <button className="relative p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors">
              <Bell className="h-5 w-5" />
              <span className="absolute top-0.5 right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
                3
              </span>
            </button>
          </header>

          {/* Page content */}
          <main className="flex-1">
            {children}
          </main>
        </div>
      </div>

      <Footer />
    </>
  );
}
