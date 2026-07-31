'use client';

import { QRCodeSVG } from 'qrcode.react';
import { renderToStaticMarkup } from 'react-dom/server';
import { encodeObjectCode } from '@/lib/scan';
import { formatObjectId } from '@/lib/utils';

/** Reiner QR-Code eines Objekts (SVG – scharf für Druck & Bildschirm). */
function ObjectQr({ objectId, size = 96 }: { objectId: number; size?: number }) {
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
    `<div style="font-family:monospace;font-weight:700;font-size:15px;color:#0f172a">${formatObjectId(objectId)}</div>` +
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
    `<!doctype html><html><head><title>Etikett ${formatObjectId(objectId)}</title>` +
    `<style>@page{margin:8mm} body{font-family:Inter,system-ui,sans-serif;margin:0;` +
    `display:flex;align-items:center;justify-content:center;min-height:100vh}</style></head>` +
    `<body>${labelMarkup(objectId, title, subtitle, size)}<script>window.onload=function(){window.focus();window.print();};` +
    `window.onafterprint=function(){window.close();}<\/script></body></html>`,
  );
  w.document.close();
}
