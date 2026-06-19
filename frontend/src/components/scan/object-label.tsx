'use client';

import { useRef } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Printer, QrCode } from 'lucide-react';
import { encodeObjectCode } from '@/lib/scan';
import { fmtObjId } from '@/components/erp/user-detail';

/** Reiner QR-Code eines Objekts (SVG – scharf für Druck & Bildschirm). */
export function ObjectQr({ objectId, size = 96 }: { objectId: number; size?: number }) {
  return <QRCodeSVG value={encodeObjectCode(objectId)} size={size} level="M" marginSize={2} />;
}

/**
 * QR-Etikett eines Objekts inkl. Objektnummer + optionalem Titel und einem
 * «Etikett drucken»-Knopf. Das gedruckte Etikett lässt sich aufkleben und später
 * per Kamera wieder einlesen (Lagerplatz bis kleinste Charge).
 */
export function ObjectLabel({ objectId, title, subtitle, size = 120 }: {
  objectId: number; title?: string | null; subtitle?: string | null; size?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  function print() {
    const inner = ref.current?.innerHTML;
    if (!inner) return;
    const w = window.open('', '_blank', 'width=420,height=520');
    if (!w) return;
    w.document.write(
      `<!doctype html><html><head><title>Etikett ${fmtObjId(objectId)}</title>` +
      `<style>@page{margin:8mm} body{font-family:Inter,system-ui,sans-serif;margin:0;` +
      `display:flex;align-items:center;justify-content:center;min-height:100vh}</style></head>` +
      `<body>${inner}<script>window.onload=function(){window.focus();window.print();};` +
      `window.onafterprint=function(){window.close();}<\/script></body></html>`,
    );
    w.document.close();
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
        <QrCode size={13} /> Etikett
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {/* Druckbare Etikett-Fläche (wird 1:1 ins Druckfenster übernommen) */}
        <div ref={ref}>
          <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: 12, border: '1px solid #e2e8f0', borderRadius: 12, background: '#fff' }}>
            <ObjectQr objectId={objectId} size={size} />
            <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 15, color: '#0f172a' }}>{fmtObjId(objectId)}</div>
            {title && <div style={{ fontSize: 12, color: '#475569', maxWidth: size + 24, textAlign: 'center' }}>{title}</div>}
            {subtitle && <div style={{ fontSize: 11, color: '#94a3b8' }}>{subtitle}</div>}
          </div>
        </div>
        <button onClick={print} style={printBtn}>
          <Printer size={14} /> Etikett drucken
        </button>
      </div>
    </div>
  );
}

const printBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8,
  border: '1px solid #E2E8F0', background: '#fff', color: '#374151', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
