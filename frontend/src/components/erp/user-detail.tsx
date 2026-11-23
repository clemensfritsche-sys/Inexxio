'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Mail } from 'lucide-react';
import { ClaudeList, PasskeyList } from '@/components/erp/person-access';
import { Communication } from '@/components/erp/communication';
import { userDisplayName } from '@/lib/utils';
import { NOTHING, day, when } from '@/lib/when';
import { ROLE_CFG, isStaff, userStatus } from '@/lib/record-status';
import { ROLES, lookup } from '@/lib/vocab';
import { api } from '@/lib/api';
import { Card, DETAIL_PANE, DetailBody, DetailHeader, TodoAt, TodoChip } from '@/components/erp/detail-frame';
import { DocumentTiles } from '@/components/erp/documents';
import { TimeCard } from '@/components/erp/time/time-card';
import { PAYMENTS_TIP, PaymentList, usePayments } from '@/components/erp/payment-list';
import { sectionItems, todoChanged } from '@/lib/todo';
// **ERP ist Master, das Profil ist der Spiegel** – der Profil-Teil nutzt dieselben Bausteine
// wie das Konto (ein Formular, ein Auto-Save, Google-Adress-Suche); dazu nur die ERP-Extras
// (Rolle, Anstellung, System).
import { KtDate, KtField, KtSelect } from '@/components/form/kt-section';
import { ChangesSwitch } from '@/components/erp/history';
import { AddressBook } from '@/components/erp/address-book';
import { Competences } from '@/components/erp/competences';
import { CompanyField } from '@/components/erp/company-field';
import { useMapsApiKey } from '@/lib/use-maps-key';
import { useAutosaveValue } from '@/lib/use-autosave';
import { SaveStatusIndicator } from '@/components/form/save-status';
import type { ErpAdminUpdate, NewsletterState, Todo, UserProfile, UserRole } from '@/types';
import { qk } from '@/lib/queries';
import { errorText, useAction } from '@/lib/use-action';

// ►►► **Eine Seite aus Abschnitten – dieselben wie im Konto** (`Card` = `.kt-sec`, Felder `KtField`). ◄◄◄
// Keine Reiter, keine Karten: Verlauf · Zeit · Zahlungen · Person · Adressen · Firma · Mitarbeit ·
// Newsletter · Sicherheit · System, getrennt von Haarlinien. Was die Person im Konto sieht, sieht
// das Personal hier genauso – dazu nur die ERP-Extras (Mitarbeit, System).

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function userInitials(name: string, email: string): string {
  if (name && name !== email) {
    return name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }
  return email[0]?.toUpperCase() ?? '?';
}

// ─── Formular (Spiegel des Profils + ERP-Extras) ───────────────────────────────

/** Die Sprache, in der wir der Person schreiben – automatische Mails folgen ihr. */
type Language = NonNullable<ErpAdminUpdate['language']>;
const LANGUAGES: Record<Language, string> = { de: 'Deutsch', fr: 'Französisch', en: 'Englisch', it: 'Italienisch' };

interface ERPForm {
  role: UserRole;
  language: Language;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
}

type StrKey = { [K in keyof ERPForm]: ERPForm[K] extends string ? K : never }[keyof ERPForm];

