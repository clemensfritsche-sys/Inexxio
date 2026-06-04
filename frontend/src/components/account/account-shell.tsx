'use client';

import { useState, useMemo } from 'react';
import { User, MapPin, Building2, Truck, FileText, Shield, Bell, Lock, Loader2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { ProfileSection } from './sections/profile-section';
import { ContactSection } from './sections/contact-section';
import { CompanySection } from './sections/company-section';
import { ShippingSection } from './sections/shipping-section';
import { InvoiceSection } from './sections/invoice-section';
import { SecuritySection } from './sections/security-section';
import { NotificationsSection } from './sections/notifications-section';
import { PrivacySection } from './sections/privacy-section';

type SectionId = 'profile' | 'contact' | 'company' | 'shipping' | 'invoice' | 'security' | 'notifications' | 'privacy';

interface Props {
  profile: UserProfile | null;
  isLoading: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function AccountShell({ profile, isLoading, onSave }: Props) {
  const [activeSection, setActiveSection] = useState<SectionId>('profile');

  const isBusiness = profile?.is_business || profile?.role === 'supplier';
  const isCustomer = profile?.role === 'customer';
  const isEmployee = profile?.role === 'employee';
  const isSupplier = profile?.role === 'supplier';

  const sections = useMemo(() => {
    const base: { id: SectionId; label: string; icon: React.ElementType }[] = [
      { id: 'profile', label: 'Mein Profil', icon: User },
      { id: 'contact', label: 'Kontakt & Adresse', icon: MapPin },
    ];
    if (isBusiness || isSupplier) {
      base.push({ id: 'company', label: 'Firmendaten', icon: Building2 });
    }
    if (isCustomer || isSupplier) {
      base.push({ id: 'shipping', label: 'Lieferadressen', icon: Truck });
      base.push({ id: 'invoice', label: 'Rechnungsadresse', icon: FileText });
    }
    base.push(
      { id: 'security', label: 'Sicherheit', icon: Shield },
      { id: 'notifications', label: 'Benachrichtigungen', icon: Bell },
      { id: 'privacy', label: 'Datenschutz & Marketing', icon: Lock },
    );
    return base;
  }, [isBusiness, isCustomer, isSupplier]);

  const fullName = profile
    ? [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.display_name || profile.email
    : '';

  const initials = fullName
    ? fullName.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : '??';

  function renderSection() {
    if (!profile) return null;
    switch (activeSection) {
      case 'profile': return <ProfileSection profile={profile} onSave={onSave} isEmployee={isEmployee} isCustomer={isCustomer} />;
      case 'contact': return <ContactSection profile={profile} onSave={onSave} />;
      case 'company': return <CompanySection profile={profile} onSave={onSave} />;
      case 'shipping': return <ShippingSection profile={profile} onSave={onSave} isBusiness={isBusiness} />;
      case 'invoice': return <InvoiceSection profile={profile} onSave={onSave} isBusiness={!!isBusiness} />;
      case 'security': return <SecuritySection profile={profile} />;
      case 'notifications': return <NotificationsSection profile={profile} onSave={onSave} />;
      case 'privacy': return <PrivacySection profile={profile} onSave={onSave} />;
    }
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '40px 24px', display: 'flex', gap: 32, alignItems: 'flex-start' }}>
      {/* Sidebar */}
      <aside style={{ width: 220, flexShrink: 0, position: 'sticky', top: 88 }}>
        {/* Avatar card */}
        <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, padding: '20px 16px', marginBottom: 16, textAlign: 'center' }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%', margin: '0 auto 10px',
            background: profile?.photo_url ? 'transparent' : '#E51A14',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 700, color: '#fff', overflow: 'hidden',
          }}>
            {profile?.photo_url
              // eslint-disable-next-line @next/next/no-img-element
              ? <img src={profile.photo_url} alt={fullName} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : initials}
          </div>
          <p style={{ fontSize: 14, fontWeight: 600, color: '#0F172A', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {fullName || '—'}
          </p>
          <p style={{ fontSize: 12, color: '#94a3b8', margin: '2px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {profile?.email || ''}
          </p>
        </div>

        {/* Nav */}
        <nav style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
          {sections.map((s, i) => {
            const Icon = s.icon;
            const active = activeSection === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '11px 14px', background: active ? '#FEF2F2' : 'none',
                  border: 'none', borderBottom: i < sections.length - 1 ? '1px solid #F1F5F9' : 'none',
                  color: active ? '#E51A14' : '#374151', cursor: 'pointer',
                  fontSize: 13, fontWeight: active ? 600 : 400,
                  textAlign: 'left', transition: 'background 0.15s',
                }}
              >
                <Icon style={{ width: 15, height: 15, flexShrink: 0 }} />
                {s.label}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, minWidth: 0 }}>
        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 80 }}>
            <Loader2 style={{ width: 28, height: 28, color: '#E51A14', animation: 'spin 0.7s linear infinite' }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}
        {!isLoading && renderSection()}
      </main>
    </div>
  );
}
