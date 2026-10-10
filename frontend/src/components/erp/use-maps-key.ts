'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

// Der Google-Maps-Key steht in den ÖFFENTLICHEN Firmeneinstellungen (für Karte + Adress-
// Autovervollständigung). Einmal laden und modulweit cachen – jede Adress-Eingabe teilt ihn.
let cached: string | null | undefined;
let inflight: Promise<string | null> | null = null;

/**
 * ►►► **`undefined` heisst «noch nicht bekannt», `null` «es gibt keinen»** (Testnotiz
 * #1044). ◄◄◄
 *
 * Beides war einmal `null`, und die Unterscheidung fehlte an genau einer Stelle: ein
 * Adressfeld meldete beim **ersten** Rendern «kein Schlüssel» und schaltete auf die
 * manuelle Erfassung – auch dort, wo der Schlüssel eine Zehntelsekunde später eintraf.
 * Wer den Datensatz als Erstes in der Sitzung öffnete, bekam darum das Formular, beim
 * zweiten Mal die Suche: dieselbe Oberfläche, zwei Gesichter.
 *
 * Ein dritter Wert ist dafür genug – eine Antwort, die man noch nicht hat, ist keine.
 */
export function useMapsApiKey(): string | null | undefined {
  const [key, setKey] = useState<string | null | undefined>(cached);
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
