'use client';

import { useState, useEffect, useRef } from 'react';
import { User, Briefcase, Building2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  company_name: string;
  uid_number: string;
  company_billing_email: string;
}

function buildForm(p: UserProfile): Form {
  return {
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    company_name: p.company_name ?? '',
    uid_number: p.uid_number ?? '',
    company_billing_email: p.company_billing_email ?? '',
  };
}

interface Props {
  profile: UserProfile;
  isEmployee: boolean;
  isSupplier: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isEmployee, isSupplier, onSave }: Props) {
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

  const { status, errorMsg, saveNow } = useAutosave(
    form,
    (v) => {
      const data = { ...v } as Partial<UserProfile>;
      if (!isSupplier) {
        delete data.company_name;
        delete data.uid_number;
        delete data.company_billing_email;
      }
      return onSave(data);
    },
    3000,
    resetKey,
  );

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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)} placeholder="Max" required={!form.first_name.trim()} onEnter={saveNow} />
          <Field label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)} placeholder="Muster" required={!form.last_name.trim()} onEnter={saveNow} />
          <Field label="Geburtsdatum" value={form.date_of_birth} onChange={(v) => set('date_of_birth', v)} type="date" onEnter={saveNow} />
        </div>

        {isSupplier && (
          <div style={{ padding: '16px', background: '#F8FAFC', borderRadius: 10, border: '1px solid #E2E8F0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
              <Building2 style={{ width: 13, height: 13, color: '#64748b' }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Firmendaten
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Firmenname" value={form.company_name} onChange={(v) => set('company_name', v)} placeholder="Muster AG" required={!form.company_name.trim()} onEnter={saveNow} />
              <Field label="UID-Nummer" value={form.uid_number} onChange={(v) => set('uid_number', v)} placeholder="CHE-123.456.789" hint="Format: CHE-xxx.xxx.xxx" required={!form.uid_number.trim()} onEnter={saveNow} />
              <div className="col-span-2" style={{ display: 'flex' }}>
                <div style={{ flex: 1 }}>
                  <Field label="Rechnungs-E-Mail" value={form.company_billing_email} onChange={(v) => set('company_billing_email', v)} placeholder="buchhaltung@firma.ch" type="email" onEnter={saveNow} />
                </div>
              </div>
            </div>
          </div>
        )}

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
