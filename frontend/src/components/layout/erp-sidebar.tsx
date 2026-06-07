'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Package,
  Building2,
  Settings,
  Users,
  LogOut,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getInitials } from '@/lib/utils';

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { href: '/erp', label: 'ERP Feed', icon: <LayoutDashboard className="h-5 w-5" /> },
  { href: '/artikel', label: 'Artikel', icon: <Package className="h-5 w-5" /> },
  { href: '/firmen', label: 'Kunden & Lieferanten', icon: <Building2 className="h-5 w-5" /> },
];

const adminItems: NavItem[] = [
  { href: '/admin/einstellungen', label: 'Einstellungen', icon: <Settings className="h-5 w-5" />, adminOnly: true },
  { href: '/admin/benutzer', label: 'Benutzer', icon: <Users className="h-5 w-5" />, adminOnly: true },
];

interface ErpSidebarProps {
  userEmail?: string;
  userName?: string;
  userRole?: string;
  onLogout?: () => void;
}

export function ErpSidebar({
  userEmail = 'user@inexxio.com',
  userName = 'Benutzer',
  userRole = 'user',
  onLogout,
}: ErpSidebarProps) {
  const pathname = usePathname();
  const isAdmin = userRole === 'admin' || userRole === 'manager';

  const isActive = (href: string) => {
    if (href === '/erp') return pathname === '/erp';
    return pathname.startsWith(href);
  };

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-slate-900 text-white">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-slate-800">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 font-bold text-sm">
          IX
        </div>
        <span className="font-bold text-base tracking-tight">Inexxio ERP</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <div className="mb-2 px-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Module
          </p>
        </div>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group',
              isActive(item.href)
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800',
            )}
          >
            <span className={cn(isActive(item.href) ? 'text-white' : 'text-slate-500 group-hover:text-white')}>
              {item.icon}
            </span>
            {item.label}
            {isActive(item.href) && (
              <ChevronRight className="ml-auto h-4 w-4 opacity-60" />
            )}
          </Link>
        ))}

        {isAdmin && (
          <>
            <div className="mt-6 mb-2 px-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Administration
              </p>
            </div>
            {adminItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group',
                  isActive(item.href)
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800',
                )}
              >
                <span className={cn(isActive(item.href) ? 'text-white' : 'text-slate-500 group-hover:text-white')}>
                  {item.icon}
                </span>
                {item.label}
                {isActive(item.href) && (
                  <ChevronRight className="ml-auto h-4 w-4 opacity-60" />
                )}
              </Link>
            ))}
          </>
        )}
      </nav>

      {/* User section */}
      <div className="border-t border-slate-800 p-3">
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer group">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white shrink-0">
            {getInitials(userName)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">{userName}</p>
            <p className="text-xs text-slate-500 truncate">{userEmail}</p>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className="text-slate-500 hover:text-white transition-colors opacity-0 group-hover:opacity-100"
              aria-label="Abmelden"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
