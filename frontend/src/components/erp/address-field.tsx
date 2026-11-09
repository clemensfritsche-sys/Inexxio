'use client';

/**
 * **Adresse = EIN Feld.** Die eine Adress-Eingabe für das ganze System:
 *   1. **Leer → nur ein Suchfeld** (Google); ein Treffer füllt alles in einem Zug.
 *   2. **Gefüllt → Zusammenfassung, nicht editierbar** + «Ändern» (= neue Suche).
 *   3. **«Adresse nicht gefunden?» → manuell erfassen** für die echten Ausnahmen.
 * Ohne Google-Key oder bei Ladefehler: manueller Modus mit Hinweis.
 */

import { useEffect, useRef, useState } from 'react';
import { MapPin, Pencil, Search, CheckCircle2, LocateFixed, Loader2 } from 'lucide-react';
import { useGoogleMaps } from '@/lib/use-google-maps';
import { Input, Select } from '@/components/form/field';
import { RequiredMark } from '@/components/erp/controls';

export type Address = {
  /** Strasse inkl. Hausnummer – genau so, wie Google sie liefert (eine Zeile). */
  street: string;
  /** Zusatz (c/o, Postfach) – rein manuell, Google liefert das nicht. */
  street2?: string;
  zip: string;
  city: string;
  region?: string;
  /** Je nach Aufrufer ISO-2 («CH») oder Klarname («Schweiz») – siehe `countryOptions`. */
  country: string;
  lat?: number;
  lng?: number;
};

// Google liefert das Land als ISO-2, die Aufrufer führen ISO-2 (Person) oder Klarname
// (Firma): beides auf ISO-2 bringen, damit ein Treffer die richtige Option trifft.
const _TO_ISO2: Record<string, string> = {
  schweiz: 'CH', switzerland: 'CH', suisse: 'CH', svizzera: 'CH',
  deutschland: 'DE', germany: 'DE',
  österreich: 'AT', osterreich: 'AT', austria: 'AT',
  frankreich: 'FR', france: 'FR',
  italien: 'IT', italy: 'IT', italia: 'IT',
  liechtenstein: 'LI',
  usa: 'US', 'united states': 'US', 'united states of america': 'US', 'vereinigte staaten': 'US',
  grossbritannien: 'GB', 'united kingdom': 'GB', 'vereinigtes königreich': 'GB', 'great britain': 'GB',
  spanien: 'ES', spain: 'ES', niederlande: 'NL', netherlands: 'NL',
  belgien: 'BE', belgium: 'BE', luxemburg: 'LU', luxembourg: 'LU',
  portugal: 'PT', irland: 'IE', ireland: 'IE', finnland: 'FI', finland: 'FI',
  schweden: 'SE', sweden: 'SE', dänemark: 'DK', denmark: 'DK', polen: 'PL', poland: 'PL',
};

export function toIso2(country: string | null | undefined): string {
  const c = (country ?? '').trim();
  if (!c) return '';
  return _TO_ISO2[c.toLowerCase()] ?? (c.length === 2 ? c.toUpperCase() : c);
}

type PlacePick = {
  street: string; zip: string; city: string; region: string; country: string;
  lat?: number; lng?: number;
};

export function parsePlace(place: google.maps.places.PlaceResult): PlacePick {
  const comps = place.address_components ?? [];
  const get = (t: string) => comps.find((c) => c.types.includes(t))?.long_name ?? '';
  const short = (t: string) => comps.find((c) => c.types.includes(t))?.short_name ?? '';
  const loc = place.geometry?.location;
  return {
    street: [get('route'), get('street_number')].filter(Boolean).join(' ').trim(),
    zip: get('postal_code'),
    city: get('locality') || get('postal_town') || get('administrative_area_level_2'),
    // Region = Kanton bzw. Bundesstaat, kurz vor lang («ZH», nicht «Zürich»).
    region: short('administrative_area_level_1') || get('administrative_area_level_1'),
    country: short('country') || get('country'),
    lat: loc ? loc.lat() : undefined,
    lng: loc ? loc.lng() : undefined,
  };
}

export function hasAddress(a: Address | null | undefined): boolean {
  return !!a && !!(a.street?.trim() || a.zip?.trim() || a.city?.trim());
}

