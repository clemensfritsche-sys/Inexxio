'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  User, MapPin, Building2, Bell, Cog,
} from 'lucide-react';
import { Communication } from '@/components/erp/communication';
import { userDisplayName } from '@/lib/utils';
import { day, when } from '@/lib/when';
import { ROLE_CFG, isStaff, userStatus } from '@/lib/record-status';
import { api } from '@/lib/api';
import { Card, DetailBody, DetailHeader, SectionSep, StatusDot, TodoChip } from '@/components/erp/fields';
import { DocumentTiles } from '@/components/erp/documents';
import { TimeCard } from '@/components/erp/time/time-card';
import { PAYMENTS_TIP, PaymentList, usePayments } from '@/components/erp/payment-list';
import { sectionItems, todoChanged } from '@/lib/todo';
// **ERP ist Master, das Profil ist der Spiegel** – und weil dem Nutzer Struktur, Logik
// und Namensgebung der Profileinstellungen besser gefallen (Notiz #294), übernimmt der
// Profil-Reiter hier **dieselben Bausteine** wie das Konto: EIN Formular, EIN Auto-Save,
// «Rechnungsadresse = Lieferadresse»-Schalter mit Spiegelung, Google-Adress-Suche. Keine
// zweite Optik, kein zweiter Feld-Satz – nur die ERP-Extras kommen dazu (Notiz #295:
// Rolle, admin-pflegbare Anstellung, System). Reuse statt Nachbau.
import { Field as AField, SelectField } from '@/components/form/field';
import { AddressBook } from '@/components/erp/address-book';
import { CompanyField } from '@/components/erp/company-field';
import { useMapsApiKey } from '@/lib/use-maps-key';
import { useAutosaveValue } from '@/lib/use-autosave';
import { SaveStatusIndicator } from '@/components/form/save-status';
import type { ErpAdminUpdate, NewsletterState, Todo, UserProfile, UserRole } from '@/types';
import { qk } from '@/lib/queries';

// **Keine Reiter**: Kommunikation und Stammdaten stehen auf EINER Seite. «Bestellungen» und
// «Dokumente» kommen mit ihren Bereichen zurück (docs/attic.md).

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function userInitials(name: string, email: string): string {
  if (name && name !== email) {
    return name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }
  return email[0]?.toUpperCase() ?? '?';
}

// ─── Formular (Spiegel des Profils + ERP-Extras) ───────────────────────────────

interface ERPForm {
  role: UserRole;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
}

type StrKey = { [K in keyof ERPForm]: ERPForm[K] extends string ? K : never }[keyof ERPForm];

