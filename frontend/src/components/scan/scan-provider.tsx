'use client';

import { createContext, useCallback, useContext, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import type { ScanRequest } from '@/lib/scan';

// Scanner-Dialog (inkl. ZXing-Decoder) erst bei Bedarf laden – hält das ERP-
// Initialbündel schlank, der schwere Decoder kommt erst beim ersten Scan.
const ScanDialog = dynamic(
  () => import('@/components/scan/scan-dialog').then((m) => m.ScanDialog),
  { ssr: false },
);

// Zentrale Scan-Funktion: ein Aufruf öffnet den globalen Scanner-Dialog.
// Genau EINE Dialog-Instanz hängt am ERP-Wurzel-Layout; jede Funktion triggert
// sie über `useScan()` – das ist die «zentrale Grundfunktion».
type ScanFn = (req: ScanRequest) => void;

const ScanContext = createContext<ScanFn | null>(null);

export function useScan(): ScanFn {
  const fn = useContext(ScanContext);
  if (!fn) throw new Error('useScan muss innerhalb von <ScanProvider> verwendet werden');
  return fn;
}

export function ScanProvider({ children }: { children: React.ReactNode }) {
  // Jede Anfrage bekommt eine eigene id → der Dialog wird per `key` frisch
  // gemountet. Wichtig für Scan-Sequenzen (Bewegung/Ressource/Datenerfassung),
  // die `scan()` mehrfach hintereinander aufrufen: kein Zustands-Recycling.
  const [req, setReq] = useState<{ id: number; req: ScanRequest } | null>(null);
  const idRef = useRef(0);
  const scan = useCallback<ScanFn>((r) => {
    // Eine leere Sequenz ergäbe einen Dialog, der die Kamera öffnet und auf nichts
    // wartet. Das ist ein Aufruffehler und wird als solcher gemeldet, statt als
    // stummes Fenster zu erscheinen.
    if (!r.steps.length) throw new Error('scan() braucht mindestens einen Schritt');
    idRef.current += 1;
    setReq({ id: idRef.current, req: r });
  }, []);

  return (
    <ScanContext.Provider value={scan}>
      {children}
      {req && (
        <ScanDialog
          key={req.id}
          {...req.req}
          onComplete={(ids, how) => { setReq(null); req.req.onComplete(ids, how); }}
          onClose={() => setReq(null)}
        />
      )}
    </ScanContext.Provider>
  );
}