export function AddressField({
  value, onChange, apiKey, countryOptions, showStreet2 = false, showRegion = false,
  label = 'Adresse', required = false, look = 'erp',
}: {
  value: Address;
  onChange: (a: Address) => void;
  apiKey: string | null | undefined;
  /** Auswahl für den manuellen Modus. `[value, label]`; bestimmt auch das Format von `country`. */
  countryOptions: [string, string][];
  showStreet2?: boolean;
  showRegion?: boolean;
  label?: string;
  /** Pflichtangabe – markiert die Beschriftung, solange nichts erfasst ist (wie `Field`). */
  required?: boolean;
  /** `kt` = Gestaltung des Kontos (graue Flächen, `.kt-*`) – dieselbe Logik, andere Haut. */
  look?: 'erp' | 'kt';
}) {
  const kt = look === 'kt';
  const S = kt ? KT : ST;
  const { loaded, error } = useGoogleMaps(apiKey);
  const usable = loaded && !error;
  /**
   * ►►► **Der Modus ist eine ABLEITUNG, kein Einbahn-Schalter** ◄◄◄ – der Schlüssel kommt
   * später an. Manuell ist, wer es will oder wer keine Suche hat; solange offen ist, ob es
   * einen Schlüssel gibt (`pending`), steht die Suche da.
   */
  const [wantsManual, setWantsManual] = useState(false);
  const pending = !loaded && !error;
  const manual = wantsManual || (!usable && !pending);
  const [searching, setSearching] = useState(!hasAddress(value));
  const [street2Open, setStreet2Open] = useState(false);
  const [query, setQuery] = useState('');
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const valueRef = useRef(value);
  valueRef.current = value;

  const missing = required && !hasAddress(value);
  const labelNode = (
    <span style={S.label}>
      {label}
      {missing && <RequiredMark />}
    </span>
  );

  /** **Standort verwenden**: GPS → Geocoder → derselbe Zweig wie ein Suchtreffer (`applyPlace`). */
  function useMyLocation() {
    if (!usable || !navigator.geolocation) return;
    setLocating(true); setLocateError(null);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        new google.maps.Geocoder().geocode(
          { location: { lat: coords.latitude, lng: coords.longitude } },
          (results, status) => {
            setLocating(false);
            const hit = status === 'OK' ? results?.[0] : null;
            if (!hit?.address_components) {
              setLocateError('Zu diesem Standort wurde keine Adresse gefunden.');
              return;
            }
            applyPlace(hit);
          },
        );
      },
      () => {
        setLocating(false);
        setLocateError('Standort nicht verfügbar – bitte im Browser freigeben.');
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  /** Ein Google-Treffer (Vorschlag ODER GPS-Rückwärtssuche) → Adressfelder. EINE Stelle. */
  function applyPlace(place: google.maps.places.PlaceResult | google.maps.GeocoderResult) {
    const p = parsePlace(place as google.maps.places.PlaceResult);
    // Den Options-Wert übernehmen, der dem Google-Land entspricht; sonst den Google-Code –
    // nie still das alte Land.
    const matched = countryOptions.find(([v]) => toIso2(v) === toIso2(p.country));
    onChangeRef.current({
      ...valueRef.current,
      street: p.street, zip: p.zip, city: p.city,
      // Auch leer überschreibt: ein Treffer ersetzt die ganze Anschrift.
      region: p.region,
      country: matched ? matched[0] : (p.country || valueRef.current.country),
      lat: p.lat, lng: p.lng,
    });
    setSearching(false);
    setQuery('');
  }

  // Als Ref, damit der Autocomplete-Effekt nicht bei jedem Render neu aufgesetzt wird.
  const applyPlaceRef = useRef(applyPlace);
  applyPlaceRef.current = applyPlace;

  useEffect(() => {
    if (!usable || manual || !searching || !inputRef.current || !google.maps.places) return;
    const ac = new google.maps.places.Autocomplete(inputRef.current, {
      fields: ['address_components', 'geometry'],
      types: ['address'],
    });
    const listener = ac.addListener('place_changed', () => {
      const place = ac.getPlace();
      if (!place.address_components) return;
      applyPlaceRef.current(place);
    });
    return () => listener.remove();
  }, [usable, manual, searching, countryOptions]);

  const set = (k: keyof Address) => (v: string) => onChange({ ...value, [k]: v });

  // ── Manueller Modus: die klassischen Felder, bewusst gewählt ────────────────────
  if (manual) {
    return (
      <div style={S.wrap}>
        <div style={S.head}>
          {!kt && <MapPin size={14} style={{ color: 'var(--fg-3)' }} />}
          {labelNode}
          {usable && (
            <button type="button" onClick={() => { setWantsManual(false); setSearching(true); }} style={S.link}>
              <Search size={12} /> Stattdessen suchen
            </button>
          )}
        </div>
        {error === 'auth' && (
          <p style={S.note}>Adress-Suche nicht verfügbar (Google «Places API» nicht freigeschaltet) – bitte manuell erfassen.</p>
        )}
        <div style={S.grid}>
          <Line name="street" kt={kt} label="Strasse und Hausnummer" value={value.street} onChange={set('street')} wide />
          {showStreet2 && <Line name="street2" kt={kt} label="Adresszusatz" value={value.street2 ?? ''} onChange={set('street2')} wide />}
          <Line name="zip" kt={kt} label="PLZ" value={value.zip} onChange={set('zip')} />
          <Line name="city" kt={kt} label="Ort" value={value.city} onChange={set('city')} />
          {showRegion && <Line name="region" kt={kt} label="Region" value={value.region ?? ''} onChange={set('region')} />}
          <Pick name="country" kt={kt} label="Land" value={value.country} onChange={set('country')} options={countryOptions} />
        </div>
      </div>
    );
  }

  // ── Suchmodus: EIN Feld, der Standardweg ───────────────────────────────────────
  if (searching || !hasAddress(value)) {
    return (
      <div style={S.wrap}>
        <div style={S.head}>
          {!kt && <MapPin size={14} style={{ color: 'var(--fg-3)' }} />}
          {labelNode}
          {hasAddress(value) && (
            <button type="button" onClick={() => setSearching(false)} style={S.link}>Abbrechen</button>
          )}
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={kt ? 18 : 14} style={S.searchIcon} />
          {/* eslint-disable-next-line no-restricted-syntax -- Suchfeld (Google Places): der Text sucht eine Anschrift, er ist nicht ihr Wert. */}
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Adresse suchen – z. B. Musterstrasse 12, Zürich"
            autoComplete="off"
            className={kt ? 'kt-input' : undefined}
            style={S.search}
            // Enter wählt den Vorschlag, statt das Formular abzuschicken.
            onKeyDown={(e) => {
              if (e.key === 'Enter' && document.querySelector('.pac-container:not([style*="display: none"])')) {
                e.preventDefault();
              }
            }}
          />
        </div>
        {/* Zwei Auswege: der eigene Standort und die manuelle Erfassung. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {usable && typeof navigator !== 'undefined' && 'geolocation' in navigator && (
            <button type="button" onClick={useMyLocation} disabled={locating} style={S.locate}>
              {locating ? <Loader2 size={13} className="animate-spin" /> : <LocateFixed size={13} />}
              {locating ? 'Standort wird ermittelt…' : 'Aktuellen Standort verwenden'}
            </button>
          )}
          <button type="button" onClick={() => setWantsManual(true)} style={S.escape}>
            Adresse nicht gefunden? Manuell erfassen
          </button>
        </div>
        {locateError && <p style={{ ...S.note, color: 'var(--warning)' }}>{locateError}</p>}
      </div>
    );
  }

  // ── Gefüllt: kompakte Zusammenfassung, nicht editierbar ────────────────────────
  // Label über exakten Wert ODER ISO-2-Gleichheit («US» → «USA»).
  const countryLabel =
    countryOptions.find(([v]) => v === value.country)?.[1]
    ?? countryOptions.find(([v]) => toIso2(v) === toIso2(value.country))?.[1]
    ?? value.country;
  return (
    <div style={S.wrap}>
      <div style={S.head}>
        {!kt && <MapPin size={14} style={{ color: 'var(--fg-3)' }} />}
        {labelNode}
        <button type="button" onClick={() => setSearching(true)} style={S.link}>
          <Pencil size={12} /> Ändern
        </button>
      </div>
      <div style={S.summary}>
        <CheckCircle2 size={15} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 1 }} />
        <div style={{ minWidth: 0 }}>
          <div style={S.line1}>{value.street}</div>
          {showStreet2 && value.street2 && <div style={S.line2}>{value.street2}</div>}
          <div style={S.line2}>{[value.zip, value.city].filter(Boolean).join(' ')}</div>
          {showRegion && value.region && <div style={S.line2}>{value.region}</div>}
          <div style={S.line2}>{countryLabel}</div>
        </div>
      </div>
      {/* Adresszusatz nur, wenn befüllt oder ausdrücklich gewünscht. */}
      {showStreet2 && (value.street2 || street2Open ? (
        <Line name="street2" kt={kt} label="Adresszusatz (c/o, Postfach)" value={value.street2 ?? ''} onChange={set('street2')} wide />
      ) : (
        <button type="button" onClick={() => setStreet2Open(true)} style={S.escape}>
          + Adresszusatz
        </button>
      ))}
    </div>
  );
}

// ─── Bausteine ────────────────────────────────────────────────────────────────────

function Line({ name, label, value, onChange, wide, kt }: {
  name: keyof Address; label: string; value: string; onChange: (v: string) => void; wide?: boolean; kt?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: kt ? 6 : 4, gridColumn: wide ? '1 / -1' : undefined }}>
      <label style={(kt ? KT : ST).fieldLabel}>{label}</label>
      <Input name={name} value={value} onChange={onChange}
        className={kt ? 'kt-input' : undefined} style={kt ? undefined : ST.input} />
    </div>
  );
}

