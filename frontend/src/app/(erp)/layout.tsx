'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Settings2, LayoutGrid, Package, Layers, Wrench, Building2, Settings,
  Users, Bell, LogOut, Search, ChevronRight, Menu, X
} from 'lucide-react';
import { onAuthChange, logout } from '@/lib/firebase';
import { api } from '@/lib/api';
import type { User } from 'firebase/auth';

const navItems = [
  { href: '/erp', icon: LayoutGrid, label: 'ERP Feed' },
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

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar Overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-30 w-64 flex-shrink-0 bg-slate-900 text-white
        transition-transform duration-300 ease-in-out
        lg:static lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-800">
          <Link href="/erp" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
              <Settings2 className="h-4 w-4" />
            </div>
            <span className="font-bold text-white">Inexxio ERP</span>
          </Link>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden text-slate-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}

          <div className="pt-4 pb-1">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Admin
            </p>
          </div>
          {adminNavItems.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div className="border-t border-slate-800 p-3">
          <div className="flex items-center gap-3">
            {user?.photoURL ? (
              <img src={user.photoURL} alt={initials} className="h-8 w-8 rounded-full" />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                {initials}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-white">
                {user?.displayName || user?.email?.split('@')[0] || 'Benutzer'}
              </p>
              <p className="truncate text-xs text-slate-400">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              title="Abmelden"
              className="text-slate-400 hover:text-white transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden text-slate-500 hover:text-slate-900"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Breadcrumb */}
          <nav className="flex items-center gap-1 text-sm text-slate-500">
            <Link href="/erp" className="hover:text-slate-900">ERP</Link>
            {pathname !== '/erp' && (
              <>
                <ChevronRight className="h-4 w-4" />
                <span className="text-slate-900 font-medium capitalize">
                  {pathname.split('/').pop()?.replace('-', ' ') || ''}
                </span>
              </>
            )}
          </nav>

          <div className="flex-1" />

          {/* Search hint */}
          <button className="hidden sm:flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100 transition-colors">
            <Search className="h-4 w-4" />
            Suchen…
            <kbd className="ml-1 rounded border border-slate-300 bg-white px-1 text-xs text-slate-400">
              ⌘K
            </kbd>
          </button>

          {/* Notifications */}
          <button className="relative text-slate-500 hover:text-slate-900 transition-colors">
            <Bell className="h-5 w-5" />
            <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
              3
            </span>
          </button>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
