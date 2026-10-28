'use client';

import { File, FileSpreadsheet, FileText, Film, Image as ImageIcon, Lock, X } from 'lucide-react';
import { assetUrl } from '@/lib/api';
import { useDocumentsOf } from '@/lib/queries';
import { formatObjectId } from '@/lib/utils';
import { SectionSep } from '@/components/erp/fields';
import { useErpNav } from '@/components/erp/obj-id';
import type { DocumentRefOut, DocumentSummary } from '@/types';

/**
 * ►►► **Die Dokumente eines Datensatzes – unten, zentriert, als Kacheln.** ◄◄◄
 *
 * Regel 4: ein Dokument erscheint genau dort, wohin seine Referenz zeigt. Unter der Kachel
 * steht nur die **Art**; Name und Nummer im Hover. Ein Klick öffnet das Dokument. Ein «+»
 * gibt es hier nicht – neue Dokumente entstehen immer über den Feed («+» → Dokument), damit
 * es genau EINEN Anlageweg gibt.
 *
 * Ohne Dokument steht nichts da – auch kein leerer Abschnitt.
 */
export function DocumentTiles({ objectId }: { objectId: number | null | undefined }) {
  // Nachgeladen nach jeder Änderung an Dokumenten oder Aufträgen (`lib/feed.TOUCHES`).
  const docs = useDocumentsOf(objectId).data ?? [];
  if (!docs.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 8 }}>
      <SectionSep label="Dokumente" />
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '18px 12px', padding: '6px 0 4px' }}>
        {docs.map((d) => <DocumentTile key={d.object_id} doc={d} />)}
      </div>
    </div>
  );
}

/** Ein Symbol je Sorte – wo es kein Vorschaubild gibt. */
export function mimeIcon(mime: string) {
  if (mime.startsWith('image/')) return ImageIcon;
  if (mime.startsWith('video/')) return Film;
  if (mime.includes('sheet') || mime.includes('excel') || mime === 'text/csv') return FileSpreadsheet;
  if (mime === 'application/pdf' || mime === 'text/html' || mime.startsWith('text/')) return FileText;
  return File;
}

function DocumentTile({ doc }: { doc: DocumentSummary }) {
  const nav = useErpNav();
  const Icon = mimeIcon(doc.mime);
  return (
    <button type="button" onClick={() => nav?.(doc.object_id)}
      data-tip={`${doc.art} · ${doc.name} · ${formatObjectId(doc.object_id)}`}
      style={{ width: 92, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
               background: 'none', border: 'none', cursor: nav ? 'pointer' : 'default', padding: 0 }}>
      <span style={{ position: 'relative', width: 62, height: 86, borderRadius: 4, overflow: 'hidden',
                     border: '1px solid var(--border-2)', background: 'var(--bg-1)', boxShadow: 'var(--shadow-sm)',
                     display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--fg-4)' }}>
        {doc.preview_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={assetUrl(doc.preview_url)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
          : <Icon size={22} />}
      </span>
      <span style={{ font: '600 11.5px/1.25 var(--font-body)', color: 'var(--fg-2)', textAlign: 'center',
                     overflowWrap: 'anywhere' }}>{doc.art}</span>
    </button>
  );
}

/**
 * ►►► **Eine Referenz als Chip.** ◄◄◄ Ein Pflichtfeld trägt ein **Schloss** statt ×: geändert
 * wird es nur dort, wo das Feld steht, und leer wird es nie (Regel 6). Ein Vorschlag der KI
 * ist gestrichelt.
 */
export function RefChip({ objectId, label, lockTip, proposed, onRemove }: {
  objectId: number; label: string; lockTip?: string | null; proposed?: boolean; onRemove?: () => void;
}) {
  const nav = useErpNav();
  return (
    <span data-tip={lockTip ? `Pflichtfeld: ${lockTip} – ändern nur dort` : undefined}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 6px 4px 10px',
               borderRadius: 999, maxWidth: '100%',
               border: `1px ${proposed ? 'dashed var(--warning)' : 'solid var(--border-2)'}`,
               background: proposed ? 'var(--warning-bg)' : 'var(--bg-1)',
               font: '500 13px var(--font-body)', color: 'var(--fg-1)' }}>
      <button type="button" onClick={() => nav?.(objectId)} disabled={!nav}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0, background: 'none',
                 border: 'none', padding: 0, cursor: nav ? 'pointer' : 'default', color: 'inherit', font: 'inherit' }}>
        <span className="erp-objid" style={{ font: '500 13px var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
          {formatObjectId(objectId)}
        </span>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      </button>
      {lockTip
        ? <span style={{ display: 'flex', color: 'var(--fg-4)' }}><Lock size={13} /></span>
        : onRemove && (
          <button type="button" onClick={onRemove} aria-label="Referenz entfernen" data-tip="Referenz entfernen"
            style={{ display: 'flex', background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--fg-4)' }}>
            <X size={13} />
          </button>
        )}
    </span>
  );
}

/** Die Chips einer gespeicherten Referenzliste. */
export function RefChips({ refs, onRemove }: {
  refs: DocumentRefOut[]; onRemove?: (refId: number) => void;
}) {
  if (!refs.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {refs.map((r) => (
        <RefChip key={r.id} objectId={r.object_id} label={r.label} lockTip={r.field_label}
          onRemove={onRemove ? () => onRemove(r.id) : undefined} />
      ))}
    </div>
  );
}
