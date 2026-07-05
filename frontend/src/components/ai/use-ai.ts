'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { AiConfig } from '@/types';

// Modulweiter Cache: die KI-Verfügbarkeit ändert sich nur mit der Server-Konfiguration –
// EIN Request je Seite genügt (mehrere Einbau-Orte teilen sich das Ergebnis).
let cached: Promise<AiConfig> | null = null;

function fetchConfig(): Promise<AiConfig> {
  if (!cached) {
    cached = api.getAiConfig().catch((e) => { cached = null; throw e; });
  }
  return cached;
}

/** KI-Verfügbarkeit (Text/Bild) – ``null`` solange unbekannt (nichts einblenden). */
export function useAiConfig(): AiConfig | null {
  const [cfg, setCfg] = useState<AiConfig | null>(null);
  useEffect(() => {
    let alive = true;
    fetchConfig().then((c) => { if (alive) setCfg(c); }).catch(() => { if (alive) setCfg(null); });
    return () => { alive = false; };
  }, []);
  return cfg;
}
