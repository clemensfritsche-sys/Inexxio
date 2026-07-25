'use client';

/**
 * **Orts-Wähler** – setzt einen Standort als Adresse/GPS, ohne dass dafür ein eigener
 * Datensatz angelegt werden muss.
 *
 * Ein Standort ist ein **Halter**: Ort | Person | Instanz | Unternehmen. Drei davon tragen
 * eine Objektnummer und sind scannbar; der **Ort** ist die reine Adresse und wird hier
 * erfasst – Strasse tippen (Google-Places-Vorschlag) oder auf der Karte setzen. Genau hier
 * gehört der Karten-Picker hin (nicht an den Artikel: ein Artikel ist eine Spezifikation).
 */

import { useState } from 'react';
import { MapPin, Check, X } from 'lucide-react';
import type { Place } from '@/types';
import { AddressAutocomplete, type AutoAddress } from '@/components/erp/address-autocomplete';
import { MapPicker, type ParsedAddress } from '@/components/erp/map-picker';
import { useMapsApiKey } from '@/components/erp/use-maps-key';

export function PlacePicker({ initial, onPick, onCancel }: {
  initial?: Place | null;
  onPick: (place: Place) => void;
  onCancel: () => void;
}) {
  const mapsApiKey = useMapsApiKey();
  const [name, setName] = useState(initial?.name ?? '');
  const [street, setStreet] = useState(initial?.street1 ?? '');
  const [zip, setZip] = useState(initial?.zip ?? '');
  const [city, setCity] = useState(initial?.city ?? '');
  const [country, setCountry] = useState(initial?.country ?? 'CH');
  const [lat, setLat] = useState<number | null>(initial?.lat ?? null);
  const [lng, setLng] = useState<number | null>(initial?.lng ?? null);

  // Ein Ort braucht mindestens EINE inhaltliche Angabe (sonst wäre er bedeutungslos) –
  // dieselbe Regel wie im Backend (`schemas/place.py`).
  const usable = !!(name.trim() || street.trim() || zip.trim() || city.trim() || (lat != null && lng != null));

  function applyAddress(a: AutoAddress | ParsedAddress, la?: number, ln?: number) {
    if (a.street) setStreet(a.street);
    if (a.zip) setZip(a.zip);
    if (a.city) setCity(a.city);
    if (a.country) setCountry(a.country);
    if (la != null) setLat(la);
    if (ln != null) setLng(ln);
  }

  function confirm() {
    if (!usable) return;
    onPick({
      name: name.trim() || null,
      street1: street.trim() || null,
      zip: zip.trim() || null,
      city: city.trim() || null,
      country: country.trim() || 'CH',
      lat, lng,
    });
  }

  return (
    <div style={{
      border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', padding: '12px 14px',
      display: 'flex', flexDirection: 'column', gap: 10, background: 'var(--bg-2)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <MapPin size={15} style={{ color: 'var(--inexxio-red)' }} />
        <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--fg-1)' }}>Ort wählen</span>
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Adresse oder Karte – kein Datensatz nötig</span>
        <button type="button" onClick={onCancel} aria-label="Abbrechen"
          style={{ marginLeft: 'auto', border: 'none', background: 'none', color: 'var(--fg-3)', cursor: 'pointer', display: 'flex' }}>
          <X size={16} />
        </button>
      </div>

      <label style={lbl}>Bezeichnung <span style={{ fontWeight: 400, textTransform: 'none' }}>(optional)</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Baustelle Müller"
          style={inp} />
      </label>

      <AddressAutocomplete
        apiKey={mapsApiKey}
        value={street}
        onChange={setStreet}
        onPick={(a) => applyAddress(a, a.lat, a.lng)}
        placeholder="Strasse und Nummer"
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(96px, 1fr))', gap: 8 }}>
        <label style={lbl}>PLZ<input value={zip} onChange={(e) => setZip(e.target.value)} style={inp} /></label>
        <label style={lbl}>Ort<input value={city} onChange={(e) => setCity(e.target.value)} style={inp} /></label>
        <label style={lbl}>Land<input value={country} onChange={(e) => setCountry(e.target.value)} style={inp} /></label>
      </div>

      <MapPicker apiKey={mapsApiKey} lat={lat} lng={lng}
        onPick={(la, ln, address) => { setLat(la); setLng(ln); if (address) applyAddress(address); }} />

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button type="button" onClick={onCancel} style={btn(false)}>Abbrechen</button>
        <button type="button" onClick={confirm} disabled={!usable} style={btn(true, !usable)}>
          <Check size={14} /> Ort übernehmen
        </button>
      </div>
    </div>
  );
}

const lbl: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10.5, fontWeight: 600,
  color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.03em',
};
const inp: React.CSSProperties = {
  fontSize: 12.5, padding: '7px 9px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)',
  background: 'var(--bg-1)', color: 'var(--fg-1)', textTransform: 'none', letterSpacing: 'normal', fontWeight: 400,
};
function btn(primary: boolean, disabled = false): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px',
    borderRadius: 'var(--r-sm)', fontSize: 12.5, fontWeight: 600,
    border: primary ? 'none' : '1px solid var(--border-1)',
    background: primary ? 'var(--inexxio-red)' : 'var(--bg-1)',
    color: primary ? '#fff' : 'var(--fg-2)',
    opacity: disabled ? 0.5 : 1, cursor: disabled ? 'not-allowed' : 'pointer',
  };
}
