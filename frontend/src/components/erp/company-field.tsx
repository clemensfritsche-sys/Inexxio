'use client';

import { useEffect, useRef, useState } from 'react';
import { Building2, Plus } from 'lucide-react';
import { api } from '@/lib/api';
import { legalForms } from '@/lib/legal-forms';
import { Field as AField } from '@/components/account/field';
import { ObjectSelect } from '@/components/erp/object-select';
import { ErrorText } from '@/components/erp/fields';
import { AddressField, type Address } from '@/components/erp/address-field';
import { COMPANY_COUNTRIES, splitStreet, taxIds } from '@/components/erp/organization-detail';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';
import type { CompanyCard, CompanyRef, CompanySettings, NewCompany } from '@/types';

/**
 * ►►► **Die Firma einer Person – gewählt, nicht abgetippt** (CRM Schritt 1). ◄◄◄
 *
 * Die Firma ist ein eigener Datensatz. Die Person **wählt** sie (Vorschläge ab zwei
 * Zeichen: Nummer, Name oder UID) oder **nennt** eine neue – dann sucht der Server zuerst
 * nach einer eindeutig gleichen (gleiche UID, oder gleicher Name **und** Rechtsform) und
 * legt nur sonst eine an (`sites.resolve_for_person`).
 *
 * **Ihre Angaben pflegt man darunter** (`CompanyEditor`) – gespeichert am Datensatz der
 * Firma, nie als Kopie an der Person.
 *
 * EIN Bauteil für Konto und ERP: wer speichert, sagt der Aufrufer (`onLink`/`onCreate`).
 */
export function CompanyField({ company, readOnly, country, onLink, onCreate }: {
  company: CompanyRef | null | undefined;
  readOnly?: boolean;
  /** Land der Person – für die Vorschläge der Rechtsform. */
  country?: string | null;
  onLink: (objectId: number | null) => Promise<unknown>;
  onCreate: (company: NewCompany) => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<NewCompany>({ company_name: '', legal_form: '', uid_number: '' });
  const forms = legalForms(country ?? 'CH');

  async function run(act: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await act();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Speichern nicht möglich.');
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    const ok = await run(() => onCreate({
      company_name: draft.company_name.trim(),
      legal_form: draft.legal_form.trim(),
      uid_number: draft.uid_number?.trim() || null,
    }));
    if (ok) {
      setAdding(false);
      setDraft({ company_name: '', legal_form: '', uid_number: '' });
    }
  }

  const ready = !!draft.company_name.trim() && !!draft.legal_form.trim();
  const facts = company
    ? [company.uid_number || company.vat_number, company.city].filter(Boolean).join(' · ')
    : '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <ObjectSelect<{ object_id: number; name: string }>
        label="Firma" value={company?.object_id ?? null} disabled={readOnly || busy}
        kind="company" scanLabel="Firma"
        emptyOption="Keine – Privatperson"
        selected={company ? { object_id: company.object_id, name: company.legal_name } : null}
        find={async (q) => (await api.searchCompanies(q))
          .map((c) => ({ object_id: c.object_id, name: c.legal_name }))}
        onChange={(id) => { void run(() => onLink(id)); }} />

      {company && facts && (
        <span className="text-xs text-fg-3 ix-tnum">{facts}</span>
      )}

      {!readOnly && !adding && (
        <button type="button" onClick={() => setAdding(true)}
          className="self-start inline-flex items-center gap-1.5 text-xs text-accent hover:underline">
          <Plus size={13} /> Firma nicht in der Liste – neu erfassen
        </button>
      )}

      {!readOnly && adding && (
        <div className="rounded-ds-md border border-border-1 p-3 flex flex-col gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-fg-2">
            <Building2 size={13} /> Neue Firma
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <AField label="Firmenname" value={draft.company_name} required
              onChange={(v) => setDraft((d) => ({ ...d, company_name: v }))} placeholder="Muster" />
            <div>
              <AField label="Rechtsform" value={draft.legal_form} required list="company-field-forms"
                onChange={(v) => setDraft((d) => ({ ...d, legal_form: v }))} placeholder={forms[0] ?? 'AG'} />
              <datalist id="company-field-forms">
                {forms.map((f) => <option key={f} value={f} />)}
              </datalist>
            </div>
            <div className="sm:col-span-2">
              <AField label="UID-Nummer" value={draft.uid_number ?? ''}
                onChange={(v) => setDraft((d) => ({ ...d, uid_number: v }))} placeholder="CHE-123.456.789" />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!ready || busy}
              title={ready ? undefined : 'Firmenname und Rechtsform fehlen.'} onClick={() => void create()}>
              Firma übernehmen
            </button>
            <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={busy}
              onClick={() => { setAdding(false); setError(''); }}>
              Abbrechen
            </button>
          </div>
        </div>
      )}

      {error && <ErrorText msg={error} />}
    </div>
  );
}

/** Das Formular der Firma, so weit es den Rechnungsweg betrifft. */
interface CompanyForm {
  company_name: string; legal_form: string; uid: string; vat_number: string;
  street: string; street_number: string; zip: string; city: string; country: string;
  email: string;
}

