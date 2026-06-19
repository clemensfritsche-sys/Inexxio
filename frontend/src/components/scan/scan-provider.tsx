'use client';

import { createContext, useCallback, useContext, useState } from 'react';
import dynamic from 'next/dynamic';
import type { ScanRequest } from '@/components/scan/scan-dialog';

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
  const [req, setReq] = useState<ScanRequest | null>(null);
  const scan = useCallback<ScanFn>((r) => setReq(r), []);

  return (
    <ScanContext.Provider value={scan}>
      {children}
      {req && (
        <ScanDialog
          {...req}
          onResult={(id) => { setReq(null); req.onResult(id); }}
          onClose={() => setReq(null)}
        />
      )}
    </ScanContext.Provider>
  );
}
