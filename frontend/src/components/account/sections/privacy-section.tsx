'use client';

import { useState, useEffect, useRef } from 'react';
import { Lock, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import type { UserProfile } from '@/types';
import { ToggleField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  accepts_marketing: boolean;
}

function buildForm(p: UserProfile): Form {
  return { accepts_marketing: p.accepts_marketing ?? false };
}

interface Props {
  profile: UserProfile;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function PrivacySection({ profile, onSave }: Props) {
  const [form, setForm] = useState<Form>(() => buildForm(profile));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (profile.id !== prevId.current) {
      prevId.current = profile.id;
      setForm(buildForm(profile));
      setResetKey((k) => k + 1);
    }
  }, [profile.id, profile]);

  const { status, errorMsg } = useAutosave(form, (v) => onSave(v as Partial<UserProfile>), 1000, resetKey);

  const termsDate = profile.terms_accepted_at
    ? new Date(profile.terms_accepted_at).toLocaleDateString('de-CH')
    : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Lock style={{ width: 16, height: 16, color: '#64748b' }} />
            <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Datenschutz & Marketing</h2>
          </div>
          <SaveStatusIndicator status={status} errorMsg={errorMsg} />
        </div>

        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <ToggleField
            label="Marketing-Kommunikation"
            description="Ich möchte personalisierte Angebote und Produktneuigkeiten per E-Mail erhalten"
            checked={form.accepts_marketing}
            onChange={(v) => setForm({ accepts_marketing: v })}
          />
        </div>
      </div>

      {/* Nutzungsbedingungen */}
      <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, padding: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#0F172A', margin: '0 0 4px' }}>Nutzungsbedingungen</h3>
        <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 16px' }}>
          Werden automatisch mit der ersten Anmeldung akzeptiert und können nicht abgelehnt werden.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {([
            { label: 'Allgemeine Geschäftsbedingungen (AGB)', href: '/agb' },
            { label: 'Datenschutzerklärung', href: '/datenschutz' },
          ] as const).map(({ label, href }, i, arr) => (
            <div key={href} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
              padding: '12px 0',
              borderBottom: i < arr.length - 1 ? '1px solid #F1F5F9' : 'none',
            }}>
              <div>
                <Link href={href} style={{ fontSize: 14, color: '#374151', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  {label}
                  <ExternalLink style={{ width: 12, height: 12, color: '#94a3b8', flexShrink: 0 }} />
                </Link>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '2px 0 0' }}>
                  {termsDate
                    ? `Akzeptiert am ${termsDate}${profile.terms_version ? ` · v${profile.terms_version}` : ''}`
                    : 'Noch nicht akzeptiert'}
                </p>
              </div>
              <div style={{
                width: 44, height: 24, borderRadius: 12, flexShrink: 0,
                background: termsDate ? '#16a34a' : '#cbd5e1',
                position: 'relative', opacity: 0.6, cursor: 'default', pointerEvents: 'none',
              }}>
                <span style={{
                  position: 'absolute', top: 3,
                  left: termsDate ? 23 : 3,
                  width: 18, height: 18, borderRadius: '50%', background: '#fff',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
