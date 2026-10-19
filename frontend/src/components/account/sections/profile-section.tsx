'use client';

/**
 * **Mein Profil – EINE Sektion, vier Container.**
 *
 * Vorher lagen dieselben Daten in vier Karten mit vier Auto-Saves (Profil, Adresse,
 * Rechnungsadresse, Datenschutz) – und die Rechnungsadresse spiegelte den Profil-Stand
 * aus dem `profile`-Prop, hinkte also jeder noch nicht gespeicherten Änderung hinterher.
 *
 * Jetzt: ein Formular, ein Auto-Save, eine Rückmeldung. Gruppiert nach dem, was fachlich
 * zusammengehört:
 *   1. **Person**            – wer bin ich (inkl. Telefon; + Anstellung)
 *   2. **Adressen**          – privat: Adresse, optional Rechnungsadresse und weitere
 *                              Lieferadressen
 *   3. **Geschäftskonto**    – optional: die Firma (genannt, nie gesucht) und dieselbe
 *                              Adress-Maske, dazu die Rechnungs-E-Mail
 *   4. **Kommunikation**     – Newsletter: ein eigener Schalter, sofort geschrieben (kein
 *                              Feld dieses Formulars – die Einwilligung ist ein Nachweis)
 */

import { useState, useEffect, useRef } from 'react';
import { User, Briefcase, Building2, Bell, MapPin } from 'lucide-react';
import type { NewsletterState, UserProfile } from '@/types';
import { api } from '@/lib/api';
import { day } from '@/lib/when';
import { Field, ToggleField } from '@/components/form/field';
import { useAutosaveValue } from '@/lib/use-autosave';
import { SaveStatusIndicator } from '@/components/form/save-status';
import { AddressBook } from '@/components/erp/address-book';
import { Card, MICRO_LABEL, SubBlock } from '@/components/erp/fields';
import { CompanyField } from '@/components/erp/company-field';
import { useQueryClient } from '@tanstack/react-query';
import { useMapsApiKey } from '@/components/erp/use-maps-key';

interface Form {
  // Person
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
  // ►►► **Die Anschriften stehen im Adressbuch** (`AddressBook`) – nicht in diesem
  // Formular: jede ist ein eigener Eintrag mit eigenem Auto-Save.
}

function buildForm(p: UserProfile): Form {
  return {
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
  };
}

