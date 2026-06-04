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
  date_of_birth: string;
  language: string;
  is_business: boolean;
}

function buildForm(p: UserProfile): Form {
  return {
    salutation: p.salutation ?? '',
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
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

  const { status, errorMsg } = useAutosave(form, (v) => onSave(v as Partial<UserProfile>), 3000, resetKey);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const objectNumber = profile.object_id != null
    ? String(profile.object_id).padStart(9, '0')
    : String(profile.id);

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <User style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Mein Profil</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Benutzernummer (read-only) */}
        <Field label="Benutzernummer" value={objectNumber} readOnly hint="Eindeutige Kennnummer Ihres Kontos" />

        {/* B2B / B2C toggle for customers */}
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

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
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
          <Field label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)} placeholder="Max" />
          <Field label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)} placeholder="Muster" />
          {isCustomer && (
            <Field label="Geburtsdatum" value={form.date_of_birth} onChange={(v) => set('date_of_birth', v)} type="date" />
          )}
        </div>

        {/* Read-only employment block for employees */}
        {isEmployee && (
          <div style={{ padding: '16px', background: '#F8FAFC', borderRadius: 10, border: '1px solid #E2E8F0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
              <Briefcase style={{ width: 13, height: 13, color: '#64748b' }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Anstellungsdaten (nur lesbar)
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
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
      </div>
    </div>
  );
}
