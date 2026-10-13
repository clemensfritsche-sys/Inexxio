'use client';

import { useState, useEffect, useRef } from 'react';
import {
  User, MapPin, Building2, Briefcase, Bell, Check, Cog, UserRound, MessagesSquare,
} from 'lucide-react';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { Communication } from '@/components/erp/communication';
import { userDisplayName } from '@/lib/utils';
import { day, when } from '@/lib/when';
import { ROLE_CFG, userStatus } from '@/lib/record-status';
import { api } from '@/lib/api';
import { Card, DetailBody, DetailHeader } from '@/components/erp/fields';
// **ERP ist Master, das Profil ist der Spiegel** – und weil dem Nutzer Struktur, Logik
// und Namensgebung der Profileinstellungen besser gefallen (Notiz #294), übernimmt der
// Profil-Reiter hier **dieselben Bausteine** wie das Konto: EIN Formular, EIN Auto-Save,
// «Rechnungsadresse = Lieferadresse»-Schalter mit Spiegelung, Google-Adress-Suche. Keine
// zweite Optik, kein zweiter Feld-Satz – nur die ERP-Extras kommen dazu (Notiz #295:
// Rolle, admin-pflegbare Anstellung, System). Reuse statt Nachbau.
import { Field as AField, ToggleField, SelectField } from '@/components/account/field';
import { AddressBook } from '@/components/erp/address-book';
import { CompanyField } from '@/components/erp/company-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';
import type { UserProfile, UserRole } from '@/types';

// **Der Benutzer hat keine Reiter mehr** – aus demselben Befund, zweimal.
//
// «Bestellungen» rendete **gar nichts**: seine Karte hing am Verkaufs-Modul, und das ist
// mit dem Basis-Neuaufbau entfallen (docs/attic.md). «Dokumente» ebenso (Testnotiz #772):
// zwei Überschriften über leeren Flächen, denn das Dokumentenmodul gibt es nicht mehr.
// Übrig blieb genau ein Reiter, und der trägt das ganze Formular: es gibt hier nichts
// mehr zu wählen. Dieselbe Auflösung wie am Artikel (Notiz #760/#761) – dort war es
// dieselbe Ursache und nicht eine Regel über Reiter.
//
// Kommen die Bereiche zurück, kommen ihre Reiter mit ihnen.

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function userInitials(name: string, email: string): string {
  if (name && name !== email) {
    return name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }
  return email[0]?.toUpperCase() ?? '?';
}

// ─── Karten-Bausteine (Spiegel der Profileinstellungen) ────────────────────────
// Gleiche Anatomie wie `account/sections/profile-section.tsx`, damit «fast eine
// Spiegelung» entsteht (Notiz #294) – Symbol + Titel + optionaler rechter Slot. Die
// `Card` selbst wohnt im gemeinsamen Vokabular (`fields.tsx`), seit der Unternehmens-
// Datensatz dieselbe Anatomie nutzt; die alten `Field`/`Sec` (slate/blue-Altpalette,
// nur noch von dort genutzt) sind damit entfallen.

