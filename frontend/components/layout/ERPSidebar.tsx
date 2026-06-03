"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
  Building2,
  Settings,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/cn";

const navGroups = [
  {
    label: "Übersicht",
    items: [
      { href: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "Stammdaten",
    items: [
      { href: "/app/items", label: "Artikel", icon: Package },
      { href: "/app/companies", label: "Kunden & Lieferanten", icon: Building2 },
    ],
  },
  {
    label: "Prozesse",
    items: [
      { href: "/app/work-plans", label: "Arbeitspläne", icon: ClipboardList },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/app/admin", label: "Einstellungen", icon: Settings },
    ],
  },
];

export default function ERPSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex w-56 bg-gray-900 text-gray-300 flex-col">
      <div className="h-16 flex items-center px-4 border-b border-gray-800">
        <Link href="/" className="font-bold text-white text-lg">
          Inexxio
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3">
        {navGroups.map((group) => (
          <div key={group.label} className="mb-6">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-2 mb-2">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 px-2 py-2 rounded-lg text-sm font-medium transition-colors",
                        active
                          ? "bg-brand-600 text-white"
                          : "hover:bg-gray-800 hover:text-white"
                      )}
                    >
                      <item.icon size={16} />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
