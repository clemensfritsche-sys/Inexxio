'use client';

/**
 * **Adresse = EIN Feld.** Die eine Adress-Eingabe für das ganze System.
 *
 * Vorher stand überall dieselbe Reihe aus fünf Eingaben (Strasse · Hausnummer · PLZ ·
 * Ort · Land) neben einem Suchfeld. Man *konnte* suchen, *musste* aber nicht – also
 * wurde getippt, und jede getippte Adresse ist eine Fehlerquelle (Tippfehler, falsche
 * PLZ, «Zürich»/«Zurich», Strasse ohne Hausnummer).
 *
 * Diese Komponente dreht das um, ohne den Nutzer einzusperren:
 *
 *   1. **Leer → nur ein Suchfeld.** Der einzige sichtbare Weg ist die Google-Suche.
 *      Ein Treffer füllt Strasse/Hausnummer, PLZ, Ort und Land in einem Zug.
 *   2. **Gefüllt → kompakte, NICHT editierbare Zusammenfassung** + «Ändern» (= neue
 *      Suche). Was einmal validiert ist, kann nicht versehentlich verfälscht werden.
 *   3. **«Adresse nicht gefunden?» → manuell erfassen.** Klein gesetzt, ein Klick, für
 *      die echten Ausnahmen (Neubau, Postfach, Industrieareal ohne Hausnummer).
 *
 * Gezwungen wird also über den **Standardweg**, nicht über gesperrte Felder – ein
 * hartes Read-only würde genau die Ausnahmen unbedienbar machen, die es real gibt.
 *
 * Ohne Google-Key oder bei Ladefehler startet die Komponente direkt im manuellen
 * Modus (mit Hinweis) – sie ist nie kaputt, nur weniger komfortabel.
 */

import { useEffect, useRef, useState } from 'react';
import { MapPin, Pencil, Search, CheckCircle2, LocateFixed, Loader2 } from 'lucide-react';
import { useGoogleMaps } from './use-google-maps';

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

// Google liefert das Land als **ISO-2** (``short('country')``, z. B. «US»). Die Aufrufer
// führen es teils als ISO-2 (Person: Wert «CH»), teils als Klarname (Firma: Wert «USA»).
// Diese Normalisierung bringt beide auf ISO-2, damit ein Google-Treffer die richtige Option
// trifft – ohne sie wurde «US» gegen «USA» verglichen, verworfen und das alte Land (Schweiz)
// blieb stehen (der gemeldete Bug). Deckt die in den Dropdowns verwendeten Klarnamen +
// gängige englische Google-Namen ab; ein reiner 2-Buchstaben-Code fällt unverändert durch.
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

type PlacePick = { street: string; zip: string; city: string; country: string; lat?: number; lng?: number };

