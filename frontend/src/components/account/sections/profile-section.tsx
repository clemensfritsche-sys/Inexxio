'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { User, Briefcase, Globe } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  first_name: string;
  last_name: string;
  language: string;
}

function buildForm(p: UserProfile): Form {
  return {
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    language: p.language ?? 'de',
  };
}

interface Props {
  profile: UserProfile;
  isEmployee: boolean;
  isCustomer: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isEmployee, isCustomer: _isCustomer, onSave }: Props) {
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

  const detectedLang = useMemo(() => {
    if (typeof window === 'undefined') return null;
    const tag = navigator.language?.split('-')[0]?.toLowerCase();
    return tag === 'de' || tag === 'en' ? tag : null;
  }, []);

  const langSuggestion = detectedLang !== null && detectedLang !== form.language ? detectedLang : null;
  const langLabel = (l: string) => (l === 'de' ? 'Deutsch' : 'English');

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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)} placeholder="Max" required={!form.first_name.trim()} onEnter={saveNow} />
          <Field label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)} placeholder="Muster" required={!form.last_name.trim()} onEnter={saveNow} />
          <div>
            <SelectField
              label="Sprache"
              value={form.language}
              onChange={(v) => set('language', v)}
              options={[
                { value: 'de', label: 'Deutsch' },
                { value: 'en', label: 'English' },
              ]}
            />
            {langSuggestion && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                <Globe style={{ width: 11, height: 11, color: '#94a3b8', flexShrink: 0 }} />
                <span style={{ fontSize: 11, color: '#64748b' }}>
                  Browser: {langLabel(langSuggestion)}
                </span>
                <button
                  type="button"
                  onClick={() => set('language', langSuggestion)}
                  style={{
                    fontSize: 11, color: '#2563eb', background: 'none', border: 'none',
                    padding: '0 4px', cursor: 'pointer', fontWeight: 600,
                  }}
                >
                  Übernehmen
                </button>
              </div>
            )}
          </div>
          <div />
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

      </div>
    </div>
  );
}
