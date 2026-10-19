'use client';

import { useState } from 'react';
import { User, Shield, Loader2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { isStaff } from '@/lib/record-status';
import { useIsMobile } from '@/hooks/useIsMobile';
import { useProfileCompletion } from '@/hooks/useProfileCompletion';
import { ProfileSection } from './sections/profile-section';
import { SecuritySection } from './sections/security-section';

// Zwei Reiter: «Mein Profil» bündelt Person + Adressen + Kommunikation in EINER Sektion
// (ein Formular, ein Auto-Save); «Sicherheit» verwaltet die Passkeys.
type SectionId = 'profile' | 'security';

const SECTIONS: { id: SectionId; label: string; icon: React.ElementType }[] = [
  { id: 'profile', label: 'Mein Profil', icon: User },
  { id: 'security', label: 'Sicherheit', icon: Shield },
];

interface Props {
  profile: UserProfile | null;
  isLoading: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

/** Der Ton des Fortschritts – an EINER Stelle für Ring, Punkt und Balken. */
function completionTone(percentage: number): string {
  if (percentage === 100) return 'var(--success)';
  return percentage >= 60 ? 'var(--warning)' : 'var(--inexxio-red)';
}

const CARD: React.CSSProperties = {
  background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 12,
};
const ELLIPSIS: React.CSSProperties = {
  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
};

function CompletionRing({ percentage }: { percentage: number }) {
  const radius = 17;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;
  const color = completionTone(percentage);
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" style={{ flexShrink: 0 }}>
      <circle cx="20" cy="20" r={radius} fill="none" style={{ stroke: 'var(--bg-3)' }} strokeWidth="3" />
      <circle
        cx="20" cy="20" r={radius} fill="none"
        strokeWidth="3" strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset}
        transform="rotate(-90 20 20)"
        style={{ stroke: color, transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="20" y="24" textAnchor="middle" style={{ fontSize: 9, fontWeight: 700, fill: color }}>{percentage}%</text>
    </svg>
  );
}

/** Profilbild oder Initialen auf Rot – im Kopf (Telefon) wie in der Seitenleiste. */
function Avatar({ profile, name, size, text }: {
  profile: UserProfile | null; name: string; size: number; text: number;
}) {
  const initials = name
    ? name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : '??';
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      background: profile?.photo_url ? 'transparent' : 'var(--inexxio-red)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: text, fontWeight: 700, color: 'var(--fg-on-red)', overflow: 'hidden',
    }}>
      {profile?.photo_url
        // eslint-disable-next-line @next/next/no-img-element
        ? <img src={profile.photo_url} alt={name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : initials}
    </div>
  );
}

/** Name und Anmelde-E-Mail – zweimal dieselbe Auskunft, einmal gebaut. */
function Identity({ profile, name, size }: { profile: UserProfile | null; name: string; size: number }) {
  return (
    <>
      <p style={{ fontSize: size, fontWeight: 600, color: 'var(--fg-1)', margin: 0, ...ELLIPSIS }}>
        {name || '—'}
      </p>
      <p style={{ fontSize: 12, color: 'var(--fg-4)', margin: '2px 0 0', ...ELLIPSIS }}>
        {profile?.email || ''}
      </p>
    </>
  );
}

/** Wie viele Pflichtfelder in einem Reiter offen sind – eine runde Zahl in der Warnfarbe. */
function MissingBadge({ count, size, style }: { count: number; size: number; style?: React.CSSProperties }) {
  if (count <= 0) return null;
  return (
    <span style={{
      background: 'var(--warning)', color: 'var(--color-text-inverse)',
      borderRadius: '50%', width: size, height: size, minWidth: size,
      fontSize: 9, fontWeight: 700,
      display: 'flex', alignItems: 'center', justifyContent: 'center', ...style,
    }}>
      {count}
    </span>
  );
}