function SubBlock({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  return (
    <div style={{ padding: 16, background: 'var(--bg-2)', borderRadius: 10, border: '1px solid var(--border-1)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
        <Icon style={{ width: 13, height: 13, color: 'var(--fg-3)' }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

// ─── Formular (Spiegel des Profils + ERP-Extras) ───────────────────────────────

interface ERPForm {
  role: UserRole;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
  department: string;
  job_title: string;
  employment_start_date: string;
  weekly_hours: string;
  newsletter_opt_in: boolean;
}

type StrKey = { [K in keyof ERPForm]: ERPForm[K] extends string ? K : never }[keyof ERPForm];

function buildForm(p: UserProfile): ERPForm {
  return {
    role: p.role,
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
    department: p.department ?? '',
    job_title: p.job_title ?? '',
    employment_start_date: p.employment_start_date ?? '',
    weekly_hours: p.weekly_hours != null ? String(p.weekly_hours) : '',
    newsletter_opt_in: p.newsletter_opt_in ?? false,
  };
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/**
 * Form → Update-Payload.
 *
 * ►►► **Nur noch EINE Bedingung** (Testnotiz #1043): die **Anstellung** – sie gehört nicht
 * zu jedem Datensatz. Firma und Anschriften stehen nicht in diesem Formular: die Firma
 * wird zugeordnet (`CompanyField`), die Anschriften leben im Adressbuch (`AddressBook`),
 * jede mit ihrem eigenen Auto-Save.
 */
function mapUpdate(v: ERPForm): Partial<UserProfile> {
  const isStaff = v.role === 'employee' || v.role === 'admin';
  const data: Record<string, unknown> = {
    role: v.role,
    first_name: nn(v.first_name),
    last_name: nn(v.last_name),
    date_of_birth: nn(v.date_of_birth),
    phone: nn(v.phone),
    newsletter_opt_in: v.newsletter_opt_in,
  };
  if (isStaff) {
    // ►►► **Wer Mitarbeiter ist, gehört zu einer Gesellschaft** (Testnotiz #905). ◄◄◄
    //
    // Ohne sie kann ein Beleg nicht sagen, wer ihn stellt – er nähme still den Betreiber,
    // auch wenn eine Schwestergesellschaft fakturiert. **Die Regel steht im Dienst**
    // (`people.assert_employment`), nicht hier: sie gilt für jede Oberfläche, die diesen
    // Datensatz schreibt. Dies ist die freundliche Hälfte.
    data.department = nn(v.department);
    data.job_title = nn(v.job_title);
    data.employment_start_date = nn(v.employment_start_date);
    data.weekly_hours = nn(v.weekly_hours);
  }
  return data as Partial<UserProfile>;
}

function ProfileForm({ record, isAdmin, onSaved }: {
  record: UserProfile; isAdmin: boolean; onSaved: (u: UserProfile) => void;
}) {
  const canEdit = isAdmin;
  const ro = !canEdit;
  const mapsKey = useMapsApiKey();
  const [form, setForm] = useState<ERPForm>(() => buildForm(record));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | null | undefined>(undefined);

  // Nur bei Datensatz-Wechsel neu aufbauen (nicht bei jedem `record`-Prop) – sonst
  // klobbert ein Auto-Save → onSaved → neuer Prop die gerade getippte Eingabe.
  useEffect(() => {
    if (record.object_id !== prevId.current) {
      prevId.current = record.object_id;
      setForm(buildForm(record));
      setResetKey((k) => k + 1);
    }
  }, [record.object_id, record]);

  const { status, errorMsg, saveNow } = useAutosave(
    form,
    async (v) => {
      if (!canEdit || !record.object_id) return;
      const updated = await api.updateErpRecord(record.object_id, mapUpdate(v));
      onSaved(updated);
    },
    2500,
    resetKey,
  );

  function set<K extends keyof ERPForm>(key: K, value: ERPForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }
  const str = (k: StrKey) => (canEdit ? (val: string) => setForm((prev) => ({ ...prev, [k]: val })) : undefined);

  const role = form.role;
  const isStaff = role === 'employee' || role === 'admin';

  const termsDate = record.terms_accepted_at
    ? day(record.terms_accepted_at) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── 1. Persönliche Angaben ─────────────────────────────────────────── */}
      <Card icon={User} title="Person" right={canEdit ? <SaveStatusIndicator status={status} errorMsg={errorMsg} /> : undefined}>
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
          <AField label="Vorname" value={form.first_name} onChange={str('first_name')} readOnly={ro} placeholder="Max" onEnter={saveNow} />
          <AField label="Nachname" value={form.last_name} onChange={str('last_name')} readOnly={ro} placeholder="Muster" onEnter={saveNow} />
          <AField label="Telefon" value={form.phone} onChange={str('phone')} readOnly={ro} type="tel" placeholder="+41 44 000 00 00" onEnter={saveNow} />
          <AField label="Geburtsdatum" value={form.date_of_birth} onChange={str('date_of_birth')} readOnly={ro} type="date" onEnter={saveNow} />
        </div>

        {/* Anstellung: im Profil read-only, **im ERP admin-pflegbar** (Notiz #295 –
            «das ERP muss ALLES können»; ``ErpAdminUpdate`` erbt + ergänzt genau das). */}
        {isStaff && (
          <SubBlock icon={Briefcase} title="Anstellung">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label="Abteilung" value={form.department} onChange={str('department')} readOnly={ro} onEnter={saveNow} />
              <AField label="Funktion" value={form.job_title} onChange={str('job_title')} readOnly={ro} onEnter={saveNow} />
              <AField label="Eintrittsdatum" value={form.employment_start_date} onChange={str('employment_start_date')} readOnly={ro} type="date" onEnter={saveNow} />
              <AField label="Pensum (h/Woche)" value={form.weekly_hours} onChange={str('weekly_hours')} readOnly={ro} onEnter={saveNow} />
            </div>
          </SubBlock>
        )}

      </Card>

      {/* ── 2. Adressen (privat) – dieselbe Maske wie im Konto ───────────────── */}
      <Card icon={MapPin} title="Adressen">
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
            { company_object_id: id } as Partial<UserProfile>).then(onSaved)} />
        {record.company && (
          <AddressBook owner={record.object_id ?? null} account="business"
            addresses={record.addresses ?? []} loginEmail={record.email} readOnly={ro}
            mapsKey={mapsKey} onSaved={onSaved} />
        )}
      </Card>

      {/* ── 4. Kommunikation & Rechtliches ──────────────────────────────────── */}
      <Card icon={Bell} title="Kommunikation">
        {canEdit ? (
          <ToggleField label="Newsletter" description="Produktneuigkeiten und Angebote per E-Mail"
            checked={form.newsletter_opt_in} onChange={(x) => set('newsletter_opt_in', x)} />
        ) : (
          <AField label="Newsletter" value={form.newsletter_opt_in ? 'Abonniert' : 'Nicht abonniert'} readOnly />
        )}
        {/* Kein Schalter, sondern eine Tatsache (wie im Profil): die Rechtstexte sind
            akzeptiert. Die vollständige, versionierte Historie führt der Reiter «Dokumente». */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13, color: 'var(--fg-3)' }}>
          {termsDate && <Check size={15} style={{ color: 'var(--success)', flexShrink: 0 }} />}
          <span>
            {termsDate
              ? `AGB und Datenschutzerklärung akzeptiert am ${termsDate}${record.terms_version ? ` · v${record.terms_version}` : ''}`
              : 'AGB und Datenschutzerklärung noch nicht akzeptiert'}
          </span>
        </div>
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

// ─── Bestellungen (Reiter) ─────────────────────────────────────────────────────

// Die Karte «Bestellungen» ist mit dem Verkaufs-Modul entfallen (docs/attic.md).

type UserTab = 'person' | 'comm';

export function UserDetail({ record, onSave, isAdmin, onBack, me, messages }: {
  record: UserProfile;
  onSave: (u: UserProfile) => void;
  isAdmin: boolean;
  onBack: () => void;
  /** Wer gerade arbeitet – Absender einer neuen Nachricht. */
  me?: { object_id: number; name: string } | null;
  /** Offene Nachrichten im Verlauf – die Zahl am Symbol (wie im Feed). */
  messages?: { open: number; overdue: number } | null;
}) {
  const [tab, setTab] = useState<UserTab>('person');
  const rc       = userStatus(record);
  const name     = userDisplayName(record);
  const hasName  = !!name && name !== record.email;
  const initials = userInitials(name, record.email);

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
        photoUrl={record.photo_url} initials={initials} messages={messages}
        tabs={<DetailTabs<UserTab> active={tab} onChange={setTab} tabs={[
          { key: 'person', label: 'Person', icon: UserRound },
          { key: 'comm', label: 'Kommunikation', icon: MessagesSquare },
        ]} />}
      />

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 40px', background: 'var(--bg-2)' }}>
        {/* **Dieselbe Breite wie jeder andere Datensatz** (Notiz #763). Ohne sie lief das
            Formular auf einem breiten Schirm über die volle Fensterbreite auseinander –
            und eine Zeile wurde unlesbar lang. */}
        <DetailBody>
        {tab === 'person' && <ProfileForm record={record} isAdmin={isAdmin} onSaved={onSave} />}
        {tab === 'comm' && record.object_id != null && (
          <Communication me={me}
            person={{ object_id: record.object_id, name: hasName ? name : record.email }} />
        )}
        </DetailBody>
      </div>
    </div>
  );
}