function Pick({ name, label, value, onChange, options, kt }: {
  name: keyof Address; label: string; value: string; onChange: (v: string) => void; options: [string, string][]; kt?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: kt ? 6 : 4 }}>
      <label style={(kt ? KT : ST).fieldLabel}>{label}</label>
      <Select name={name} value={value} onChange={onChange}
        className={kt ? 'kt-input kt-select' : undefined} style={kt ? undefined : ST.input}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </Select>
    </div>
  );
}

const ST: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 8 },
  head: { display: 'flex', alignItems: 'center', gap: 7 },
  label: { font: '600 13px var(--font-body)', color: 'var(--fg-2)' },
  link: {
    marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4,
    font: '600 12px var(--font-body)', color: 'var(--accent)',
    background: 'none', border: 'none', padding: 0, cursor: 'pointer',
  },
  search: {
    width: '100%', padding: '10px 12px 10px 34px', borderRadius: 'var(--r-md)',
    border: '1px solid var(--border-1)', background: 'var(--bg-1)',
    font: '400 14px var(--font-body)', color: 'var(--fg-1)', outline: 'none', boxSizing: 'border-box',
  },
  searchIcon: {
    position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
    color: 'var(--fg-4)', pointerEvents: 'none',
  },
  escape: {
    alignSelf: 'flex-start', font: '400 12px var(--font-body)', color: 'var(--fg-4)',
    background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline',
    textUnderlineOffset: 2,
  },
  locate: {
    display: 'inline-flex', alignItems: 'center', gap: 5,
    font: '600 12px var(--font-body)', color: 'var(--accent)',
    background: 'none', border: 'none', padding: 0, cursor: 'pointer',
  },
  summary: {
    display: 'flex', gap: 9, padding: '11px 13px', borderRadius: 'var(--r-md)',
    border: '1px solid var(--border-1)', background: 'var(--bg-2)',
  },
  line1: { font: '600 13.5px var(--font-body)', color: 'var(--fg-1)' },
  line2: { font: '400 13px var(--font-body)', color: 'var(--fg-3)' },
  note: { font: '400 12px var(--font-body)', color: 'var(--fg-4)', margin: 0 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 },
  fieldLabel: { font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' },
  input: {
    width: '100%', padding: '8px 11px', borderRadius: 'var(--r-md)',
    border: '1px solid var(--border-1)', background: 'var(--bg-1)',
    font: '400 13.5px var(--font-body)', color: 'var(--fg-1)', outline: 'none', boxSizing: 'border-box',
  },
};

