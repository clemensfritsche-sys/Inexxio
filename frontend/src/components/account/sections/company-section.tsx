'use client';

import { useState, useEffect, useRef } from 'react';
import { Building2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, ToggleField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  company_name: string;
  uid_number: string;
  vat_number: string;
  vat_registered: boolean;
  trade_register_nr: string;
  trade_register_canton: string;
  company_website: string;
  company_billing_email: string;
}

function buildForm(p: UserProfile): Form {
  return {
    company_name: p.company_name ?? '',
    uid_number: p.uid_number ?? '',
    vat_number: p.vat_number ?? '',
    vat_registered: p.vat_registered ?? false,
    trade_register_nr: p.trade_register_nr ?? '',
    trade_register_canton: p.trade_register_canton ?? '',
    company_website: p.company_website ?? '',
    company_billing_email: p.company_billing_email ?? '',
  };
}

interface Props {
  profile: UserProfile;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function CompanySection({ profile, onSave }: Props) {
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

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Building2 style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Firmendaten</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Firmenname" value={form.company_name} onChange={(v) => set('company_name', v)} placeholder="Muster AG" required={!form.company_name.trim()} onEnter={saveNow} />
          <Field label="UID-Nummer" value={form.uid_number} onChange={(v) => set('uid_number', v)} placeholder="CHE-123.456.789" hint="Format: CHE-xxx.xxx.xxx" required={!form.uid_number.trim()} onEnter={saveNow} />
          <Field label="MWST-Nummer" value={form.vat_number} onChange={(v) => set('vat_number', v)} placeholder="CHE-123.456.789 MWST" onEnter={saveNow} />
          <Field label="Handelsregister-Nr." value={form.trade_register_nr} onChange={(v) => set('trade_register_nr', v)} placeholder="CH-020.3.000.000-0" onEnter={saveNow} />
          <Field label="Kanton HR" value={form.trade_register_canton} onChange={(v) => set('trade_register_canton', v)} placeholder="ZH" onEnter={saveNow} />
          <Field label="Website" value={form.company_website} onChange={(v) => set('company_website', v)} placeholder="https://www.firma.ch" type="url" onEnter={saveNow} />
          <Field label="Rechnungs-E-Mail" value={form.company_billing_email} onChange={(v) => set('company_billing_email', v)} placeholder="buchhaltung@firma.ch" type="email" onEnter={saveNow} />
        </div>

        <div style={{ paddingTop: 4 }}>
          <ToggleField
            label="MWST-pflichtig"
            description="Aktivieren wenn Ihr Unternehmen mehrwertsteuerpflichtig ist"
            checked={form.vat_registered}
            onChange={(v) => set('vat_registered', v)}
          />
        </div>
      </div>
    </div>
  );
}
