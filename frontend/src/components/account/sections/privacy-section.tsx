'use client';

import { useState, useEffect, useRef } from 'react';
import { Lock } from 'lucide-react';
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

      {/* AGB info */}
      <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, padding: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#0F172A', margin: '0 0 12px' }}>Nutzungsbedingungen</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #F1F5F9' }}>
            <span style={{ fontSize: 14, color: '#374151' }}>AGB akzeptiert</span>
            <span style={{ fontSize: 14, color: termsDate ? '#16a34a' : '#94a3b8' }}>
              {termsDate ?? 'Noch nicht akzeptiert'}
              {profile.terms_version ? ` (v${profile.terms_version})` : ''}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 16, paddingTop: 8 }}>
            <Link href="/agb" style={{ fontSize: 13, color: '#E51A14', textDecoration: 'none' }}>AGB ansehen →</Link>
            <Link href="/datenschutz" style={{ fontSize: 13, color: '#E51A14', textDecoration: 'none' }}>Datenschutzerklärung →</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
