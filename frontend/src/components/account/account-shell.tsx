'use client';

import { useState, useMemo } from 'react';
import { User, MapPin, Building2, Truck, FileText, Shield, Bell, Lock, Loader2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { useIsMobile } from '@/hooks/useIsMobile';
import { useProfileCompletion } from '@/hooks/useProfileCompletion';
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

function CompletionRing({ percentage }: { percentage: number }) {
  const radius = 17;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;
  const color = percentage === 100 ? '#16a34a' : percentage >= 60 ? '#f59e0b' : '#E51A14';
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" style={{ flexShrink: 0 }}>
      <circle cx="20" cy="20" r={radius} fill="none" stroke="#F1F5F9" strokeWidth="3" />
      <circle
        cx="20" cy="20" r={radius} fill="none"
        stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset}
        transform="rotate(-90 20 20)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="20" y="24" textAnchor="middle" style={{ fontSize: 9, fontWeight: 700, fill: color }}>{percentage}%</text>
    </svg>
  );
}

export function AccountShell({ profile, isLoading, onSave }: Props) {
  const [activeSection, setActiveSection] = useState<SectionId>('profile');
  const isMobile = useIsMobile(768);
  const completion = useProfileCompletion(profile);

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
      { id: 'privacy', label: 'Datenschutz', icon: Lock },
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
      case 'shipping': return <ShippingSection profile={profile} onSave={onSave} isBusiness={!!isBusiness} />;
      case 'invoice': return <InvoiceSection profile={profile} onSave={onSave} isBusiness={!!isBusiness} />;
      case 'security': return <SecuritySection profile={profile} />;
      case 'notifications': return <NotificationsSection profile={profile} onSave={onSave} />;
      case 'privacy': return <PrivacySection profile={profile} onSave={onSave} />;
    }
  }

  const totalMissing = completion.totalCount - completion.completedCount;
  const pctColor = completion.percentage === 100 ? '#16a34a' : completion.percentage >= 60 ? '#f59e0b' : '#E51A14';

  if (isMobile) {
    return (
      <div style={{ paddingBottom: 40 }}>
        {/* Mobile header */}
        <div style={{ padding: '16px 16px 0', background: '#fff', borderBottom: '1px solid #E2E8F0', marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
              background: profile?.photo_url ? 'transparent' : '#E51A14',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, fontWeight: 700, color: '#fff', overflow: 'hidden',
            }}>
              {profile?.photo_url
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={profile.photo_url} alt={fullName} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : initials}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <p style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {fullName || '—'}
              </p>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: '2px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {profile?.email || ''}
              </p>
            </div>
            {/* Mobile completion badge */}
            {profile && totalMissing > 0 && (
              <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: pctColor }} />
                <span style={{ fontSize: 12, color: pctColor, fontWeight: 600 }}>{completion.percentage}%</span>
              </div>
            )}
          </div>

          {/* Mobile progress bar */}
          {profile && (
            <div style={{ height: 3, background: '#F1F5F9', marginLeft: -16, marginRight: -16 }}>
              <div style={{
                height: '100%',
                width: `${completion.percentage}%`,
                background: pctColor,
                transition: 'width 0.6s ease',
                borderRadius: '0 2px 2px 0',
              }} />
            </div>
          )}

          {/* Horizontal scroll nav */}
          <div style={{ display: 'flex', gap: 0, overflowX: 'auto', marginLeft: -16, marginRight: -16, paddingLeft: 16 }}>
            {sections.map((s) => {
              const active = activeSection === s.id;
              const missing = completion.missingBySection[s.id as keyof typeof completion.missingBySection] ?? 0;
              return (
                <button
                  key={s.id}
                  onClick={() => setActiveSection(s.id)}
                  style={{
                    padding: '10px 14px', border: 'none', background: 'none',
                    fontSize: 13, fontWeight: active ? 600 : 400, whiteSpace: 'nowrap',
                    color: active ? '#E51A14' : '#64748b',
                    borderBottom: active ? '2px solid #E51A14' : '2px solid transparent',
                    cursor: 'pointer', flexShrink: 0, position: 'relative',
                  }}
                >
                  {s.label}
                  {missing > 0 && (
                    <span style={{
                      position: 'absolute', top: 6, right: 4,
                      background: '#f59e0b', color: '#fff',
                      borderRadius: '50%', width: 14, height: 14,
                      fontSize: 9, fontWeight: 700,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {missing}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div style={{ padding: '16px' }}>
          {isLoading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60 }}>
              <Loader2 style={{ width: 28, height: 28, color: '#E51A14', animation: 'spin 0.7s linear infinite' }} />
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}
          {!isLoading && renderSection()}
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '40px 24px', display: 'flex', gap: 32, alignItems: 'flex-start' }}>
      {/* Sidebar */}
      <aside style={{ width: 220, flexShrink: 0, position: 'sticky', top: 88 }}>
        {/* Avatar card */}
        <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, padding: '20px 16px', marginBottom: 12, textAlign: 'center' }}>
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

        {/* Completion card */}
        {profile && (
          <div style={{
            background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12,
            padding: '12px 14px', marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <CompletionRing percentage={completion.percentage} />
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#0F172A', margin: 0 }}>
                Profil {completion.percentage === 100 ? 'vollständig' : `${completion.percentage}% vollständig`}
              </p>
              {totalMissing > 0 ? (
                <p style={{ fontSize: 11, color: '#94a3b8', margin: '2px 0 0' }}>
                  {totalMissing} Pflichtfeld{totalMissing !== 1 ? 'er' : ''} fehlen
                </p>
              ) : (
                <p style={{ fontSize: 11, color: '#16a34a', margin: '2px 0 0' }}>Alle Pflichtfelder ausgefüllt</p>
              )}
            </div>
          </div>
        )}

        {/* Nav */}
        <nav style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
          {sections.map((s, i) => {
            const Icon = s.icon;
            const active = activeSection === s.id;
            const missing = completion.missingBySection[s.id as keyof typeof completion.missingBySection] ?? 0;
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
                <span style={{ flex: 1 }}>{s.label}</span>
                {missing > 0 && (
                  <span style={{
                    background: '#f59e0b', color: '#fff',
                    borderRadius: '50%', width: 16, height: 16, minWidth: 16,
                    fontSize: 9, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {missing}
                  </span>
                )}
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
