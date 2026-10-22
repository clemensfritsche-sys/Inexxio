'use client';

/**
 * **Mein Konto – EINE ruhige Seite** (Entwurf «Mein Konto» A, Oktober 2026).
 *
 * Kopf wie die Website (`StageHero`): das grosse Wort «Mein Konto», davor die Person, darunter
 * Name, E-Mail und Benutzernummer und – solange etwas fehlt – eine Glas-Pille, die genau das
 * Erste nennt, was fehlt. Darunter eine Glas-Leiste mit Sprungmarken, dann die Abschnitte
 * (Person · Adressen · Firma · Newsletter · Sicherheit). Vorher: zwei Reiter, Seitenleiste
 * und ein eigener Handy-Zweig – jetzt eine Anordnung, die das CSS schmal stapelt.
 */

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { isStaff } from '@/lib/record-status';
import { useProfileCompletion } from '@/hooks/useProfileCompletion';
import { ProfileSection } from './sections/profile-section';
import { SecuritySection } from './sections/security-section';

interface Props {
  profile: UserProfile | null;
  isLoading: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

const NAV = [
  { id: 'person', label: 'Person' },
  { id: 'adressen', label: 'Adressen' },
  { id: 'firma', label: 'Firma' },
  { id: 'newsletter', label: 'Newsletter' },
  { id: 'sicherheit', label: 'Sicherheit' },
];

/** Profilbild oder Initialen auf Rot, im Ring. */
function Avatar({ profile, name }: { profile: UserProfile; name: string }) {
  const initials = name ? name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2) : '?';
  return (
    <div className="kt-av">
      <span>
        {profile.photo_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={profile.photo_url} alt={name} />
          : initials}
      </span>
    </div>
  );
}

/** Welcher Abschnitt gerade oben steht – die Leiste zeigt ihn als weisse Pille. */
function useActiveSection(ready: boolean): string {
  const [active, setActive] = useState(NAV[0].id);
  useEffect(() => {
    const seen = new Map<string, boolean>();
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) seen.set(e.target.id, e.isIntersecting);
      const first = NAV.find((n) => seen.get(n.id));
      if (first) setActive(first.id);
    }, { rootMargin: '-40% 0px -55% 0px' });
    for (const n of NAV) {
      const el = document.getElementById(n.id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, [ready]);
  return active;
}

export function AccountShell({ profile, isLoading, onSave }: Props) {
  const completion = useProfileCompletion(profile);
  const active = useActiveSection(!!profile);

  if (isLoading || !profile) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        {isLoading && <Loader2 style={{ width: 28, height: 28, color: 'var(--inexxio-red)', animation: 'ix-spin 0.7s linear infinite' }} />}
      </div>
    );
  }

  const name = userDisplayName(profile);
  const number = profile.object_id != null ? String(profile.object_id).padStart(9, '0').replace(/(\d{3})(?=\d)/g, '$1 ') : '';
  const next = completion.missing[0];
  const tone = completion.percentage === 100 ? 'var(--success)' : 'var(--fg-1)';

  return (
    <div className="kt">
      <header className="kt-hero">
        <span className="kt-word" aria-hidden>Mein Konto</span>
        <Avatar profile={profile} name={name} />
        <h1>{name || 'Mein Konto'}</h1>
        <p className="kt-meta">
          <span>{profile.email}</span>
          {number && <> · <span>Benutzernummer <b>{number}</b></span></>}
        </p>
        {next && (
          <p className="kt-todo">
            <span className="kt-ring" aria-hidden
              style={{ background: `conic-gradient(${tone} 0 ${completion.percentage}%, var(--border-1) ${completion.percentage}% 100%)` }} />
            Profil zu {completion.percentage} % vollständig – <a href={`#${next.anchor}`}>{next.label} ergänzen</a>
          </p>
        )}
      </header>

      <nav className="kt-nav" aria-label="Konto">
        <div>
          {NAV.map((n) => (
            <a key={n.id} href={`#${n.id}`} aria-current={active === n.id ? 'true' : undefined}>{n.label}</a>
          ))}
        </div>
      </nav>

      <div className="kt-wrap">
        {/* Personal (Admin wie Mitarbeiter) sieht seine Anstellung und ändert seine
            Gesellschaft nicht selbst – dieselbe Frage wie überall: `isStaff`. */}
        <ProfileSection profile={profile} onSave={onSave} isStaff={isStaff(profile.role)} />
        <SecuritySection profile={profile} />
      </div>
    </div>
  );
}
