'use client';

import { useEffect, useState } from 'react';
import { ErpNavContext } from '@/components/erp/obj-id';
import { CaptureSheet, type PinHost } from '@/components/erp/capture/capture-sheet';
import { CaptureContext, CREATABLE_OF, type CaptureActions } from '@/components/erp/capture/capture-context';

/** Wer die Seite einbettet (die Website, gleicher Ursprung) – hört auf `ready` und `close`. */
const SOURCE = 'inexxio-capture';

/**
 * ►►► **Das «+» zum Einbetten** – die Website zeigt es Personal über jeder Seite
 * (`website/src/scripts/capture.ts`) in einem Rahmen. ◄◄◄
 *
 * Es ist dasselbe «+» wie im ERP (`CaptureSheet`) mit derselben Anmeldung (ERP-Layout,
 * `AuthGate staffOnly`) – das Gespräch, Foto und Datei laufen hier im Rahmen. Nur die Wege nach
 * draussen gehen ins Fenster dahinter: die Stecknadel zeigt auf die Website (gleicher Ursprung),
 * «Neu anlegen» und «Entwurf öffnen» öffnen das ERP (`/erp?neu=…&handgriff=…`, `/erp?open=…`),
 * schliessen meldet `close`. Kopf und Fuss der Seite selbst sind aus (`html[data-embed]`).
 *
 * Ohne Rahmen (direkt aufgerufen) gibt es nichts einzubetten: dann geht es ins ERP.
 */
export default function EmbeddedCapture() {
  const [inFrame, setInFrame] = useState<boolean | null>(null);
  useEffect(() => {
    const framed = window.parent !== window && sameOrigin();
    if (!framed) { window.location.replace('/erp'); return; }
    document.documentElement.setAttribute('data-embed', '');
    setInFrame(true);
    tellParent('ready');
  }, []);
  if (!inFrame) return null;

  const top = window.parent;
  const go = (path: string) => { top.location.href = path; };
  const host: PinHost = {
    doc: top.document,
    win: top,
    hide: () => { window.frameElement?.setAttribute('style', 'visibility:hidden'); },
    show: () => { window.frameElement?.removeAttribute('style'); },
  };
  const actions: CaptureActions = {
    // Nur die Nummer reist: die Feed-Seite liest den Vorschlag selbst (`draftFrom`) – dieselben
    // Werte wie im ERP, auch die Zeilen eines Auftrags.
    openDraft: (d) => go(`/erp?${new URLSearchParams({
      neu: CREATABLE_OF[d.kind], handgriff: String(d.handgriff) })}`),
  };
  return (
    <ErpNavContext.Provider value={(objectId) => go(`/erp?open=${objectId}`)}>
      <CaptureContext.Provider value={actions}>
        <CaptureSheet hint={null} host={host} onClose={() => tellParent('close')}
          onCreate={(type) => go(`/erp?neu=${type}`)} />
      </CaptureContext.Provider>
    </ErpNavContext.Provider>
  );
}

function sameOrigin(): boolean {
  try { return window.parent.location.origin === window.location.origin; } catch { return false; }
}

function tellParent(what: 'ready' | 'close') {
  window.parent.postMessage({ source: SOURCE, what }, window.location.origin);
}
