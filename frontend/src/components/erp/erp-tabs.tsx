'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Users, Package } from 'lucide-react';

const TABS = [
  { href: '/erp', label: 'Benutzer', icon: Users },
  { href: '/erp/artikel', label: 'Artikel', icon: Package },
];

export function ErpTabs() {
  const pathname = usePathname();

  return (
    <div style={{
      display: 'flex', gap: 2, padding: '0 14px',
      borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0,
    }}>
      {TABS.map((tab) => {
        const active = pathname === tab.href;
        const Icon = tab.icon;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '11px 12px', fontSize: 13, fontWeight: 600,
              color: active ? '#2563eb' : '#64748b',
              borderBottom: `2px solid ${active ? '#2563eb' : 'transparent'}`,
              textDecoration: 'none', marginBottom: -1,
            }}
          >
            <Icon size={14} />
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
