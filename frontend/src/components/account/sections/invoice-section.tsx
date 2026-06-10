'use client';

import { useState, useEffect, useRef } from 'react';
import { FileText, Copy } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  invoice_same_as_shipping: boolean;
  invoice_company: string;
  invoice_first_name: string;
  invoice_last_name: string;
  invoice_address_line1: string;
  invoice_address_line2: string;
  invoice_postal_code: string;
  invoice_city: string;
  invoice_country: string;
  invoice_email: string;
}

function copyFromAddress(p: UserProfile): Partial<Form> {
  return {
    invoice_first_name: p.first_name ?? '',
    invoice_last_name: p.last_name ?? '',
    invoice_address_line1: p.address_line1 ?? '',
    invoice_address_line2: p.address_line2 ?? '',
    invoice_city: p.city ?? '',
    invoice_postal_code: p.postal_code ?? '',
    invoice_country: p.country ?? 'CH',
  };
}

function buildForm(p: UserProfile): Form {
  const sameAsShipping = p.invoice_same_as_shipping ?? true;
  const base: Form = {
    invoice_same_as_shipping: sameAsShipping,
    invoice_company: p.invoice_company ?? '',
    invoice_first_name: p.invoice_first_name ?? '',
    invoice_last_name: p.invoice_last_name ?? '',
    invoice_address_line1: p.invoice_address_line1 ?? '',
    invoice_address_line2: p.invoice_address_line2 ?? '',
    invoice_postal_code: p.invoice_postal_code ?? '',
    invoice_city: p.invoice_city ?? '',
    invoice_country: p.invoice_country ?? 'CH',
    invoice_email: p.invoice_email ?? '',
  };
  if (sameAsShipping) {
    return { ...base, ...copyFromAddress(p) };
  }
  return base;
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
  isBusiness: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function InvoiceSection({ profile, isBusiness, onSave }: Props) {
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

  // Keep invoice fields in sync with the Adresse section when same-as is on
  const { first_name, last_name, address_line1, address_line2, city, postal_code, country } = profile;
  useEffect(() => {
    setForm((prev) => {
      if (!prev.invoice_same_as_shipping) return prev;
      const patch: Partial<Form> = {
        invoice_first_name: first_name ?? '',
        invoice_last_name: last_name ?? '',
        invoice_address_line1: address_line1 ?? '',
        invoice_address_line2: address_line2 ?? '',
        invoice_city: city ?? '',
        invoice_postal_code: postal_code ?? '',
        invoice_country: country ?? 'CH',
      };
      const changed = (Object.keys(patch) as (keyof Form)[]).some((k) => prev[k] !== patch[k]);
      return changed ? { ...prev, ...patch } : prev;
    });
  }, [first_name, last_name, address_line1, address_line2, city, postal_code, country]);

  const { status, errorMsg, saveNow } = useAutosave(form, (v) => onSave(v as Partial<UserProfile>), 3000, resetKey);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSameAsShipping(on: boolean) {
    setForm((prev) => ({
      ...prev,
      invoice_same_as_shipping: on,
      ...(on ? copyFromAddress(profile) : {}),
    }));
  }

  const sameAsShipping = form.invoice_same_as_shipping;
  const disabled = sameAsShipping;

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
        {/* Same-as-shipping toggle */}
        <button
          onClick={() => handleSameAsShipping(!sameAsShipping)}
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px', borderRadius: 8,
            border: `1px solid ${sameAsShipping ? '#E51A14' : '#E2E8F0'}`,
            background: sameAsShipping ? '#FEF2F2' : '#F8FAFC',
            cursor: 'pointer', width: '100%', textAlign: 'left',
          }}
        >
          <Copy style={{ width: 14, height: 14, color: sameAsShipping ? '#E51A14' : '#64748b', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: sameAsShipping ? '#E51A14' : '#374151', margin: 0 }}>
              Gleich wie Lieferadresse
            </p>
            <p style={{ fontSize: 12, color: '#94a3b8', margin: '1px 0 0' }}>
              {sameAsShipping ? 'Rechnungsadresse von Lieferadresse übernommen' : 'Felder automatisch befüllen'}
            </p>
          </div>
          <div style={{
            width: 18, height: 18, borderRadius: 4, border: `2px solid ${sameAsShipping ? '#E51A14' : '#cbd5e1'}`,
            background: sameAsShipping ? '#E51A14' : 'transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            {sameAsShipping && <span style={{ color: '#fff', fontSize: 11, fontWeight: 800 }}>✓</span>}
          </div>
        </button>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {isBusiness && (
            <div className="col-span-2">
              <Field label="Firmenname" value={form.invoice_company} onChange={(v) => set('invoice_company', v)} readOnly={disabled} onEnter={saveNow} />
            </div>
          )}
          <Field label="Vorname" value={form.invoice_first_name} onChange={(v) => set('invoice_first_name', v)} readOnly={disabled} required={!disabled && !form.invoice_first_name.trim()} onEnter={saveNow} />
          <Field label="Nachname" value={form.invoice_last_name} onChange={(v) => set('invoice_last_name', v)} readOnly={disabled} required={!disabled && !form.invoice_last_name.trim()} onEnter={saveNow} />
          <div className="col-span-2">
            <Field label="Strasse und Hausnummer" value={form.invoice_address_line1} onChange={(v) => set('invoice_address_line1', v)} readOnly={disabled} required={!disabled && !form.invoice_address_line1.trim()} onEnter={saveNow} />
          </div>
          <div className="col-span-2">
            <Field label="Adresszusatz" value={form.invoice_address_line2} onChange={(v) => set('invoice_address_line2', v)} placeholder="c/o, Postfach…" readOnly={disabled} onEnter={saveNow} />
          </div>
          <Field label="PLZ" value={form.invoice_postal_code} onChange={(v) => set('invoice_postal_code', v)} readOnly={disabled} required={!disabled && !form.invoice_postal_code.trim()} onEnter={saveNow} />
          <Field label="Ort" value={form.invoice_city} onChange={(v) => set('invoice_city', v)} readOnly={disabled} required={!disabled && !form.invoice_city.trim()} onEnter={saveNow} />
          <SelectField label="Land" value={form.invoice_country} onChange={(v) => set('invoice_country', v)} options={COUNTRIES} />
          <Field label="Rechnungs-E-Mail" value={form.invoice_email} onChange={(v) => set('invoice_email', v)} type="email" placeholder="buchhaltung@firma.ch" onEnter={saveNow} />
        </div>
      </div>
    </div>
  );
}
