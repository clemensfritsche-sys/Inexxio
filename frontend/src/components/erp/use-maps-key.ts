'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

// Der Google-Maps-Key steht in den ÖFFENTLICHEN Firmeneinstellungen (für Karte + Adress-
// Autovervollständigung). Einmal laden und modulweit cachen – jede Adress-Eingabe teilt ihn.
let cached: string | null | undefined;
let inflight: Promise<string | null> | null = null;

export function useMapsApiKey(): string | null {
  const [key, setKey] = useState<string | null>(cached ?? null);
  useEffect(() => {
    if (cached !== undefined) { setKey(cached); return; }
    inflight ??= api.getPublicSettings()
      .then((s) => { cached = (s.google_maps_api_key as string | null) ?? null; return cached; })
      .catch(() => { cached = null; return null; });
    let alive = true;
    inflight.then((k) => { if (alive) setKey(k); });
    return () => { alive = false; };
  }, []);
  return key;
}
