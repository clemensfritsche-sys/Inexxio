'use client';

import { useRef, useState } from 'react';
import { Building2, User } from 'lucide-react';
import { api } from '@/lib/api';
import { legalForms } from '@/lib/legal-forms';
import { Field as AField, SelectField } from '@/components/form/field';
import { Card, DetailBody, DetailHeader, HeaderAction } from '@/components/erp/detail-frame';
import { ErrorText } from '@/components/erp/hints';
import { Segmented } from '@/components/erp/controls';
import { OWN_OPTIONS } from '@/components/erp/organization-detail';
import { ObjectSelect } from '@/components/erp/object-select';
import type { CompanySettings, CompanyRef, UserProfile, UserRole } from '@/types';
import { useAction } from '@/lib/use-action';
import { NOTHING } from '@/lib/when';
import { ROLES } from '@/lib/vocab';
import { isStaff } from '@/lib/record-status';

/**
 * ►►► **Eine Person anlegen – ohne dass sie sich je angemeldet hat** (CRM Schritt 1). ◄◄◄
 *
 * Das Minimum ist Vorname, Nachname, E-Mail und Rolle; die Firma kann gleich mit. Wie bei
 * jedem Entwurf im Haus lebt sie bis zum Anlegen im Browser – erst dann entstehen
 * Objektnummer und Anmeldekonto (`people.create_person`). Meldet sich die Person später mit
 * dieser E-Mail an, ist sie **dieser** Datensatz. Personal-Rollen vergibt nur ein Admin –
 * der Dienst prüft es, die Auswahl bietet sie darum nur einem Admin an.
 */
export function NewPerson({ isAdmin, initial, onSaved, onBack }: {
  isAdmin: boolean; onSaved: (u: UserProfile) => void; onBack: () => void;
  /** Vorausgefüllt aus einem Vorschlag («Entwurf öffnen») – Spaltennamen wie die API. */
  initial?: Record<string, string> | null;
}) {
  const [first, setFirst] = useState(initial?.first_name ?? '');
  const [last, setLast] = useState(initial?.last_name ?? '');
  const [email, setEmail] = useState(initial?.email ?? '');
  // Rolle und Firma kommen mit, wenn der Vorschlag sie nennt – Personal-Rollen nur für einen Admin.
  const [role, setRole] = useState<UserRole>(roleOf(initial?.role, isAdmin));
  const [companyId, setCompanyId] = useState<number | null>(
    Number(initial?.company_object_id) > 0 ? Number(initial?.company_object_id) : null);
  // Der Name der gewählten Firma (aus der Suche); vorausgefüllt zeigt das Feld ihre Nummer.
  const [company, setCompany] = useState<CompanyRef | null>(null);
  // Die zuletzt gezeigten Vorschläge – die Wahl gibt nur die Nummer zurück.
  const found = useRef<CompanyRef[]>([]);
  const { busy, error, run } = useAction('Anlegen nicht möglich.');

  const missing = [!first.trim() && 'Vorname', !last.trim() && 'Nachname',
                   !email.trim() && 'E-Mail'].filter(Boolean) as string[];

  const create = () => run(async () => onSaved(await api.createErpRecord({
    first_name: first, last_name: last, email, role,
    company_object_id: companyId,
  })));

  const roles = [{ value: 'user', label: 'Benutzer' },
                 ...(isAdmin ? [{ value: 'employee', label: 'Mitarbeiter' },
                                { value: 'admin', label: 'Admin' }] : [])];
  const title = `${first} ${last}`.trim();

  return (
    <div className="flex-1 overflow-y-auto">
      <DetailHeader type="user" title={title || null} placeholder="Neue Person"
        objectIdText={NOTHING} objectIdHint="Die Objektnummer entsteht beim Anlegen."
        onBack={onBack}
        actions={<HeaderAction label="Anlegen" disabled={busy || missing.length > 0}
          hint={missing.length ? `Es fehlt: ${missing.join(', ')}.` : undefined}
          onClick={() => void create()} />}
        right={<button type="button" className="erp-actbtn erp-actbtn-neutral" onClick={onBack}>Abbrechen</button>} />
      <DetailBody>
        <Card icon={User} title="Person">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <AField name="first_name" label="Vorname" value={first} onChange={setFirst} required placeholder="Max" />
            <AField name="last_name" label="Nachname" value={last} onChange={setLast} required placeholder="Muster" />
            <AField name="email" label="E-Mail" value={email} onChange={setEmail} required type="email"
              placeholder="max.muster@firma.ch" />
            <SelectField name="role" label="Rolle" value={role} onChange={(v) => setRole(v as UserRole)}
              options={roles} />
            <div className="sm:col-span-2">
              <ObjectSelect<{ object_id: number; name: string }>
                label="Firma" value={companyId} kind="company" scanLabel="Firma"
                emptyOption="Keine – Privatperson"
                selected={company && company.object_id === companyId
                  ? { object_id: company.object_id, name: company.legal_name } : null}
                find={async (q) => {
                  const rows = await api.searchCompanies(q);
                  found.current = rows;
                  return rows.map((c) => ({ object_id: c.object_id, name: c.legal_name }));
                }}
                onChange={(id) => {
                  setCompanyId(id);
                  setCompany(id == null ? null : found.current.find((c) => c.object_id === id) ?? null);
                }} />
            </div>
          </div>
          {error && <ErrorText msg={error} />}
        </Card>
      </DetailBody>
    </div>
  );
}