interface Props {
  profile: UserProfile;
  isStaff: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isStaff, onSave }: Props) {
  const [form, setForm] = useState<Form>(() => buildForm(profile));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | undefined>(undefined);
  const mapsKey = useMapsApiKey();
  const qc = useQueryClient();

  useEffect(() => {
    if (profile.id !== prevId.current) {
      prevId.current = profile.id;
      setForm(buildForm(profile));
      setResetKey((k) => k + 1);
    }
  }, [profile.id, profile]);

  const { status, errorMsg, saveNow } = useAutosaveValue(
    form,
    (v) => onSave({ ...v } as Partial<UserProfile>),
    resetKey,
  );

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const objectNumber = profile.object_id != null
    ? String(profile.object_id).padStart(9, '0')
    : String(profile.id);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── 1. Persönliche Angaben ─────────────────────────────────────────── */}
      <Card icon={User} title="Person" right={<SaveStatusIndicator status={status} errorMsg={errorMsg} />}>
        {/* Die Objektnummer ist vergeben und unveränderlich – sie wie ein Formularfeld
            zu zeigen, lud zum Hineinklicken ein. Jetzt steht sie da wie überall sonst
            im System: Versalien-Label + monospaced Nummer. */}
        <div>
          <div style={{ ...MICRO_LABEL, marginBottom: 4 }}>
            Benutzernummer
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
            {objectNumber}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)} placeholder="Max" required={!form.first_name.trim()} onEnter={saveNow} />
          <Field label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)} placeholder="Muster" required={!form.last_name.trim()} onEnter={saveNow} />
          <Field label="Telefon" value={form.phone} onChange={(v) => set('phone', v)} placeholder="+41 44 000 00 00" type="tel" required={!form.phone.trim()} onEnter={saveNow} />
          <Field label="Geburtsdatum" value={form.date_of_birth} onChange={(v) => set('date_of_birth', v)} type="date" onEnter={saveNow} />
        </div>

        {isStaff && (
          <SubBlock icon={Briefcase} title="Anstellung · wird vom Administrator gepflegt">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Eintrittsdatum" value={profile.employment_start_date ? day(profile.employment_start_date) : ''} readOnly />
              <Field label="Pensum" value={profile.weekly_hours ? `${profile.weekly_hours}h / Woche` : ''} readOnly />
            </div>
          </SubBlock>
        )}
      </Card>

      {/* ── 2. Adressen (privat) ─────────────────────────────────────────── */}
      {/* ►►► **Eine Adresse, optional eine abweichende Lieferadresse und weitere
          Lieferadressen.** ◄◄◄ Privat geht die Rechnung an die E-Mail der Person. */}
      <Card icon={MapPin} title="Adressen">
        <AddressBook owner={null} account="private" addresses={profile.addresses ?? []}
          loginEmail={profile.email} mapsKey={mapsKey}
          onSaved={(u) => qc.setQueryData(['me'], u)} />
      </Card>

      {/* ── 3. Geschäftskonto (optional) ─────────────────────────────────────── */}
      {/* ►►► **Dieselbe Maske noch einmal – für die Firma.** ◄◄◄ Die Firma wird genannt
          (UID, sonst Name und Rechtsform) und vom Server erkannt oder angelegt; eine Liste
          fremder Firmen sieht ein Kunde nie. Die Anschriften gehören der Person, die
          Rechnungs-E-Mail steht an der Rechnungsadresse. */}
      <Card icon={Building2} title="Geschäftskonto">
        <CompanyField company={profile.company} readOnly={isStaff}
          country={profile.addresses?.[0]?.country}
          onLink={(id) => onSave({ company_object_id: id } as Partial<UserProfile>)}
          onCreate={(nc) => onSave({ new_company: nc } as Partial<UserProfile>)} />
        {profile.company && (
          <AddressBook owner={null} account="business" addresses={profile.addresses ?? []}
            loginEmail={profile.email} mapsKey={mapsKey}
            onSaved={(u) => qc.setQueryData(['me'], u)} />
        )}
      </Card>

      {/* ── 4. Kommunikation & Rechtliches ──────────────────────────────────── */}
      <Card icon={Bell} title="Kommunikation"><Newsletter /></Card>
    </div>
  );
}

/** ►►► **Der Newsletter – ein Schalter, sofort geschrieben.** ◄◄◄ Die Adresse ist im Konto
 *  bestätigt, darum ohne zweiten Klick. Neben dem Schalter steht der Satz, dem man
 *  zustimmt – derselbe, der als Nachweis gespeichert wird (vom Server). */
function Newsletter() {
  const [state, setState] = useState<NewsletterState | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.myNewsletter().then(setState).catch(() => {}); }, []);
  const flip = (on: boolean) => {
    setError(null);
    api.setMyNewsletter(on).then(setState)
      .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht gespeichert werden.'));
  };
  return (
    <div style={{ minHeight: 44 }}>
      <ToggleField label="Newsletter" description={state?.wording ?? ''}
        checked={!!state?.subscribed} onChange={(v) => { if (state) flip(v); }} />
      {state?.subscribed && state.since && (
        <p style={{ fontSize: 12, color: 'var(--fg-3)', margin: '6px 0 0' }}>Angemeldet seit {day(state.since)}</p>
      )}
      {error && <p style={{ fontSize: 12, color: 'var(--danger)', margin: '6px 0 0' }}>{error}</p>}
    </div>
  );
}
