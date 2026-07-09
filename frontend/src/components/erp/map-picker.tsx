'use client';

/// <reference types="google.maps" />
import { useEffect, useRef, useState } from 'react';
import { Crosshair, AlertCircle } from 'lucide-react';
import { useGoogleMaps } from './use-google-maps';

export type ParsedAddress = { street: string; zip: string; city: string; country: string };

const DEFAULT_CENTER = { lat: 46.8, lng: 8.23 }; // Schweiz
const DEFAULT_ZOOM = 7;
const PICK_ZOOM = 17;

function parseAddress(components: google.maps.GeocoderAddressComponent[]): ParsedAddress {
  const get = (type: string) => components.find((c) => c.types.includes(type))?.long_name ?? '';
  const street = [get('route'), get('street_number')].filter(Boolean).join(' ').trim();
  const city = get('locality') || get('postal_town') || get('administrative_area_level_2');
  return { street, zip: get('postal_code'), city, country: get('country') };
}

export function MapPicker({ apiKey, lat, lng, onPick, readOnly = false }: {
  apiKey: string | null;
  lat: number | null;
  lng: number | null;
  onPick: (lat: number, lng: number, address?: ParsedAddress) => void;
  readOnly?: boolean;
}) {
  const { loaded, error } = useGoogleMaps(apiKey);
  const mapAvailable = !!apiKey && !error;

  const mapEl = useRef<HTMLDivElement>(null);
  const searchEl = useRef<HTMLInputElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const marker = useRef<google.maps.Marker | null>(null);
  const geocoder = useRef<google.maps.Geocoder | null>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const [locating, setLocating] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);

  function reverseGeocode(p: google.maps.LatLngLiteral) {
    if (!geocoder.current) { onPickRef.current(p.lat, p.lng); return; }
    geocoder.current.geocode({ location: p }, (results, status) => {
      if (status === 'OK' && results && results[0]) {
        onPickRef.current(p.lat, p.lng, parseAddress(results[0].address_components));
      } else {
        onPickRef.current(p.lat, p.lng);
      }
    });
  }

  function placeMarker(p: google.maps.LatLngLiteral, pan: boolean) {
    if (!map.current) return;
    if (!marker.current) {
      marker.current = new google.maps.Marker({ map: map.current, draggable: !readOnly, position: p });
      if (!readOnly) {
        marker.current.addListener('dragend', () => {
          const pos = marker.current?.getPosition();
          if (pos) reverseGeocode({ lat: pos.lat(), lng: pos.lng() });
        });
      }
    } else {
      marker.current.setPosition(p);
    }
    if (pan) { map.current.panTo(p); map.current.setZoom(PICK_ZOOM); }
  }

  // Karte einmalig initialisieren (Komponente wird je Datensatz neu gemountet)
  useEffect(() => {
    if (!loaded || !mapEl.current || map.current) return;
    const hasCoords = lat != null && lng != null;
    map.current = new google.maps.Map(mapEl.current, {
      center: hasCoords ? { lat: lat as number, lng: lng as number } : DEFAULT_CENTER,
      zoom: hasCoords ? PICK_ZOOM : DEFAULT_ZOOM,
      mapTypeControl: false, streetViewControl: false, fullscreenControl: false,
    });
    geocoder.current = new google.maps.Geocoder();
    if (hasCoords) placeMarker({ lat: lat as number, lng: lng as number }, false);
    if (!readOnly) {
      map.current.addListener('click', (e: google.maps.MapMouseEvent) => {
        if (!e.latLng) return;
        const p = { lat: e.latLng.lat(), lng: e.latLng.lng() };
        placeMarker(p, false);
        reverseGeocode(p);
      });
      // Adress-Suche (Google Places): tippen → Vorschlag wählen → Pin + Adresse übernehmen.
      if (searchEl.current && google.maps.places) {
        const ac = new google.maps.places.Autocomplete(searchEl.current, {
          fields: ['address_components', 'geometry'], types: ['address'],
        });
        ac.addListener('place_changed', () => {
          const place = ac.getPlace();
          const loc = place.geometry?.location;
          if (!loc) return;
          const p = { lat: loc.lat(), lng: loc.lng() };
          placeMarker(p, true);
          onPickRef.current(p.lat, p.lng,
            place.address_components ? parseAddress(place.address_components) : undefined);
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  // Externe Koordinatenänderungen (z. B. GPS) im Marker spiegeln
  useEffect(() => {
    if (!map.current || lat == null || lng == null) return;
    placeMarker({ lat, lng }, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lng]);

  function useGps() {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return;
    setLocating(true);
    setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        placeMarker(p, true);
        reverseGeocode(p);
      },
      (err) => {
        setLocating(false);
        if (err.code === 1) {
          setGpsError('Standortzugriff verweigert – bitte in den Browser-Einstellungen erlauben.');
        } else if (err.code === 2) {
          setGpsError('Standort konnte nicht ermittelt werden.');
        } else {
          setGpsError('Zeitüberschreitung – bitte erneut versuchen.');
        }
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  const hasGeo = typeof navigator !== 'undefined' && !!navigator.geolocation;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>Standort (Karte)</span>
        {hasGeo && !readOnly && (
          <button
            type="button"
            onClick={useGps}
            disabled={locating}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff', fontSize: 12, fontWeight: 600, color: locating ? '#94a3b8' : '#2563eb', cursor: locating ? 'wait' : 'pointer' }}
          >
            <Crosshair size={13} /> {locating ? 'Ermittle…' : 'Standort via GPS'}
          </button>
        )}
      </div>

      {gpsError && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, padding: '7px 10px', borderRadius: 8, background: '#fef2f2', border: '1px solid #fecaca', fontSize: 12, color: '#dc2626' }}>
          <AlertCircle size={13} style={{ flexShrink: 0 }} />
          {gpsError}
        </div>
      )}

      {mapAvailable ? (
        <>
          {!readOnly && (
            <input ref={searchEl} placeholder="Adresse suchen – Vorschlag setzt Pin + füllt die Adresse"
              autoComplete="off"
              style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #E2E8F0', fontSize: 13, marginBottom: 8, boxSizing: 'border-box', outline: 'none' }} />
          )}
          <div ref={mapEl} style={{ width: '100%', height: 260, borderRadius: 10, border: '1px solid #E2E8F0', background: '#F1F5F9' }} />
          {!loaded && <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Karte lädt…</div>}
        </>
      ) : (
        <div style={noticeStyle}>
          <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            {error && error !== 'no-key'
              ? 'Karte konnte nicht geladen werden.'
              : 'Karte benötigt einen Google-Maps-API-Key (Admin → Einstellungen). Der GPS-Button funktioniert auch ohne Karte; die Adresse muss dann manuell erfasst werden.'}
          </span>
        </div>
      )}

      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 6 }}>
        {lat != null && lng != null
          ? `Koordinaten: ${lat.toFixed(6)}, ${lng.toFixed(6)}${mapAvailable && !readOnly ? ' — Marker ziehen oder auf die Karte klicken' : ''}`
          : readOnly
            ? 'Kein Standort hinterlegt.'
            : mapAvailable
              ? 'Auf die Karte klicken, Marker ziehen oder GPS verwenden — die Adresse wird automatisch ermittelt.'
              : 'GPS verwenden, um die Koordinaten zu erfassen.'}
      </div>
    </div>
  );
}

const noticeStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '12px 14px',
  background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10,
  fontSize: 13, color: '#92400e',
};
