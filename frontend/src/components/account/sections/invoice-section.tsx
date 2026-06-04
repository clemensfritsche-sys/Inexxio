'use client';

import { useState, useEffect, useRef } from 'react';
import { FileText } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  invoice_company: string;
  invoice_first_name: string;
  invoice_last_name: string;
  invoice_address_line1: string;
  invoice_address_line2: string;
  invoice_postal_code: string;
  invoice_city: string;
  invoice_country: string;
  invoice_vat_id: string;
  invoice_email: string;
}

function buildForm(p: UserProfile): Form {
  return {
    invoice_company: p.invoice_company ?? '',
    invoice_first_name: p.invoice_first_name ?? '',
    invoice_last_name: p.invoice_last_name ?? '',
    invoice_address_line1: p.invoice_address_line1 ?? '',
    invoice_address_line2: p.invoice_address_line2 ?? '',
    invoice_postal_code: p.invoice_postal_code ?? '',
    invoice_city: p.invoice_city ?? '',
    invoice_country: p.invoice_country ?? 'CH',
    invoice_vat_id: p.invoice_vat_id ?? '',
    invoice_email: p.invoice_email ?? '',
  };
}

const COUNTRIES = [
  { value: 'CH', label: 'Schweiz' },
  { value: 'DE', label: 'Deutschland' },
  { value: 'AT', label: 'Österreich' },
  { value: 'FR', label: 'Frankreich' },
  { value: 'IT', label: 'Italien' },
  { value: 'LI', label: 'Liechtenstein' },
];

interface Props {
  profile: UserProfile;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function InvoiceSection({ profile, onSave }: Props) {
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

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Rechnungsadresse</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Firmenname (optional)" value={form.invoice_company} onChange={(v) => set('invoice_company', v)} placeholder="Für B2B-Rechnungen" />
          </div>
          <Field label="Vorname" value={form.invoice_first_name} onChange={(v) => set('invoice_first_name', v)} />
          <Field label="Nachname" value={form.invoice_last_name} onChange={(v) => set('invoice_last_name', v)} />
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Strasse und Hausnummer" value={form.invoice_address_line1} onChange={(v) => set('invoice_address_line1', v)} />
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Adresszusatz" value={form.invoice_address_line2} onChange={(v) => set('invoice_address_line2', v)} placeholder="c/o, Postfach…" />
          </div>
          <Field label="PLZ" value={form.invoice_postal_code} onChange={(v) => set('invoice_postal_code', v)} />
          <Field label="Ort" value={form.invoice_city} onChange={(v) => set('invoice_city', v)} />
          <SelectField label="Land" value={form.invoice_country} onChange={(v) => set('invoice_country', v)} options={COUNTRIES} />
          <Field label="Rechnungs-E-Mail" value={form.invoice_email} onChange={(v) => set('invoice_email', v)} type="email" placeholder="buchhaltung@firma.ch" />
          <Field label="USt-ID / MWST-Nr." value={form.invoice_vat_id} onChange={(v) => set('invoice_vat_id', v)} placeholder="CHE-xxx.xxx.xxx MWST" />
        </div>
      </div>
    </div>
  );
}
