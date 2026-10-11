'use client';

import { useState } from 'react';
import { Building2, Plus } from 'lucide-react';
import { api } from '@/lib/api';
import { legalForms } from '@/lib/legal-forms';
import { Field as AField } from '@/components/account/field';
import { ObjectSelect } from '@/components/erp/object-select';
import { ErrorText } from '@/components/erp/fields';
import type { CompanyRef, NewCompany } from '@/types';

/**
 * ►►► **Die Firma einer Person – gewählt, nicht abgetippt** (CRM Schritt 1). ◄◄◄
 *
 * Die Firma ist ein eigener Datensatz. Die Person **wählt** sie (Vorschläge ab zwei
 * Zeichen: Nummer, Name oder UID) oder **nennt** eine neue – dann sucht der Server zuerst
 * nach einer eindeutig gleichen (gleiche UID, oder gleicher Name **und** Rechtsform) und
 * legt nur sonst eine an (`sites.resolve_for_person`).
 *
 * **Die Angaben der Firma ändert man hier nicht** – an ihrem eigenen Datensatz. Sonst
 * änderte jeder Kunde die Firmendaten seiner Kollegen; hier steht sie als Auskunft.
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