/** Die Rolle aus einem Vorschlag – nur eine, die es gibt und die diese Person vergeben darf. */
function roleOf(raw: string | undefined, isAdmin: boolean): UserRole {
  const known = ROLES.find((r) => r === raw) ?? 'user';
  return isStaff(known) && !isAdmin ? 'user' : known;
}

/**
 * ►►► **Eine Firma anlegen** – Kunde, Lieferant oder (nur Admin) eine unserer
 * Gesellschaften. ◄◄◄ Name und Rechtsform sind Pflicht: «Muster» ist keine Rechtsperson,
 * «Muster AG» ist eine. Alles Weitere pflegt man danach an ihrem Datensatz.
 */
export function NewCompany({ isAdmin, initial, onSaved, onBack }: {
  isAdmin: boolean; onSaved: (c: CompanySettings) => void; onBack: () => void;
  /** Vorausgefüllt aus einem Vorschlag («Entwurf öffnen») – Spaltennamen wie die API. */
  initial?: Record<string, string> | null;
}) {
  const [name, setName] = useState(initial?.company_name ?? '');
  const [form, setForm] = useState(initial?.legal_form ?? '');
  const [uid, setUid] = useState(initial?.uid_number ?? '');
  const [own, setOwn] = useState(false);
  const { busy, error, run } = useAction('Anlegen nicht möglich.');
  const forms = legalForms('CH');
  const missing = [!name.trim() && 'Firmenname', !form.trim() && 'Rechtsform']
    .filter(Boolean) as string[];

  const create = () => run(async () => onSaved(await api.createCompany({
    company_name: name.trim(), legal_form: form.trim(), uid_number: uid.trim() || null, is_own: own,
  })));

  return (
    <div className="flex-1 overflow-y-auto">
      <DetailHeader type="organization" title={name.trim() || null} placeholder="Neue Firma"
        objectIdText={NOTHING} objectIdHint="Die Objektnummer entsteht beim Anlegen."
        onBack={onBack}
        actions={<HeaderAction label="Anlegen" disabled={busy || missing.length > 0}
          hint={missing.length ? `Es fehlt: ${missing.join(', ')}.` : undefined}
          onClick={() => void create()} />}
        right={<button type="button" className="erp-actbtn erp-actbtn-neutral" onClick={onBack}>Abbrechen</button>} />
      <DetailBody>
        <Card icon={Building2} title="Firma">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <AField name="company_name" label="Firmenname" value={name} onChange={setName} required placeholder="Muster" />
            <div>
              <AField name="legal_form" label="Rechtsform" value={form} onChange={setForm} required list="new-company-forms"
                placeholder={forms[0] ?? 'AG'} />
              <datalist id="new-company-forms">
                {forms.map((f) => <option key={f} value={f} />)}
              </datalist>
            </div>
            <AField name="uid_number" label="UID-Nummer" value={uid} onChange={setUid} placeholder="CHE-123.456.789" />
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
