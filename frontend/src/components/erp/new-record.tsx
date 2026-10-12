'use client';

import { useRef, useState } from 'react';
import { Building2, User } from 'lucide-react';
import { api } from '@/lib/api';
import { legalForms } from '@/lib/legal-forms';
import { Field as AField, SelectField } from '@/components/account/field';
import { Card, DetailBody, DetailHeader, ErrorText, HeaderAction, Segmented } from '@/components/erp/fields';
import { OWN_OPTIONS } from '@/components/erp/organization-detail';
import { ObjectSelect } from '@/components/erp/object-select';
import type { CompanySettings, CompanyRef, UserProfile, UserRole } from '@/types';

/**
 * ►►► **Eine Person anlegen – ohne dass sie sich je angemeldet hat** (CRM Schritt 1). ◄◄◄
 *
 * Das Minimum ist Vorname, Nachname, E-Mail und Rolle; die Firma kann gleich mit. Wie bei
 * jedem Entwurf im Haus lebt sie bis zum Anlegen im Browser – erst dann entstehen
 * Objektnummer und Anmeldekonto (`people.create_person`). Meldet sich die Person später mit
 * dieser E-Mail an, ist sie **dieser** Datensatz. Personal-Rollen vergibt nur ein Admin –
 * der Dienst prüft es, die Auswahl bietet sie darum nur einem Admin an.
 */
export function NewPerson({ isAdmin, onSaved, onBack }: {
  isAdmin: boolean; onSaved: (u: UserProfile) => void; onBack: () => void;
}) {
  const [first, setFirst] = useState('');
  const [last, setLast] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('user');
  const [company, setCompany] = useState<CompanyRef | null>(null);
  // Die zuletzt gezeigten Vorschläge – die Wahl gibt nur die Nummer zurück.
  const found = useRef<CompanyRef[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const missing = [!first.trim() && 'Vorname', !last.trim() && 'Nachname',
                   !email.trim() && 'E-Mail'].filter(Boolean) as string[];

  async function create() {
    setBusy(true);
    setError('');
    try {
      onSaved(await api.createErpRecord({
        first_name: first, last_name: last, email, role,
        company_object_id: company?.object_id ?? null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Anlegen nicht möglich.');
    } finally {
      setBusy(false);
    }
  }

  const roles = [{ value: 'user', label: 'Benutzer' },
                 ...(isAdmin ? [{ value: 'employee', label: 'Mitarbeiter' },
                                { value: 'admin', label: 'Admin' }] : [])];
  const title = `${first} ${last}`.trim();

  return (
    <div className="flex-1 overflow-y-auto">
      <DetailHeader type="user" title={title || null} placeholder="Neue Person"
        objectIdText="—" objectIdHint="Die Objektnummer entsteht beim Anlegen."
        onBack={onBack}
        actions={<HeaderAction label="Anlegen" disabled={busy || missing.length > 0}
          hint={missing.length ? `Es fehlt: ${missing.join(', ')}.` : undefined}
          onClick={() => void create()} />}
        right={<button type="button" className="erp-actbtn erp-actbtn-neutral" onClick={onBack}>Abbrechen</button>} />
      <DetailBody>
        <Card icon={User} title="Person">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <AField label="Vorname" value={first} onChange={setFirst} required placeholder="Max" />
            <AField label="Nachname" value={last} onChange={setLast} required placeholder="Muster" />
            <AField label="E-Mail" value={email} onChange={setEmail} required type="email"
              placeholder="max.muster@firma.ch" />
            <SelectField label="Rolle" value={role} onChange={(v) => setRole(v as UserRole)}
              options={roles} />
            <div className="sm:col-span-2">
              <ObjectSelect<{ object_id: number; name: string }>
                label="Firma" value={company?.object_id ?? null} kind="company" scanLabel="Firma"
                emptyOption="Keine – Privatperson"
                selected={company ? { object_id: company.object_id, name: company.legal_name } : null}
                find={async (q) => {
                  const rows = await api.searchCompanies(q);
                  found.current = rows;
                  return rows.map((c) => ({ object_id: c.object_id, name: c.legal_name }));
                }}
                onChange={(id) => setCompany(id == null ? null : found.current.find((c) => c.object_id === id) ?? null)} />
            </div>
          </div>
          {error && <ErrorText msg={error} />}
        </Card>
      </DetailBody>
    </div>
  );
}

/**
 * ►►► **Eine Firma anlegen** – Kunde, Lieferant oder (nur Admin) eine unserer
 * Gesellschaften. ◄◄◄ Name und Rechtsform sind Pflicht: «Muster» ist keine Rechtsperson,
 * «Muster AG» ist eine. Alles Weitere pflegt man danach an ihrem Datensatz.
 */
export function NewCompany({ isAdmin, onSaved, onBack }: {
  isAdmin: boolean; onSaved: (c: CompanySettings) => void; onBack: () => void;
}) {
  const [name, setName] = useState('');
  const [form, setForm] = useState('');
  const [uid, setUid] = useState('');
  const [own, setOwn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const forms = legalForms('CH');
  const missing = [!name.trim() && 'Firmenname', !form.trim() && 'Rechtsform']
    .filter(Boolean) as string[];

  async function create() {
    setBusy(true);
    setError('');
    try {
      onSaved(await api.createCompany({ company_name: name.trim(), legal_form: form.trim(),
                                         uid_number: uid.trim() || null, is_own: own }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Anlegen nicht möglich.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <DetailHeader type="organization" title={name.trim() || null} placeholder="Neue Firma"
        objectIdText="—" objectIdHint="Die Objektnummer entsteht beim Anlegen."
        onBack={onBack}
        actions={<HeaderAction label="Anlegen" disabled={busy || missing.length > 0}
          hint={missing.length ? `Es fehlt: ${missing.join(', ')}.` : undefined}
          onClick={() => void create()} />}
        right={<button type="button" className="erp-actbtn erp-actbtn-neutral" onClick={onBack}>Abbrechen</button>} />
      <DetailBody>
        <Card icon={Building2} title="Firma">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <AField label="Firmenname" value={name} onChange={setName} required placeholder="Muster" />
            <div>
              <AField label="Rechtsform" value={form} onChange={setForm} required list="new-company-forms"
                placeholder={forms[0] ?? 'AG'} />
              <datalist id="new-company-forms">
                {forms.map((f) => <option key={f} value={f} />)}
              </datalist>
            </div>
            <AField label="UID-Nummer" value={uid} onChange={setUid} placeholder="CHE-123.456.789" />
            {/* Vorgewählt: extern. «Eigen» setzt nur ein Admin. */}
            <Segmented value={own ? 'own' : 'foreign'} disabled={!isAdmin}
              tip={isAdmin ? undefined : 'Eine eigene Gesellschaft legt nur ein Admin an.'}
              onChange={(v) => setOwn(v === 'own')} options={OWN_OPTIONS} />
          </div>
          {error && <ErrorText msg={error} />}
        </Card>
      </DetailBody>
    </div>
  );
}
