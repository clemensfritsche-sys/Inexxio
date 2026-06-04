'use client';

import { useState, useEffect, useRef } from 'react';
import { User, Briefcase } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  salutation: string;
  first_name: string;
  last_name: string;
  language: string;
  is_business: boolean;
}

function buildForm(p: UserProfile): Form {
  return {
    salutation: p.salutation ?? '',
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    language: p.language ?? 'de',
    is_business: p.is_business ?? false,
  };
}

interface Props {
  profile: UserProfile;
  isEmployee: boolean;
  isCustomer: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isEmployee, isCustomer, onSave }: Props) {
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

  const { status, errorMsg, saveNow } = useAutosave(form, (v) => onSave(v as Partial<UserProfile>), 3000, resetKey);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const objectNumber = profile.object_id != null
    ? String(profile.object_id).padStart(9, '0')
    : String(profile.id);

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <User style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Mein Profil</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <Field label="Benutzernummer" value={objectNumber} readOnly hint="Eindeutige Kennnummer Ihres Kontos" />

        {isCustomer && (
          <div>
            <p style={{ fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 8 }}>Kontotyp</p>
            <div style={{ display: 'flex', borderRadius: 8, border: '1px solid #E2E8F0', overflow: 'hidden', width: 'fit-content' }}>
              {[
                { val: false, label: 'Privatkunde' },
                { val: true, label: 'Geschäftskunde' },
              ].map(({ val, label }) => (
                <button
                  key={String(val)}
                  onClick={() => set('is_business', val)}
                  style={{
                    padding: '8px 18px', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500,
                    background: form.is_business === val ? '#E51A14' : '#fff',
                    color: form.is_business === val ? '#fff' : '#374151',
                    transition: 'background 0.15s, color 0.15s',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <p style={{ fontSize: 12, color: '#94a3b8', marginTop: 6 }}>
              Geschäftskunden können Firmendaten und USt-ID hinterlegen.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SelectField
            label="Anrede"
            value={form.salutation}
            onChange={(v) => set('salutation', v)}
            options={[
              { value: '', label: 'Keine Angabe' },
              { value: 'Herr', label: 'Herr' },
              { value: 'Frau', label: 'Frau' },
              { value: 'Divers', label: 'Divers' },
            ]}
          />
          <SelectField
            label="Sprache"
            value={form.language}
            onChange={(v) => set('language', v)}
            options={[
              { value: 'de', label: 'Deutsch' },
              { value: 'en', label: 'English' },
            ]}
          />
          <Field label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)} placeholder="Max" required={!form.first_name.trim()} onEnter={saveNow} />
          <Field label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)} placeholder="Muster" required={!form.last_name.trim()} onEnter={saveNow} />
        </div>

        {isEmployee && (
          <div style={{ padding: '16px', background: '#F8FAFC', borderRadius: 10, border: '1px solid #E2E8F0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
              <Briefcase style={{ width: 13, height: 13, color: '#64748b' }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Anstellungsdaten (nur lesbar)
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Abteilung" value={profile.department ?? ''} readOnly />
              <Field label="Funktion" value={profile.job_title ?? ''} readOnly />
              <Field
                label="Eintrittsdatum"
                value={profile.employment_start_date ? new Date(profile.employment_start_date).toLocaleDateString('de-CH') : ''}
                readOnly
              />
              <Field
                label="Pensum"
                value={profile.weekly_hours ? `${profile.weekly_hours}h / Woche` : ''}
                readOnly
              />
            </div>
            <p style={{ fontSize: 12, color: '#94a3b8', margin: '12px 0 0' }}>
              Diese Angaben werden durch Ihren Administrator verwaltet.
            </p>
          </div>
        )}

        {/* AGB – read-only */}
        <div style={{ borderTop: '1px solid #F1F5F9', paddingTop: 16, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 500, color: '#0F172A', margin: 0 }}>AGB akzeptiert</p>
            <p style={{ fontSize: 13, color: '#94a3b8', margin: '2px 0 0' }}>
              {profile.terms_accepted_at
                ? `Akzeptiert am ${new Date(profile.terms_accepted_at).toLocaleDateString('de-CH')}${profile.terms_version ? ` · Version ${profile.terms_version}` : ''}`
                : 'Noch nicht akzeptiert'}
            </p>
          </div>
          <div style={{
            width: 44, height: 24, borderRadius: 12, flexShrink: 0,
            background: profile.terms_accepted_at ? '#16a34a' : '#cbd5e1',
            position: 'relative', opacity: 0.5, cursor: 'default', pointerEvents: 'none',
          }}>
            <span style={{
              position: 'absolute', top: 3,
              left: profile.terms_accepted_at ? 23 : 3,
              width: 18, height: 18, borderRadius: '50%', background: '#fff',
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            }} />
          </div>
        </div>
      </div>
    </div>
  );
}
