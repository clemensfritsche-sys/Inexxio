'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Settings2, LayoutGrid, Package, Layers, Wrench, Building2, Settings,
  Users, Bell, LogOut, Search, ChevronRight, Menu, X, Globe
} from 'lucide-react';
import { onAuthChange, logout } from '@/lib/firebase';
import { api } from '@/lib/api';
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

export default function ERPLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (firebaseUser) => {
      if (!firebaseUser) {
        router.replace('/login');
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
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          <p className="mt-2 text-sm text-slate-500">Wird geladen…</p>
        </div>
      </div>
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
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-30 w-60 flex-shrink-0
        bg-white border-r border-slate-200
        flex flex-col
        transition-transform duration-300 ease-in-out
        lg:static lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo — links to public website */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-200">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white group-hover:bg-blue-700 transition-colors">
              <Settings2 className="h-4 w-4" />
            </div>
            <span className="font-bold text-slate-900 text-base tracking-tight">
              Inexxio AG
            </span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* ERP badge */}
        <div className="px-4 py-2 border-b border-slate-100">
          <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
            <LayoutGrid className="h-3 w-3" />
            ERP-System
          </span>
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

        {/* Back to website + user */}
        <div className="border-t border-slate-200">
          <Link
            href="/"
            className="flex items-center gap-2 px-4 py-2.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Globe className="h-3.5 w-3.5" />
            Zurück zur Website
          </Link>
          <div className="flex items-center gap-3 px-4 py-3 border-t border-slate-100">
            {user?.photoURL ? (
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
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4">
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
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