function buildForm(p: UserProfile): ERPForm {
  return {
    role: p.role,
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
  };
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/**
 * Form → Update-Payload. Eintritt, Pensum und Austritt stehen im **Vertrag** der
 * Zeiterfassung (`time/time-contracts`), nicht mehr hier. Firma und Anschriften stehen
 * ebenfalls nicht in diesem Formular: die Firma wird zugeordnet (`CompanyField`), die
 * Anschriften leben im Adressbuch (`AddressBook`), jede mit ihrem eigenen Auto-Save.
 */
function mapUpdate(v: ERPForm): ErpAdminUpdate {
  return {
    role: v.role,
    first_name: nn(v.first_name),
    last_name: nn(v.last_name),
    date_of_birth: nn(v.date_of_birth),
    phone: nn(v.phone),
  };
}

/**
 * ►►► **Der Newsletter einer Person – Zustand, Nachweis, zwei Handlungen.** ◄◄◄ Anmelden
 * kann das ERP niemanden: es schickt die Bitte um Bestätigung (sie steht danach im Chat
 * oben), und angemeldet ist die Person erst mit ihrem Klick. Abmelden geht – wer es am
 * Telefon sagt, wird hier abgemeldet. Der Nachweis darunter: jede Zeile mit Datum und
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
  const [busy, setBusy] = useState(false);
  // Die Antwort IST der neue Stand; die Bitte steht danach im Verlauf (`lib/feed.TOUCHES`).
  const act = (call: Promise<NewsletterState>, done: string) => {
    setBusy(true); setNote(null);
    call.then((s) => { qc.setQueryData(qk.newsletter(person), s); setNote(done); })
      .catch((e) => setNote(e instanceof Error ? e.message : 'Hat nicht geklappt.'))
      .finally(() => setBusy(false));
  };
  const on = !!state?.subscribed;
  const link = { border: 0, background: 'none', padding: 0, font: 'inherit', fontSize: 13,
    color: 'var(--accent)', cursor: busy ? 'wait' : 'pointer' } as const;
  return (
    <div style={{ display: 'grid', gap: 8, minHeight: 44 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 14 }}>
        <StatusDot color={on ? 'var(--success)' : 'var(--fg-4)'} />
        <span style={{ fontWeight: 500 }}>Newsletter {on ? 'angemeldet' : 'nicht angemeldet'}</span>
        {state?.since && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
          {on ? 'seit' : 'abgemeldet am'} {day(state.since)} · {state.source}</span>}
        <span style={{ flex: 1 }} />
        {state && (on
          ? <button type="button" style={link} disabled={busy}
              data-tip="Im Namen der Person abmelden – z. B. wenn sie es am Telefon sagt"
              onClick={() => act(api.unsubscribeNewsletter(person), 'Abgemeldet.')}>Abmelden</button>
          : <button type="button" style={link} disabled={busy}
              data-tip="Schickt die Bitte um Bestätigung – angemeldet ist sie erst mit ihrem Klick"
              onClick={() => act(api.inviteNewsletter(person), 'Einladung verschickt – sie steht oben im Verlauf.')}>
              Einladung senden</button>)}
      </div>
      {note && <p style={{ fontSize: 12, color: 'var(--fg-3)', margin: 0 }}>{note}</p>}
      {state && state.history.length > 0 && (
        <div style={{ display: 'grid', gap: 2, fontSize: 12, color: 'var(--fg-3)' }}>
          {state.history.map((r, i) => (
            <span key={i} className="tabular-nums" data-tip={r.wording ?? undefined}>
              {day(r.at)} · {r.subscribed ? 'Angemeldet' : 'Abgemeldet'} · {r.source}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileForm({ record, isAdmin, onSaved, todo }: {
  record: UserProfile; isAdmin: boolean; onSaved: (u: UserProfile) => void; todo?: Todo | null;
}) {
  const canEdit = isAdmin;
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

  const role = form.role;
  // **Pflicht sagt der Server** (`people.required_fields`) – hier nur die Markierung.
  const required = (k: string) => (record.required_fields ?? []).includes(k);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── 1. Persönliche Angaben ─────────────────────────────────────────── */}
      <Card icon={User} title="Person" anchor="person" extra={<TodoChip items={sectionItems(todo, 'person')} />}
        right={canEdit ? <SaveStatusIndicator status={status} errorMsg={errorMsg} /> : undefined}>
        {/* Rolle – ERP-Extra (das Konto kennt sie nicht, die eigene Rolle ändert man nicht). */}
        {/* ►►► **Die Rolle ist der ZUGANG** (Testnotiz #1043). ◄◄◄ «Lieferant» und
            «Kunde» standen hier und waren eine Aussage über **Vorgänge**: wer Partner
            einer Ausgabe ist, ist dort Lieferant, bei einer Einnahme Kunde – dieselbe
            Person kann beides sein. Übrig bleibt die eine Frage, die das Haus wirklich
            stellt (`people.STAFF_ROLES`). */}
        {canEdit ? (
          <SelectField label="Rolle" value={role} onChange={(x) => set('role', x as UserRole)} options={[
            { value: 'admin', label: 'Admin' }, { value: 'employee', label: 'Mitarbeiter' },
            { value: 'user', label: 'Benutzer' },
          ]} />
        ) : (
          <AField label="Rolle" value={ROLE_CFG[role]?.label ?? role} readOnly />
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <AField label="Vorname" value={form.first_name} onChange={str('first_name')} readOnly={ro} placeholder="Max" onEnter={saveNow} required={required('first_name')} />
          <AField label="Nachname" value={form.last_name} onChange={str('last_name')} readOnly={ro} placeholder="Muster" onEnter={saveNow} required={required('last_name')} />
          <AField label="Telefon" value={form.phone} onChange={str('phone')} readOnly={ro} type="tel" placeholder="+41 44 000 00 00" onEnter={saveNow} required={required('phone')} />
          <AField label="Geburtsdatum" value={form.date_of_birth} onChange={str('date_of_birth')} readOnly={ro} type="date" onEnter={saveNow} required={required('date_of_birth')} />
        </div>

      </Card>

      {/* ── 2. Adressen (privat) – dieselbe Maske wie im Konto ───────────────── */}
      <Card icon={MapPin} title="Adressen" anchor="adressen" extra={<TodoChip items={sectionItems(todo, 'adressen')} />}>
        <AddressBook owner={record.object_id ?? null} account="private"
          addresses={record.addresses ?? []} loginEmail={record.email} readOnly={ro}
          mapsKey={mapsKey} onSaved={onSaved} />
      </Card>

      {/* ── 3. Geschäftskonto ───────────────────────────────────────────────── */}
      {/* ►►► **Das Personal ordnet zu – aus den bestehenden Firmen.** ◄◄◄ Eine neue legt es
          über «+» im Feed an (Testnotiz #1214), nicht hier.
          Eine fremde Firma ist nur ihre Identität (Name, Rechtsform, UID); die Anschriften
          des Geschäftskontos gehören der Person. Für Personal muss die Firma eine unserer
          Gesellschaften sein (`people.assert_employment`). */}
      <Card icon={Building2} title="Geschäftskonto">
        <CompanyField company={record.company} readOnly={ro} search
          country={record.addresses?.[0]?.country}
          onLink={(id) => api.updateErpRecord(record.object_id as number,
            { company_object_id: id }).then(onSaved)} />
        {record.company && (
          <AddressBook owner={record.object_id ?? null} account="business"
            addresses={record.addresses ?? []} loginEmail={record.email} readOnly={ro}
            mapsKey={mapsKey} onSaved={onSaved} />
        )}
      </Card>

      {/* ── 4. Einwilligungen (der Chat oben heisst «Kommunikation») ─────────── */}
      <Card icon={Bell} title="Einwilligungen">
        {record.object_id != null && <NewsletterConsent person={record.object_id} />}
      </Card>

      {/* ── 5. System (ERP-Extra, read-only – Notiz #295) ───────────────────── */}
      <Card icon={Cog} title="System">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <AField label="E-Mail" value={record.email} readOnly />
          <AField label="Anmeldung" value={signInLabel(record.last_sign_in_provider)} readOnly />
          <AField label="Passkeys" value={passkeyLabel(record.passkey_count)} readOnly />
          <AField label="Letzter Login" value={when(record.last_login_at)} readOnly />
          <AField label="Erstellt" value={when(record.created_at)} readOnly />
          <AField label="Zuletzt geändert" value={when(record.updated_at)} readOnly />
          {isAdmin && (
            <div className="sm:col-span-2">
              <AField label="Firebase UID" value={record.firebase_uid} readOnly />
            </div>
          )}
        </div>
      </Card>
    </div>
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
  return provider ? (map[provider] ?? provider) : '—';
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

  // **Eine Person wird nicht deaktiviert – sie wechselt die Rolle** (Testnotiz #755).
  //
  // Wer das Unternehmen verlässt, hört nicht auf zu existieren: er wird vom Mitarbeiter
  // zum Kunden und darf weiter einkaufen. Ein Knopf, der eine Identität stilllegt, auf
  // die Aufträge, Instanzen und Belege zeigen, beantwortete eine Frage, die niemand
  // stellt. Gepflegt wird die **Rolle**, und zwar im Formular darunter – an derselben
  // Stelle wie jede andere Angabe der Person.

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242).
          Das runde Foto als `avatar`; die Objektnummer trägt der Kopf (darum steht sie –
          anders als im Profil – nicht noch einmal als Kachel im Formular). */}
      <DetailHeader
        type="user" title={hasName ? name : null} placeholder="Kein Name"
        objectId={record.object_id} onBack={onBack}
        status={rc}
        photoUrl={record.photo_url} initials={initials} todo={todo}
      />

      {/* ►►► **EINE Seite statt zwei Reiter.** ◄◄◄ Zuerst die Kommunikation – sie ist, was man
          an einer Person am häufigsten tut –, ohne eigenen Kasten; darunter die Stammdaten.
          **Dieselbe Breite wie jeder andere Datensatz** (Notiz #763): ohne sie lief das
          Formular auf einem breiten Schirm auseinander und eine Zeile wurde unlesbar lang. */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 40px', background: 'var(--bg-2)' }}>
        <DetailBody gap={24}>
          {record.object_id != null && (
            <section aria-label="Kommunikation" data-todo="kommunikation" style={{ scrollMarginTop: 16 }}>
              <Communication me={me}
                person={{ object_id: record.object_id, name: hasName ? name : record.email }} />
            </section>
          )}
          {/* ►►► **Zeiterfassung** – eigener Datensatz oder Admin, und nur für Personal. Der
              Server prüft es noch einmal (`timekeeping.may_see`). */}
          {record.object_id != null && isStaff(record.role)
            && (isAdmin || me?.object_id === record.object_id) && (
            <>
              <SectionSep label="Zeiterfassung" anchor="zeiterfassung" todo={sectionItems(todo, 'zeiterfassung')} />
              <TimeCard person={record.object_id} />
            </>
          )}
          {/* ►►► **Zahlungen** – jede Zahlung, in der diese Person Partei ist; eine
              Ableitung, keine Kopie. Ohne Zahlung kein Abschnitt. */}
          {payments != null && payments.length > 0 && (
            <>
              <SectionSep label="Zahlungen" anchor="zahlungen" tip={PAYMENTS_TIP}
                todo={sectionItems(todo, 'zahlungen')} />
              <PaymentList rows={payments} />
            </>
          )}
          {/* Dezent: hier beginnen die Stammdaten – eine Haarlinie mit dem Mikro-Label. */}
          <SectionSep label="Stammdaten" todo={sectionItems(todo, 'person', 'adressen')} />
          <ProfileForm key={record.object_id} record={record} isAdmin={isAdmin} onSaved={onSave} todo={todo} />
          <DocumentTiles objectId={record.object_id} />
        </DetailBody>
      </div>
    </div>
  );
}
