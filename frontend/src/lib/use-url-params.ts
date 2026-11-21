'use client';

import { useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { FILTER_TYPES } from '@/lib/erp-record';
import { tell } from '@/lib/notice';
import type { Creatable } from '@/components/erp/feed-panel';
import type { ErpRecordType } from '@/types';

/**
 * ►►► **Was die Adresse beim Öffnen des ERP sagt** – einmal je Seitenaufruf gelesen. ◄◄◄
 *
 * - `?typ=<Datensatztyp>` (Arbeitsleiste): stellt nur den Filter vor, wie ein Klick auf
 *   seinen Chip. Unbekannte Werte bleiben ohne Wirkung.
 * - `?open=<Objektnummer>` (Etikett, tiefer Link): öffnet den Datensatz; der Typ wird auf
 *   dem Server aufgelöst (geht auch, bevor der Feed geladen ist).
 * - `?neu=<person|company|article|order|document>` (das «+» auf der Website: «Neu anlegen»,
 *   📷 und 📄): öffnet denselben Entwurf wie das «+» im ERP; `&quelle=kamera` beginnt ihn mit
 *   der Kamera, `&handgriff=<Nr>` nennt den Vorschlag, aus dem er vorausgefüllt wird und der mit
 *   der Freigabe erledigt ist («Entwurf öffnen»). Danach steht er nicht mehr in der Adresse – ein
 *   Neuladen legt nichts zweimal an.
 */
const CREATABLE: readonly Creatable[] = ['person', 'company', 'article', 'order', 'document'];

export function useUrlParams({ onType, onOpen, onCreate }: {
  onType: (type: ErpRecordType) => void;
  onOpen: (type: ErpRecordType, objectId: number) => void;
  onCreate: (type: Creatable, camera: boolean, handgriff: number | null) => void;
}): void {
  const handlers = useRef({ onType, onOpen, onCreate });
  handlers.current = { onType, onOpen, onCreate };
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const known = FILTER_TYPES.find((t) => t === params.get('typ'));
    if (known) handlers.current.onType(known);
    const create = CREATABLE.find((t) => t === params.get('neu'));
    if (create) {
      const hg = Number(params.get('handgriff'));
      handlers.current.onCreate(create, create === 'document' && params.get('quelle') === 'kamera',
        Number.isInteger(hg) && hg > 0 ? hg : null);
      params.delete('neu');
      params.delete('handgriff');
      params.delete('quelle');
      const rest = params.toString();
      window.history.replaceState(null, '', `${window.location.pathname}${rest ? `?${rest}` : ''}`);
    }
    const raw = params.get('open');
    const oid = raw ? Number(raw) : NaN;
    if (!Number.isFinite(oid)) return;
    api.resolveObject(oid)
      .then((r) => handlers.current.onOpen(r.object_type as ErpRecordType, oid))
      .catch(tell(`Datensatz ${oid}`, 'Nicht geöffnet'));
  }, []);
}
