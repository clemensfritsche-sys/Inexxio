'use client';

import { useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { FILTER_TYPES } from '@/lib/erp-record';
import { tell } from '@/lib/notice';
import type { ErpRecordType } from '@/types';

/**
 * ►►► **Was die Adresse beim Öffnen des ERP sagt** – einmal je Seitenaufruf gelesen. ◄◄◄
 *
 * - `?typ=<Datensatztyp>` (Arbeitsleiste): stellt nur den Filter vor, wie ein Klick auf
 *   seinen Chip. Unbekannte Werte bleiben ohne Wirkung.
 * - `?open=<Objektnummer>` (Etikett, tiefer Link): öffnet den Datensatz; der Typ wird auf
 *   dem Server aufgelöst (geht auch, bevor der Feed geladen ist).
 */
export function useUrlParams({ onType, onOpen }: {
  onType: (type: ErpRecordType) => void;
  onOpen: (type: ErpRecordType, objectId: number) => void;
}): void {
  const handlers = useRef({ onType, onOpen });
  handlers.current = { onType, onOpen };
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const known = FILTER_TYPES.find((t) => t === params.get('typ'));
    if (known) handlers.current.onType(known);
    const raw = params.get('open');
    const oid = raw ? Number(raw) : NaN;
    if (!Number.isFinite(oid)) return;
    api.resolveObject(oid)
      .then((r) => handlers.current.onOpen(r.object_type as ErpRecordType, oid))
      .catch(tell(`Datensatz ${oid}`, 'Nicht geöffnet'));
  }, []);
}
