'use client';

/// <reference types="google.maps" />
import { useEffect, useRef } from 'react';
import { MapPin } from 'lucide-react';
import { useGoogleMaps } from './use-google-maps';

export type AutoAddress = {
  street: string; zip: string; city: string; country: string;
  lat?: number; lng?: number;
};

function parse(place: google.maps.places.PlaceResult): AutoAddress {
  const comps = place.address_components ?? [];
  const get = (type: string) => comps.find((c) => c.types.includes(type))?.long_name ?? '';
  const short = (type: string) => comps.find((c) => c.types.includes(type))?.short_name ?? '';
  const street = [get('route'), get('street_number')].filter(Boolean).join(' ').trim();
  const city = get('locality') || get('postal_town') || get('administrative_area_level_2');
  const loc = place.geometry?.location;
  return {
    street, zip: get('postal_code'), city,
    country: short('country') || get('country'),
    lat: loc ? loc.lat() : undefined, lng: loc ? loc.lng() : undefined,
  };
}

/**
 * Adress-Eingabe mit **Google-Places-Autovervollständigung**: der Nutzer tippt die Strasse,
 * wählt einen Vorschlag – Strasse/PLZ/Ort/Land (und Koordinaten) werden automatisch befüllt
 * (``onPick``). Ohne Google-Maps-Key (oder Ladefehler) verhält sich das Feld wie ein
 * normales Textfeld (``onChange``) – nie kaputt. Optik über ``className``/``style`` steuerbar,
 * damit es sich in jedes Formular einfügt.
 */
export function AddressAutocomplete({
  apiKey, value, onChange, onPick, placeholder, className, style, id, country,
}: {
  apiKey: string | null | undefined;
  value: string;
  onChange: (v: string) => void;
  onPick: (a: AutoAddress) => void;
  placeholder?: string;
  className?: string;
  style?: React.CSSProperties;
  id?: string;
  country?: string;   // optionale Länder-Vorfilterung (ISO-2), z. B. 'CH'
}) {
  const { loaded } = useGoogleMaps(apiKey);
  const inputRef = useRef<HTMLInputElement>(null);
  const acRef = useRef<google.maps.places.Autocomplete | null>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  useEffect(() => {
    if (!loaded || !inputRef.current || acRef.current || !google.maps.places) return;
    const ac = new google.maps.places.Autocomplete(inputRef.current, {
      fields: ['address_components', 'geometry'],
      types: ['address'],
      ...(country ? { componentRestrictions: { country } } : {}),
    });
    ac.addListener('place_changed', () => {
      const place = ac.getPlace();
      if (!place.address_components) return;
      const a = parse(place);
      if (a.street) onChange(a.street);       // Eingabefeld = Strasse
      onPickRef.current(a);
    });
    acRef.current = ac;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, country]);

  const baseStyle: React.CSSProperties = className ? {} : {
    width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #E2E8F0',
    fontSize: 14, color: '#0F172A', outline: 'none', boxSizing: 'border-box',
  };
  return (
    <div style={{ position: 'relative' }}>
      <input
        id={id}
        ref={inputRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className={className}
        style={{ ...baseStyle, ...style, paddingLeft: (style?.paddingLeft as number) ?? 30 }}
        // Enter im Autocomplete wählt den Vorschlag statt das Formular abzusenden.
        onKeyDown={(e) => { if (e.key === 'Enter' && document.querySelector('.pac-container:not([style*="display: none"])')) e.preventDefault(); }}
      />
      <MapPin size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
    </div>
  );
}
