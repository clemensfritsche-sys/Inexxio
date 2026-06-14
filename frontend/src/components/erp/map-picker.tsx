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

export function MapPicker({ apiKey, lat, lng, onPick }: {
  apiKey: string | null;
  lat: number | null;
  lng: number | null;
  onPick: (lat: number, lng: number, address?: ParsedAddress) => void;
}) {
  const { loaded, error } = useGoogleMaps(apiKey);
  const mapEl = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const marker = useRef<google.maps.Marker | null>(null);
  const geocoder = useRef<google.maps.Geocoder | null>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const [locating, setLocating] = useState(false);

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
      marker.current = new google.maps.Marker({ map: map.current, draggable: true, position: p });
      marker.current.addListener('dragend', () => {
        const pos = marker.current?.getPosition();
        if (pos) reverseGeocode({ lat: pos.lat(), lng: pos.lng() });
      });
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
    map.current.addListener('click', (e: google.maps.MapMouseEvent) => {
      if (!e.latLng) return;
      const p = { lat: e.latLng.lat(), lng: e.latLng.lng() };
      placeMarker(p, false);
      reverseGeocode(p);
    });
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
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        placeMarker(p, true);
        reverseGeocode(p);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  if (!apiKey || error === 'no-key') {
    return (
      <div style={noticeStyle}>
        <AlertCircle size={14} style={{ flexShrink: 0 }} />
        <span>Google-Maps-API-Key fehlt — bitte unter <b>Admin → Einstellungen</b> hinterlegen, um die Karte zu nutzen.</span>
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ ...noticeStyle, background: '#fef2f2', borderColor: '#fecaca', color: '#b91c1c' }}>
        <AlertCircle size={14} style={{ flexShrink: 0 }} /> Karte konnte nicht geladen werden.
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>Standort (Karte)</span>
        <button
          type="button"
          onClick={useGps}
          style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff', fontSize: 12, fontWeight: 600, color: '#2563eb', cursor: 'pointer' }}
        >
          <Crosshair size={13} /> {locating ? 'Ermittle…' : 'Standort via GPS'}
        </button>
      </div>
      <div ref={mapEl} style={{ width: '100%', height: 260, borderRadius: 10, border: '1px solid #E2E8F0', background: '#F1F5F9' }} />
      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 6 }}>
        {lat != null && lng != null
          ? `Koordinaten: ${lat.toFixed(6)}, ${lng.toFixed(6)} — Marker ziehen oder auf die Karte klicken, um anzupassen.`
          : 'Auf die Karte klicken, Marker ziehen oder GPS verwenden — die Adresse wird automatisch ermittelt.'}
      </div>
      {!loaded && <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Karte lädt…</div>}
    </div>
  );
}

const noticeStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '12px 14px',
  background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10,
  fontSize: 13, color: '#92400e',
};
