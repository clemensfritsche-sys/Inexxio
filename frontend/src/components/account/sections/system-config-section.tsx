'use client';

import { useState } from 'react';
import { Key } from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings } from '@/types';
import { Card, DetailBody } from '@/components/erp/fields';
import { Field } from '@/components/account/field';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';

/**
 * **Die Plattform-Konfiguration** – sie gilt der EINEN Website, nicht je Gesellschaft,
 * und steht darum nur am Betreiber-Datensatz.
 *
 * Es sind genau zwei Schlüssel, und beide haben einen Leser: die Plausible-Domain
 * (`components/analytics/plausible.tsx` – ohne sie lädt kein Analytics-Skript) und den
 * Google-Maps-Schlüssel (`components/erp/use-maps-key.ts` – die Adress-Suche in jedem
 * Adressfeld). Was hier steht, muss etwas bewirken; ein Feld auf Vorrat sieht aus wie
 * eine Stellschraube und dreht an nichts.
 *
 * Anatomie und Speicherweg sind dieselben wie im Reiter «Stammdaten» daneben – Karte,
 * Feld, Auto-Save, Anzeige im Karten-Kopf. Ein eigenes Formular mit Speichern-Knopf wäre
 * ein zweiter Bedien-Massstab in demselben Fenster.
 */
export function SystemConfigSection({ settings, onSaved }: {
  settings: CompanySettings;
  onSaved?: (s: CompanySettings) => void;
}) {
  const [form, setForm] = useState({
    plausible_domain: settings.plausible_domain ?? '',
    google_maps_api_key: settings.google_maps_api_key ?? '',
  });

  const { status, errorMsg, saveNow } = useAutosave(form, async (v) => {
    const updated = await api.updateSettings({
      plausible_domain: v.plausible_domain.trim() || null,
      google_maps_api_key: v.google_maps_api_key.trim() || null,
    });
    onSaved?.(updated);
  });

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <DetailBody gap={16}>
      <Card icon={Key} title="Integrationen"
        right={<SaveStatusIndicator status={status} errorMsg={errorMsg} />}>
        <Field label="Plausible Domain" value={form.plausible_domain}
          onChange={set('plausible_domain')} onEnter={saveNow}
          placeholder="inexxio.com"
          hint="Ohne Domain lädt kein Analytics-Skript – und ohne Statistik-Einwilligung ebenfalls nicht." />
        <Field label="Google Maps API-Schlüssel" value={form.google_maps_api_key}
          onChange={set('google_maps_api_key')} onEnter={saveNow}
          placeholder="AIza…"
          hint="Für die Adress-Suche in jedem Adressfeld. Maps JavaScript API + Geocoding API aktivieren und auf die Domain einschränken." />
      </Card>
    </DetailBody>
  );
}