function companyForm(c: CompanyCard): CompanyForm {
  return {
    company_name: c.company_name ?? '', legal_form: c.legal_form ?? '',
    uid: c.uid_number ?? '', vat_number: c.vat_number ?? '',
    street: c.street ?? '', street_number: c.street_nr ?? '',
    zip: c.zip_code ?? '', city: c.city ?? '', country: c.country || 'Schweiz',
    email: c.email ?? '',
  };
}

/**
 * ►►► **Mit Firma geht die Rechnung an die FIRMA – und ihre Angaben stehen hier**
 * (`voucher._company_billing`). ◄◄◄
 *
 * Firmenname, Rechtsform, UID, Rechnungsadresse und Rechnungs-E-Mail **sind** der
 * Rechnungsweg dieser Person – also stehen sie dort, wo man ihn sucht, statt hinter
 * einem Sprung zum Firmen-Datensatz. **Gespeichert wird am Datensatz der Firma**
 * (`onSave`): es gibt sie nur einmal, und sie gilt für alle Personen dieser Firma. Eine
 * Kopie an der Person wäre die zweite Wahrheit, und eine neue Firma je Änderung die dritte.
 *
 * **Eine unserer Gesellschaften ändert nur ein Admin** – dann steht alles gesperrt da
 * (`readOnly`); die Regel selbst steht im Dienst (`sites.apply_update`).
 */
export function CompanyEditor({ company, readOnly, mapsKey, onSave }: {
  company: CompanyCard;
  readOnly?: boolean;
  mapsKey?: string | null;
  onSave: (data: Partial<CompanySettings>) => Promise<unknown>;
}) {
  const [form, setForm] = useState<CompanyForm>(() => companyForm(company));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef(company.object_id);

  // Nur beim **Wechsel** der Firma neu aufbauen – sonst klobbert ein Auto-Save die Eingabe.
  useEffect(() => {
    if (company.object_id === prevId.current) return;
    prevId.current = company.object_id;
    setForm(companyForm(company));
    setResetKey((k) => k + 1);
  }, [company]);

  const { status, errorMsg, saveNow } = useAutosave(form, async (v) => {
    // Ein leerer Name ist kein speicherbarer Zustand – das Feld markiert ihn.
    if (readOnly || !v.company_name.trim()) return;
    await onSave({
      company_name: v.company_name.trim(), legal_form: v.legal_form.trim(),
      uid: nn(v.uid), vat_number: nn(v.vat_number),
      street: v.street, street_number: nn(v.street_number),
      zip: v.zip, city: v.city, country: v.country, email: v.email.trim(),
    });
  }, 2500, resetKey);

  const str = (k: keyof CompanyForm) => (val: string) => setForm((p) => ({ ...p, [k]: val }));
  const ids = taxIds(form.country);
  const forms = legalForms(form.country);
  const address: Address = {
    street: [form.street, form.street_number].filter(Boolean).join(' '),
    zip: form.zip, city: form.city, country: form.country,
  };
  function applyAddress(a: Address) {
    const [street, nr] = splitStreet(a.street);
    setForm((p) => ({ ...p, street, street_number: nr, zip: a.zip, city: a.city, country: a.country }));
  }

  return (
    <fieldset disabled={readOnly} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}
      className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-fg-3">
          {readOnly ? 'Eine unserer Gesellschaften – ändern darf sie nur ein Admin.'
            : 'Rechnungsempfänger · gilt für alle Personen dieser Firma'}
        </span>
        {!readOnly && <SaveStatusIndicator status={status} errorMsg={errorMsg} />}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <AField label="Firmenname" value={form.company_name} onChange={str('company_name')}
          required onEnter={saveNow} />
        <div>
          <AField label="Rechtsform" value={form.legal_form} onChange={str('legal_form')} required
            list="company-editor-forms" placeholder={forms[0] ?? 'AG'} onEnter={saveNow} />
          <datalist id="company-editor-forms">
            {forms.map((f) => <option key={f} value={f} />)}
          </datalist>
        </div>
        <AField label={ids.uid.label} value={form.uid} onChange={str('uid')}
          placeholder={ids.uid.ph} onEnter={saveNow} />
        {ids.vat && (
          <AField label={ids.vat.label} value={form.vat_number} onChange={str('vat_number')}
            placeholder={ids.vat.ph} onEnter={saveNow} />
        )}
      </div>
      <AddressField value={address} onChange={applyAddress} apiKey={mapsKey}
        countryOptions={COMPANY_COUNTRIES} label="Rechnungsadresse" />
      <AField label="Rechnungs-E-Mail" value={form.email} onChange={str('email')} type="email"
        placeholder="rechnung@firma.ch" onEnter={saveNow} />
    </fieldset>
  );
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/** Die gespeicherte Firma (Antwort von `updateCompany`) in der Form, die an der Person steht. */
export function cardOf(s: CompanySettings): CompanyCard {
  return {
    object_id: s.object_id as number, company_name: s.company_name,
    legal_form: s.legal_form ?? '', legal_name: s.legal_name ?? s.company_name,
    uid_number: s.uid ?? null, vat_number: s.vat_number ?? null, is_own: !!s.is_own,
    street: s.street ?? null, street_nr: s.street_number ?? null, zip_code: s.zip ?? null,
    city: s.city ?? null, country: s.country ?? null, email: s.email ?? null,
  };
}
