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
 *   4. **Kommunikation**     – Newsletter + Nachweis der akzeptierten Rechtstexte
 */

import { useState, useEffect, useRef } from 'react';
import { User, Briefcase, Building2, Bell, MapPin } from 'lucide-react';
import type { UserProfile } from '@/types';
import { day } from '@/lib/when';
import { Field, ToggleField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';
import { AddressBook } from '@/components/erp/address-book';
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
  // Kommunikation
  newsletter_opt_in: boolean;
}

function buildForm(p: UserProfile): Form {
  return {
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
    newsletter_opt_in: p.newsletter_opt_in ?? false,
  };
}

interface Props {
  profile: UserProfile;
  isEmployee: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isEmployee, onSave }: Props) {
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

  const { status, errorMsg, saveNow } = useAutosave(
    form,
    (v) => onSave({ ...v } as Partial<UserProfile>),
    3000,
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
          <div style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--fg-4)', marginBottom: 4 }}>
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

        {isEmployee && (
          <SubBlock icon={Briefcase} title="Anstellung · wird vom Administrator gepflegt">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Abteilung" value={profile.department ?? ''} readOnly />
              <Field label="Funktion" value={profile.job_title ?? ''} readOnly />
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
        <CompanyField company={profile.company} readOnly={isEmployee}
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
      <Card icon={Bell} title="Kommunikation">
        <ToggleField
          label="Newsletter"
          description="Produktneuigkeiten und Angebote per E-Mail"
          checked={form.newsletter_opt_in}
          onChange={(v) => set('newsletter_opt_in', v)}
        />
        {/* Der AGB-/Datenschutz-Nachweis ist hier entfallen (Testnotiz #325): **welche
            Fassung wann bestätigt wurde, gehört ins Dokumentenmanagement** – dort steht die
            Version als Objektnummer mit ihrer Historie, und dort werden auch die übrigen
            Pflichtdokumente geführt. Zwei Anzeigen derselben Tatsache liefen sonst
            auseinander, sobald die Dokument-Ansicht dazukommt (Reiter «Meine Dokumente»). */}
      </Card>
    </div>
  );
}

// ─── Bausteine ────────────────────────────────────────────────────────────────

function Card({ icon: Icon, title, right, children }: {
  icon: React.ElementType; title: string; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border-1)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid var(--border-1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon style={{ width: 16, height: 16, color: 'var(--fg-3)' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>{title}</h2>
        </div>
        {right}
      </div>
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>{children}</div>
    </div>
  );
}

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