function parsePlace(place: google.maps.places.PlaceResult): PlacePick {
  const comps = place.address_components ?? [];
  const get = (t: string) => comps.find((c) => c.types.includes(t))?.long_name ?? '';
  const short = (t: string) => comps.find((c) => c.types.includes(t))?.short_name ?? '';
  const loc = place.geometry?.location;
  return {
    street: [get('route'), get('street_number')].filter(Boolean).join(' ').trim(),
    zip: get('postal_code'),
    city: get('locality') || get('postal_town') || get('administrative_area_level_2'),
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
  label = 'Adresse', required = false,
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
}) {
  const { loaded, error } = useGoogleMaps(apiKey);
  const usable = loaded && !error;
  const [manual, setManual] = useState(false);
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
    <span style={ST.label}>
      {label}
      {missing && <span style={{ color: '#f59e0b', marginLeft: 3, fontWeight: 700 }}>*</span>}
    </span>
  );

  /**
   * **Standort verwenden** (Testnotiz #306): GPS → Adresse, in einem Griff.
   *
   * Der Browser liefert Koordinaten, Googles Geocoder macht daraus dieselbe Trefferform
   * wie die Suche (`parsePlace`) – also läuft die Übernahme durch **denselben** Zweig wie
   * ein gewählter Vorschlag, statt einen zweiten Weg ins Formular aufzumachen. Nützlich
   * genau dort, wo man steht: eine Aussenstelle vor Ort erfassen.
   */
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
    // Den Google-Code (ISO-2) über die Normalisierung gegen die Optionen matchen und –
    // bei Treffer – den **Options-Wert** übernehmen (Klarname «USA» bzw. ISO «US», je nach
    // Aufrufer). Kein Treffer: den Google-Code trotzdem übernehmen (NIE still das alte Land
    // behalten – genau das war der Bug); nur wenn Google gar nichts liefert, bleibt der Wert.
    const matched = countryOptions.find(([v]) => toIso2(v) === toIso2(p.country));
    onChangeRef.current({
      ...valueRef.current,
      street: p.street, zip: p.zip, city: p.city,
      country: matched ? matched[0] : (p.country || valueRef.current.country),
      lat: p.lat, lng: p.lng,
    });
    setSearching(false);
    setQuery('');
  }

  // `applyPlace` schliesst über Props/State – als Ref gehalten, damit der Autocomplete-
  // Effekt nicht bei jedem Render neu aufgesetzt werden muss.
  const applyPlaceRef = useRef(applyPlace);
  applyPlaceRef.current = applyPlace;

  // Ohne nutzbare Google-Suche gibt es keinen Standardweg – dann direkt manuell.
  useEffect(() => {
    if (error) setManual(true);
  }, [error]);

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
      <div style={ST.wrap}>
        <div style={ST.head}>
          <MapPin size={14} style={{ color: 'var(--fg-3)' }} />
          {labelNode}
          {usable && (
            <button type="button" onClick={() => { setManual(false); setSearching(true); }} style={ST.link}>
              <Search size={12} /> Stattdessen suchen
            </button>
          )}
        </div>
        {error === 'auth' && (
          <p style={ST.note}>Adress-Suche nicht verfügbar (Google «Places API» nicht freigeschaltet) – bitte manuell erfassen.</p>
        )}
        <div style={ST.grid}>
          <Input label="Strasse und Hausnummer" value={value.street} onChange={set('street')} wide />
          {showStreet2 && <Input label="Adresszusatz" value={value.street2 ?? ''} onChange={set('street2')} wide />}
          <Input label="PLZ" value={value.zip} onChange={set('zip')} />
          <Input label="Ort" value={value.city} onChange={set('city')} />
          {showRegion && <Input label="Region" value={value.region ?? ''} onChange={set('region')} />}
          <Select label="Land" value={value.country} onChange={set('country')} options={countryOptions} />
        </div>
      </div>
    );
  }

  // ── Suchmodus: EIN Feld, der Standardweg ───────────────────────────────────────
  if (searching || !hasAddress(value)) {
    return (
      <div style={ST.wrap}>
        <div style={ST.head}>
          <MapPin size={14} style={{ color: 'var(--fg-3)' }} />
          {labelNode}
          {hasAddress(value) && (
            <button type="button" onClick={() => setSearching(false)} style={ST.link}>Abbrechen</button>
          )}
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={ST.searchIcon} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Adresse suchen – z. B. Musterstrasse 12, Zürich"
            autoComplete="off"
            style={ST.search}
            // Enter wählt den Vorschlag, statt das Formular abzuschicken.
            onKeyDown={(e) => {
              if (e.key === 'Enter' && document.querySelector('.pac-container:not([style*="display: none"])')) {
                e.preventDefault();
              }
            }}
          />
        </div>
        {/* Zwei Auswege aus dem Tippen: der Standort, an dem man gerade steht (#306),
            und – für die echten Ausnahmen – die manuelle Erfassung. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {usable && typeof navigator !== 'undefined' && 'geolocation' in navigator && (
            <button type="button" onClick={useMyLocation} disabled={locating} style={ST.locate}>
              {locating ? <Loader2 size={13} style={{ animation: 'spin 0.7s linear infinite' }} /> : <LocateFixed size={13} />}
              {locating ? 'Standort wird ermittelt…' : 'Aktuellen Standort verwenden'}
            </button>
          )}
          <button type="button" onClick={() => setManual(true)} style={ST.escape}>
            Adresse nicht gefunden? Manuell erfassen
          </button>
        </div>
        {locateError && <p style={{ ...ST.note, color: 'var(--warning)' }}>{locateError}</p>}
      </div>
    );
  }

  // ── Gefüllt: kompakte Zusammenfassung, nicht editierbar ────────────────────────
  // Label über exakten Wert ODER ISO-2-Gleichheit (so zeigt ein gespeichertes «US» das
  // Klarname-Label «USA», wenn die Optionen Klarnamen sind).
  const countryLabel =
    countryOptions.find(([v]) => v === value.country)?.[1]
    ?? countryOptions.find(([v]) => toIso2(v) === toIso2(value.country))?.[1]
    ?? value.country;
  return (
    <div style={ST.wrap}>
      <div style={ST.head}>
        <MapPin size={14} style={{ color: 'var(--fg-3)' }} />
        {labelNode}
        <button type="button" onClick={() => setSearching(true)} style={ST.link}>
          <Pencil size={12} /> Ändern
        </button>
      </div>
      <div style={ST.summary}>
        <CheckCircle2 size={15} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 1 }} />
        <div style={{ minWidth: 0 }}>
          <div style={ST.line1}>{value.street}</div>
          {showStreet2 && value.street2 && <div style={ST.line2}>{value.street2}</div>}
          <div style={ST.line2}>{[value.zip, value.city].filter(Boolean).join(' ')}</div>
          <div style={ST.line2}>{countryLabel}</div>
        </div>
      </div>
      {/* Adresszusatz (c/o, Postfach, Stockwerk) ist die Ausnahme, nicht die Regel – er wird
          real für Lieferetiketten gebraucht, soll aber nicht als leeres Dauerfeld Fläche kosten.
          Darum: nur zeigen, wenn befüllt oder ausdrücklich gewünscht. */}
      {showStreet2 && (value.street2 || street2Open ? (
        <Input label="Adresszusatz (c/o, Postfach)" value={value.street2 ?? ''} onChange={set('street2')} wide />
      ) : (
        <button type="button" onClick={() => setStreet2Open(true)} style={ST.escape}>
          + Adresszusatz
        </button>
      ))}
    </div>
  );
}

// ─── Bausteine ────────────────────────────────────────────────────────────────────

function Input({ label, value, onChange, wide }: {
  label: string; value: string; onChange: (v: string) => void; wide?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: wide ? '1 / -1' : undefined }}>
      <label style={ST.fieldLabel}>{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} style={ST.input} />
    </div>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={ST.fieldLabel}>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={ST.input}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
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