/** Dieselben Teile in der Gestaltung des Kontos: graue Flächen ohne Rahmen, ruhige Wörter. */
const KT: Record<string, React.CSSProperties> = {
  ...ST,
  wrap: { display: 'flex', flexDirection: 'column', gap: 10 },
  head: { display: 'flex', alignItems: 'center', gap: 8, minHeight: 20 },
  label: { font: '500 13px var(--font-body)', color: 'var(--fg-3)' },
  link: {
    marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6,
    font: '500 13px var(--font-body)', color: 'var(--fg-1)', textDecoration: 'underline',
    textUnderlineOffset: 3, background: 'none', border: 'none', padding: 0, cursor: 'pointer',
  },
  search: { paddingLeft: 48 },
  searchIcon: {
    position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)',
    color: 'var(--fg-3)', pointerEvents: 'none',
  },
  escape: {
    alignSelf: 'flex-start', font: '400 13px var(--font-body)', color: 'var(--fg-3)',
    background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline',
    textUnderlineOffset: 3,
  },
  locate: {
    display: 'inline-flex', alignItems: 'center', gap: 6, height: 36, padding: '0 14px',
    borderRadius: 999, border: '1px solid var(--border-2)', background: 'var(--bg-1)',
    font: '500 13px var(--font-body)', color: 'var(--fg-1)', cursor: 'pointer',
  },
  summary: { display: 'flex', gap: 10, padding: '14px 16px', borderRadius: 14, background: 'var(--bg-1)' },
  line1: { font: '500 15px var(--font-body)', color: 'var(--fg-1)' },
  line2: { font: '400 14px var(--font-body)', color: 'var(--fg-3)' },
  note: { font: '400 13px var(--font-body)', color: 'var(--fg-3)', margin: 0 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 },
  fieldLabel: { font: '500 13px var(--font-body)', color: 'var(--fg-3)' },
};