function buildForm(p: UserProfile): ERPForm {
  return {
    role: p.role,
    language: (p.language in LANGUAGES ? p.language : 'de') as Language,
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
  };
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/**
 * Form → Update-Payload. Eintritt, Pensum und Austritt stehen im Vertrag der Zeiterfassung
 * (`time/time-contracts`); Firma (`CompanyField`) und Anschriften (`AddressBook`) speichern selbst.
 */
function mapUpdate(v: ERPForm): ErpAdminUpdate {
  return {
    role: v.role,
    language: v.language,
    first_name: nn(v.first_name),
    last_name: nn(v.last_name),
    date_of_birth: nn(v.date_of_birth),
    phone: nn(v.phone),
  };
}

/**
 * ►►► **Der Newsletter einer Person – Zustand, Nachweis, eine Handlung.** ◄◄◄ Anmelden kann das ERP
 * niemanden: es schickt die Bitte um Bestätigung. Abmelden geht. Darunter der Nachweis mit Datum und
 * Quelle, der Wortlaut im Hover.
 */
function NewsletterConsent({ person }: { person: number }) {
  const qc = useQueryClient();
  const state = useQuery({
    queryKey: qk.newsletter(person),
    queryFn: ({ signal }) => api.personNewsletter(person, { signal }),
    meta: { what: 'Newsletter-Stand' },
  }).data ?? null;
  const [note, setNote] = useState<string | null>(null);
  const { busy, run } = useAction();
  // Die Antwort IST der neue Stand; die Bitte steht danach im Verlauf (`lib/feed.TOUCHES`).
  const act = async (call: () => Promise<NewsletterState>, done: string) => {
    setNote(null);
    const s = await run(call, (e) => setNote(errorText(e, 'Hat nicht geklappt.')));
    if (s) { qc.setQueryData(qk.newsletter(person), s); setNote(done); }
  };
  if (!state) return null;
  const on = state.subscribed;
  return (
    <>
      <div className="kt-card">
        <span className="kt-card-ic"><Mail aria-hidden /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="kt-card-tag">«Post von INEXXIO»</span>
          <div className="kt-card-text">
            {on ? 'Angemeldet' : 'Nicht angemeldet'}
            {state.since && <small>{on ? 'Seit' : 'Abgemeldet am'} {day(state.since)} · {state.source}</small>}
          </div>
        </div>
      </div>
      {on ? (
        <button type="button" className="kt-add" disabled={busy}
          data-tip="Im Namen der Person abmelden – z. B. wenn sie es am Telefon sagt"
          onClick={() => act(() => api.unsubscribeNewsletter(person), 'Abgemeldet.')}>Abmelden</button>
      ) : (
        <button type="button" className="kt-add" disabled={busy}
          data-tip="Schickt die Bitte um Bestätigung – angemeldet ist sie erst mit ihrem Klick"
          onClick={() => act(() => api.inviteNewsletter(person), 'Einladung verschickt – sie steht im Verlauf.')}>
          Einladung senden</button>
      )}
      {note && <p className="kt-note">{note}</p>}
      {state.history.length > 0 && (
        <div style={{ display: 'grid', gap: 2, fontSize: 13, color: 'var(--fg-3)' }}>
          {state.history.map((r, i) => (
            <span key={i} className="tabular-nums" data-tip={r.wording ?? undefined}>
              {day(r.at)} · {r.subscribed ? 'Angemeldet' : 'Abgemeldet'} · {r.source}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

/**
 * Die Stammdaten in Abschnitten: Person · Adressen · Firma · Mitarbeit · Newsletter · Sicherheit ·
 * System. **Ein Formular, ein Auto-Save** für Person und Rolle (der Stand steht unter «Person»);
 * Adressen, Firma, Kompetenzen und Newsletter speichern selbst.
 */
function ProfileForm({ record, isAdmin, onSaved, todo }: {
  record: UserProfile; isAdmin: boolean; onSaved: (u: UserProfile) => void; todo?: Todo | null;
}) {
  // Ändern darf, wem der Server es sagt (`may_edit`, `domain/policy`): Kunden jedes Personal,
  // Mitarbeitende nur der Admin. Die Rolle vergibt nur der Admin.
  const canEdit = record.may_edit;
  const ro = !canEdit;
  const mapsKey = useMapsApiKey();
  // **Einmal befüllt** – ein neuer `record` nach dem Auto-Save überschreibt nichts, was gerade
  // getippt wird. Ein anderer Datensatz ist ein neues Formular (`key` am Aufrufer).
  const [form, setForm] = useState<ERPForm>(() => buildForm(record));
  const objectId = record.object_id;
  const { status, errorMsg, saveNow } = useAutosaveValue(
    form,
    async (v) => {
      if (!canEdit || !objectId) return;
      const updated = await api.updateErpRecord(objectId, mapUpdate(v));
      onSaved(updated);
      todoChanged();
    },
  );

  function set<K extends keyof ERPForm>(key: K, value: ERPForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }
  const str = (k: StrKey) => (canEdit ? (val: string) => setForm((prev) => ({ ...prev, [k]: val })) : undefined);
  // **Pflicht sagt der Server** (`people.required_fields`) – hier nur die Markierung «· fehlt».
  const missing = (k: StrKey) => (record.required_fields ?? []).includes(k) && !form[k].trim();
  const staff = isStaff(record.role);

  return (
    <>
      <Card title="Person" anchor="person" extra={<TodoChip items={sectionItems(todo, 'person')} />}
        right={canEdit ? <SaveStatusIndicator status={status} errorMsg={errorMsg} /> : undefined}>
        <div className="kt-grid2">
          <KtField name="first_name" label="Vorname" value={form.first_name} onChange={str('first_name')}
            readOnly={ro} placeholder="Max" onEnter={saveNow} missing={missing('first_name')} />
          <KtField name="last_name" label="Nachname" value={form.last_name} onChange={str('last_name')}
            readOnly={ro} placeholder="Muster" onEnter={saveNow} missing={missing('last_name')} />
          <KtField name="phone" label="Telefon" type="tel" value={form.phone} onChange={str('phone')}
            readOnly={ro} placeholder="+41 44 000 00 00" onEnter={saveNow} missing={missing('phone')} />
          {ro ? (
            <KtField name="date_of_birth" label="Geburtsdatum" value={day(form.date_of_birth || null)} readOnly />
          ) : (
            <KtDate id={`born-${objectId}`} name="date_of_birth" label="Geburtsdatum" value={form.date_of_birth}
              onChange={(v) => set('date_of_birth', v)} onEnter={saveNow} missing={missing('date_of_birth')} />
          )}
          <KtField name="email" label="E-Mail" value={record.email} readOnly />
          {/* Gesetzt, wenn die Person uns zum ersten Mal schreibt; automatische Mails folgen ihr. */}
          {ro ? (
            <KtField name="language" label="Sprache" value={LANGUAGES[form.language]} readOnly />
          ) : (
            <KtSelect name="language" label="Sprache" value={form.language}
              onChange={(x) => set('language', x as Language)}
              options={(Object.keys(LANGUAGES) as Language[]).map((l) => ({ value: l, label: LANGUAGES[l] }))} />
          )}
        </div>
      </Card>

      {/* Dieselbe Maske wie im Konto (`cards`). */}
      <Card title="Adressen" anchor="adressen" extra={<TodoChip items={sectionItems(todo, 'adressen')} />}>
        <AddressBook owner={record.object_id ?? null} account="private" cards
          addresses={record.addresses ?? []} loginEmail={record.email} readOnly={ro}
          mapsKey={mapsKey} onSaved={onSaved} />
      </Card>

      {/* ►►► **Das Personal ordnet zu – aus den bestehenden Firmen.** ◄◄◄ Neu angelegt wird
          über «+» im Feed. Eine fremde Firma ist nur ihre Identität; für Personal muss es eine
          unserer Gesellschaften sein (`people.assert_employment`). */}
      <Card title="Firma">
        <CompanyField company={record.company} readOnly={ro} search look="kt"
          country={record.addresses?.[0]?.country}
          onLink={(id) => api.updateErpRecord(record.object_id as number,
            { company_object_id: id }).then(onSaved)} />
        {record.company && (
          <AddressBook owner={record.object_id ?? null} account="business" cards
            addresses={record.addresses ?? []} loginEmail={record.email} readOnly={ro}
            mapsKey={mapsKey} onSaved={onSaved} />
        )}
      </Card>

      {/* ►►► **Die Rolle ist der ZUGANG** (`people.STAFF_ROLES`) – nur im ERP. ◄◄◄ Lieferant ↔ Kunde
          ist eine Eigenschaft des Vorgangs, nicht der Person. */}
      <Card title={staff ? 'Mitarbeit' : 'Rolle'}>
        {canEdit && isAdmin ? (
          <KtSelect name="role" label="Rolle" value={form.role} onChange={(x) => set('role', x as UserRole)}
            options={ROLES.map((r) => ({ value: r, label: ROLE_CFG[r].label }))} />
        ) : (
          <KtField name="role" label="Rolle" value={lookup(ROLE_CFG, form.role)?.label ?? form.role} readOnly />
        )}
        {staff && <Competences record={record} onSaved={onSaved} />}
      </Card>

      <Card title="Newsletter">
        {record.object_id != null && <NewsletterConsent person={record.object_id} />}
      </Card>

      {/* ►►► **Sicherheit – dasselbe Bauteil wie im Konto** (ERP ist Master): Passkeys und
          Verbindungen mit Claude. Nur die Person selbst und der Admin (`may_access`, «person.access»). */}
      {record.may_access && record.object_id != null && (
        <Card title="Sicherheit" anchor="zugang"
          info="Wie die Person hereinkommt: ihre Passkeys und ihre Verbindungen mit Claude. Entfernen und Trennen gelten sofort.">
          <PasskeyList owner={record.object_id} cards />
          {staff && <ClaudeList owner={record.object_id} cards />}
        </Card>
      )}

      <Card title="System">
        <div className="kt-grid2">
          <KtField name="last_sign_in_provider" label="Anmeldung" value={signInLabel(record.last_sign_in_provider)} readOnly />
          {/* Die Passkeys selbst stehen in «Sicherheit» – wer sie nicht sieht, sieht hier ihre Zahl. */}
          {!record.may_access && (
            <KtField name="passkey_count" label="Passkeys" value={passkeyLabel(record.passkey_count)} readOnly />
          )}
          <KtField name="last_login_at" label="Letzte Anmeldung" value={when(record.last_login_at)} readOnly />
          <KtField name="created_at" label="Erstellt" value={when(record.created_at)} readOnly />
          <KtField name="updated_at" label="Zuletzt geändert" value={when(record.updated_at)} readOnly />
        </div>
        {isAdmin && (
          <KtField name="firebase_uid" label="Firebase UID" value={record.firebase_uid} readOnly />
        )}
      </Card>
    </>
  );
}

/** Anmeldeweg aus dem Firebase-ID-Token, in Klartext. */
function signInLabel(provider: string | null | undefined): string {
  const map: Record<string, string> = {
    'google.com': 'Google SSO',
    custom: 'Passkey',          // Passkey-Login stellt ein Firebase Custom Token aus
    emailLink: 'Anmeldelink',
    password: 'Passwort',
  };
  return provider ? (map[provider] ?? provider) : NOTHING;
}

function passkeyLabel(count: number | null | undefined): string {
  const n = count ?? 0;
  return n === 0 ? 'Keiner eingerichtet' : `${n} Gerät${n === 1 ? '' : 'e'}`;
}

export function UserDetail({ record, onSave, isAdmin, onBack, me, todo }: {
  record: UserProfile;
  onSave: (u: UserProfile) => void;
  isAdmin: boolean;
  onBack: () => void;
  /** Wer gerade arbeitet – Absender einer neuen Nachricht. */
  me?: { object_id: number; name: string } | null;
  /** Was zu tun ist – die Zahl am Symbol (wie im Feed), dazu je Abschnitt. */
  todo?: Todo | null;
}) {
  const rc       = userStatus(record);
  const name     = userDisplayName(record);
  const hasName  = !!name && name !== record.email;
  const initials = userInitials(name, record.email);
  const payments = usePayments(record.object_id != null ? { person: record.object_id } : null);
  // «Änderungen zeigen» im Verlauf – standardmässig aus.
  const [changes, setChanges] = useState(false);
  const id = record.object_id;

  // Eine Person wird nicht deaktiviert – sie wechselt die Rolle (Abschnitt «Mitarbeit»).

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`). */}
      <DetailHeader
        type="user" title={hasName ? name : null} placeholder="Kein Name"
        objectId={id} onBack={onBack}
        status={rc}
        photoUrl={record.photo_url} initials={initials} todo={todo}
      />

      <div style={DETAIL_PANE}>
        <DetailBody>
          {id != null && (
            <Card title="Verlauf" right={<ChangesSwitch on={changes} onChange={setChanges} />}>
              <TodoAt part="kommunikation" objectId={id}>
                <Communication me={me} changes={changes}
                  person={{ object_id: id, name: hasName ? name : record.email }} />
              </TodoAt>
            </Card>
          )}
          {/* ►►► **Zeit** – eigener Datensatz oder Admin, und nur für Personal. Der Server prüft es
              noch einmal (`timekeeping.may_see`). */}
          {id != null && isStaff(record.role) && (isAdmin || me?.object_id === id) && (
            <TimeCard person={id} todo={sectionItems(todo, 'zeiterfassung')} />
          )}
          {/* ►►► **Zahlungen** – jede Zahlung, in der diese Person Partei ist; eine Ableitung, keine
              Kopie. Ohne Zahlung kein Abschnitt. */}
          {payments != null && payments.length > 0 && (
            <Card title="Zahlungen" anchor="zahlungen" info={PAYMENTS_TIP} wide
              extra={<TodoChip items={sectionItems(todo, 'zahlungen')} />}>
              <PaymentList rows={payments} />
            </Card>
          )}
          <ProfileForm key={id} record={record} isAdmin={isAdmin} onSaved={onSave} todo={todo} />
          <DocumentTiles objectId={id} />
        </DetailBody>
      </div>
    </div>
  );
}
