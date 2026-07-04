'use client';

import { QRCodeSVG } from 'qrcode.react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Printer, QrCode } from 'lucide-react';
import { encodeObjectCode } from '@/lib/scan';
import { fmtObjId } from '@/components/erp/user-detail';

/** Reiner QR-Code eines Objekts (SVG – scharf für Druck & Bildschirm). */
export function ObjectQr({ objectId, size = 96 }: { objectId: number; size?: number }) {
  return <QRCodeSVG value={encodeObjectCode(objectId)} size={size} level="M" marginSize={2} />;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}

// Druckbares Etikett als HTML-String (QR + Objektnummer + Titel/Untertitel).
function labelMarkup(objectId: number, title?: string | null, subtitle?: string | null, size = 120): string {
  const qr = renderToStaticMarkup(<ObjectQr objectId={objectId} size={size} />);
  return (
    `<div style="display:inline-flex;flex-direction:column;align-items:center;gap:6px;padding:12px;` +
    `border:1px solid #e2e8f0;border-radius:12px;background:#fff;font-family:Inter,system-ui,sans-serif">` +
    qr +
    `<div style="font-family:monospace;font-weight:700;font-size:15px;color:#0f172a">${fmtObjId(objectId)}</div>` +
    (title ? `<div style="font-size:12px;color:#475569;max-width:${size + 24}px;text-align:center">${escapeHtml(title)}</div>` : '') +
    (subtitle ? `<div style="font-size:11px;color:#94a3b8">${escapeHtml(subtitle)}</div>` : '') +
    `</div>`
  );
}

/**
 * Öffnet direkt den Druckdialog mit dem QR-Etikett des Objekts – ohne dass das
 * Etikett auf der Seite gerendert sein muss. Genutzt vom QR-Knopf im Detail-Kopf.
 */
export function printObjectLabel(objectId: number, title?: string | null, subtitle?: string | null, size = 120) {
  const w = window.open('', '_blank', 'width=420,height=520');
  if (!w) return;
  w.document.write(
    `<!doctype html><html><head><title>Etikett ${fmtObjId(objectId)}</title>` +
    `<style>@page{margin:8mm} body{font-family:Inter,system-ui,sans-serif;margin:0;` +
    `display:flex;align-items:center;justify-content:center;min-height:100vh}</style></head>` +
    `<body>${labelMarkup(objectId, title, subtitle, size)}<script>window.onload=function(){window.focus();window.print();};` +
    `window.onafterprint=function(){window.close();}<\/script></body></html>`,
  );
  w.document.close();
}

/**
 * QR-Etikett eines Objekts inkl. Objektnummer + optionalem Titel und einem
 * «Etikett drucken»-Knopf. Das gedruckte Etikett lässt sich aufkleben und später
 * per Kamera wieder einlesen (Lagerplatz bis kleinste Charge).
 */
export function ObjectLabel({ objectId, title, subtitle, size = 120 }: {
  objectId: number; title?: string | null; subtitle?: string | null; size?: number;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)' }}>
        <QrCode size={13} /> Etikett
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: 12, border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', background: '#fff' }}>
          <ObjectQr objectId={objectId} size={size} />
          <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 15, color: 'var(--fg-1)' }}>{fmtObjId(objectId)}</div>
          {title && <div style={{ fontSize: 12, color: 'var(--fg-2)', maxWidth: size + 24, textAlign: 'center' }}>{title}</div>}
          {subtitle && <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{subtitle}</div>}
        </div>
        <button onClick={() => printObjectLabel(objectId, title, subtitle, size)} style={printBtn}>
          <Printer size={14} /> Etikett drucken
        </button>
      </div>
    </div>
  );
}

const printBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8,
  border: '1px solid var(--border-2)', background: '#fff', color: 'var(--fg-2)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