function Loading({ padding }: { padding: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding }}>
      <Loader2 style={{ width: 28, height: 28, color: 'var(--inexxio-red)', animation: 'spin 0.7s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/**
 * Die Konto-Seite: **ein** Satz Bausteine (Avatar, Identität, Fortschritt, Reiter-Zähler),
 * zwei Anordnungen – auf dem Telefon ein Kopf mit Reitern, sonst eine Seitenleiste. Vorher
 * baute jeder Zweig Initialen, Prozentfarbe und Zähler für sich.
 */
export function AccountShell({ profile, isLoading, onSave }: Props) {
  const [activeSection, setActiveSection] = useState<SectionId>('profile');
  const isMobile = useIsMobile(768);
  const completion = useProfileCompletion(profile);
  const fullName = profile ? userDisplayName(profile) : '';

  const totalMissing = completion.totalCount - completion.completedCount;
  const tone = completionTone(completion.percentage);
  const missingIn = (id: SectionId) =>
    completion.missingBySection[id as keyof typeof completion.missingBySection] ?? 0;

  const content = isLoading ? <Loading padding={isMobile ? 60 : 80} /> : profile && (
    activeSection === 'profile'
      // Personal (Admin wie Mitarbeiter) sieht seine Anstellung und ändert seine
      // Gesellschaft nicht selbst – dieselbe Frage wie überall: `isStaff`.
      ? <ProfileSection profile={profile} onSave={onSave} isStaff={isStaff(profile.role)} />
      : <SecuritySection profile={profile} />
  );

  if (isMobile) {
    return (
      <div style={{ paddingBottom: 40 }}>
        <div style={{ padding: '16px 16px 0', background: 'var(--bg-1)', borderBottom: '1px solid var(--border-1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <Avatar profile={profile} name={fullName} size={44} text={16} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <Identity profile={profile} name={fullName} size={15} />
            </div>
            {profile && totalMissing > 0 && (
              <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: tone }} />
                <span style={{ fontSize: 12, color: tone, fontWeight: 600 }}>{completion.percentage}%</span>
              </div>
            )}
          </div>

          {profile && (
            <div style={{ height: 3, background: 'var(--bg-3)', marginLeft: -16, marginRight: -16 }}>
              <div style={{
                height: '100%', width: `${completion.percentage}%`, background: tone,
                transition: 'width 0.6s ease', borderRadius: '0 2px 2px 0',
              }} />
            </div>
          )}

          <div style={{ display: 'flex', gap: 0, overflowX: 'auto', marginLeft: -16, marginRight: -16, paddingLeft: 16 }}>
            {SECTIONS.map((s) => {
              const active = activeSection === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => setActiveSection(s.id)}
                  style={{
                    padding: '10px 14px', border: 'none', background: 'none',
                    fontSize: 13, fontWeight: active ? 600 : 400, whiteSpace: 'nowrap',
                    color: active ? 'var(--inexxio-red)' : 'var(--fg-3)',
                    borderBottom: active ? '2px solid var(--inexxio-red)' : '2px solid transparent',
                    cursor: 'pointer', flexShrink: 0, position: 'relative',
                  }}
                >
                  {s.label}
                  <MissingBadge count={missingIn(s.id)} size={14}
                    style={{ position: 'absolute', top: 6, right: 4 }} />
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ padding: '16px' }}>{content}</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '40px 24px', display: 'flex', gap: 32, alignItems: 'flex-start' }}>
      <aside style={{ width: 220, flexShrink: 0, position: 'sticky', top: 88 }}>
        <div style={{ ...CARD, padding: '20px 16px', marginBottom: 12, textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <Avatar profile={profile} name={fullName} size={56} text={18} />
          </div>
          <Identity profile={profile} name={fullName} size={14} />
        </div>

        {profile && (
          <div style={{ ...CARD, padding: '12px 14px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
            <CompletionRing percentage={completion.percentage} />
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>
                Profil {completion.percentage === 100 ? 'vollständig' : `${completion.percentage}% vollständig`}
              </p>
              {totalMissing > 0 ? (
                <p style={{ fontSize: 11, color: 'var(--fg-4)', margin: '2px 0 0' }}>
                  {totalMissing} Pflichtfeld{totalMissing !== 1 ? 'er' : ''} offen
                </p>
              ) : (
                <p style={{ fontSize: 11, color: 'var(--success)', margin: '2px 0 0' }}>Alles erledigt</p>
              )}
            </div>
          </div>
        )}

        <nav style={{ ...CARD, overflow: 'hidden' }}>
          {SECTIONS.map((s, i) => {
            const Icon = s.icon;
            const active = activeSection === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '11px 14px',
                  background: active ? 'var(--color-primary-subtle)' : 'none',
                  border: 'none', borderBottom: i < SECTIONS.length - 1 ? '1px solid var(--border-1)' : 'none',
                  color: active ? 'var(--inexxio-red)' : 'var(--fg-2)', cursor: 'pointer',
                  fontSize: 13, fontWeight: active ? 600 : 400,
                  textAlign: 'left', transition: 'background 0.15s',
                }}
              >
                <Icon style={{ width: 15, height: 15, flexShrink: 0 }} />
                <span style={{ flex: 1 }}>{s.label}</span>
                <MissingBadge count={missingIn(s.id)} size={16} />
              </button>
            );
          })}
        </nav>
      </aside>

      <main style={{ flex: 1, minWidth: 0 }}>{content}</main>
    </div>
  );
}
