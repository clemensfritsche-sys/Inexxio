'use client';

import { useState } from 'react';
import { Building2, Plus, Unlink } from 'lucide-react';
import { api } from '@/lib/api';
import { legalForms } from '@/lib/legal-forms';
import { Field as AField } from '@/components/account/field';
import { ObjectSelect } from '@/components/erp/object-select';
import { ErrorText } from '@/components/erp/fields';
import type { CompanyRef, NewCompany } from '@/types';

/**
 * ►►► **Die Firma einer Person – GENANNT, nicht gesucht** (CRM). ◄◄◄
 *
 * Es bestellt immer eine Person; die Firma ist höchstens der Rechnungsempfänger «im Namen
 * von». Bei uns ist eine fremde Firma nur ihre **Identität** – Name, Rechtsform, UID –,
 * die Anschriften gehören der Person (ihr Adressbuch).
 *
 * **Eine Person nennt ihre Firma**: die UID, sonst Name und Rechtsform. Der Server
 * erkennt sie (gleiche UID · ohne UID gleicher Name und gleiche Rechtsform) oder legt sie
 * an (`sites.resolve`) – jeder darf eine Firma anlegen, und eine Dublette ist trotzdem
 * unmöglich (Unique-Index). **Eine Liste aller Firmen sieht nur das Personal** (`search`):
 * die Kundenliste ist nichts, was ein Kunde durchblättert.
 *
 * EIN Bauteil für Konto und ERP: wer speichert, sagt der Aufrufer (`onLink`/`onCreate`).
 * **Neu nennen gibt es nur ohne `search`** (Konto): das Personal legt eine Firma über den
 * regulären Weg an («+» im Feed) und ordnet sie hier zu (Testnotiz #1214).
 */
export function CompanyField({ company, readOnly, country, search, onLink, onCreate }: {
  company: CompanyRef | null | undefined;
  readOnly?: boolean;
  /** Land der Person – für die Vorschläge der Rechtsform. */
  country?: string | null;
  /** Nur das Personal wählt aus den bestehenden Firmen. */
  search?: boolean;
  onLink: (objectId: number | null) => Promise<unknown>;
  /** Nur im Konto – im ERP entsteht eine Firma über «+» im Feed. */
  onCreate?: (company: NewCompany) => Promise<unknown>;
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
    if (!onCreate) return;
    const ok = await run(() => onCreate({
      company_name: (draft.company_name ?? '').trim(),
      legal_form: (draft.legal_form ?? '').trim(),
      uid_number: draft.uid_number?.trim() || null,
    }));
    if (ok) {
      setAdding(false);
      setDraft({ company_name: '', legal_form: '', uid_number: '' });
    }
  }

  // **Die UID genügt** – kennt der Server sie, zählt der Name nicht; kennt er sie nicht,
  // sagt er es, und dann gehören Name und Rechtsform dazu.
  const ready = !!draft.uid_number?.trim()
    || (!!draft.company_name?.trim() && !!draft.legal_form?.trim());

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {search ? (
        <ObjectSelect<{ object_id: number; name: string }>
          label="Firma" value={company?.object_id ?? null} disabled={readOnly || busy}
          kind="company" scanLabel="Firma"
          emptyOption="Keine – Privatperson"
          selected={company ? { object_id: company.object_id, name: company.legal_name } : null}
          find={async (q) => (await api.searchCompanies(q))
            .map((c) => ({ object_id: c.object_id, name: c.legal_name }))}
          onChange={(id) => { void run(() => onLink(id)); }} />
      ) : (
        <Current company={company} busy={busy} readOnly={readOnly}
          onUnlink={() => { void run(() => onLink(null)); }} />
      )}

      {search && company?.uid_number && (
        <span className="text-xs text-fg-3 ix-tnum">{company.uid_number}</span>
      )}

      {!readOnly && !adding && onCreate && !company && (
        <button type="button" onClick={() => setAdding(true)}
          className="self-start inline-flex items-center gap-1.5 text-xs text-accent hover:underline">
          <Plus size={13} /> Firma angeben
        </button>
      )}

      {!readOnly && adding && onCreate && (
        <div className="rounded-ds-md border border-border-1 p-3 flex flex-col gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-fg-2">
            <Building2 size={13} /> Firma
          </span>
          <AField label="UID" value={draft.uid_number ?? ''}
            onChange={(v) => setDraft((d) => ({ ...d, uid_number: v }))}
            placeholder="CHE-123.456.788" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <AField label="Firmenname" value={draft.company_name ?? ''}
              onChange={(v) => setDraft((d) => ({ ...d, company_name: v }))} placeholder="Muster" />
            <div>
              <AField label="Rechtsform" value={draft.legal_form ?? ''} list="company-field-forms"
                onChange={(v) => setDraft((d) => ({ ...d, legal_form: v }))} placeholder={forms[0] ?? 'AG'} />
              <datalist id="company-field-forms">
                {forms.map((f) => <option key={f} value={f} />)}
              </datalist>
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={!ready || busy}
              title={ready ? undefined : 'UID – oder Firmenname und Rechtsform – fehlen.'}
              onClick={() => void create()}>
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

/** Die zugeordnete Firma, wie die Person sie sieht: Name mit Rechtsform und UID. Ändern
 *  kann sie sie nicht – nur die Zuordnung lösen und eine andere nennen. */
function Current({ company, busy, readOnly, onUnlink }: {
  company: CompanyRef | null | undefined; busy: boolean; readOnly?: boolean;
  onUnlink: () => void;
}) {
  if (!company) {
    return <span className="text-sm text-fg-3">Keine – Privatperson</span>;
  }
  return (
    <div className="flex items-center justify-between gap-3 rounded-ds-md border border-border-1 px-3 py-2">
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-semibold text-fg-1 truncate">{company.legal_name}</span>
        {company.uid_number && (
          <span className="text-xs text-fg-3 ix-tnum">{company.uid_number}</span>
        )}
      </div>
      {!readOnly && (
        <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={busy}
          onClick={onUnlink} title="Die Zuordnung lösen – danach bestellt die Person privat.">
          <Unlink size={13} /> Lösen
        </button>
      )}
    </div>
  );
}
