'use client';

import { useState } from 'react';
import { DetailBody, DetailHeader, HeaderAction } from '@/components/erp/detail-frame';
import { ErrorText } from '@/components/erp/hints';
import { Segmented } from '@/components/erp/controls';
import { DocumentPaper } from '@/components/erp/document-detail';
import { Sheet } from '@/components/erp/document-draft';
import type { PaperOut } from '@/types';

/**
 * ►►► **Die Vorschau eines Papiers – vor der Freigabe.** ◄◄◄ Genau das Papier, das die
 * Handlung hinausgäbe (vom Server in einem zurückgerollten Lauf gerechnet). «Freigeben» führt
 * die Handlung aus: das Papier wird ein Dokument und geht per Mail an die Partei. Gehen mehrere
 * (eine Offerte an zwei Kunden), stehen sie als Wahl nebeneinander.
 */
export function PaperSheet({ papers, onCancel, onRelease }: {
  papers: PaperOut[]; onCancel: () => void; onRelease: () => Promise<void>;
}) {
  const [at, setAt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const shown = papers[Math.min(at, papers.length - 1)];
  const title = `${shown.word}${shown.number ? ` ${shown.number}` : ''}`;

  async function release() {
    setBusy(true);
    setError('');
    try { await onRelease(); } catch (e) { setError((e as Error).message); setBusy(false); }
  }

  return (
    <Sheet>
      <DetailHeader type="document" title={title} objectIdText="—"
        objectIdHint="Die Nummer entsteht mit der Freigabe." onBack={onCancel}
        actions={<>
          <HeaderAction label={busy ? 'Freigeben…' : 'Freigeben'} disabled={busy}
            hint={papers.length > 1 ? `${papers.length} Papiere gehen hinaus` : 'Wird ein Dokument und geht per Mail hinaus'}
            onClick={() => void release()} />
          <HeaderAction label="Abbrechen" tone="neutral" onClick={onCancel} />
        </>} />
      <div className="flex-1 overflow-y-auto" style={{ padding: '24px clamp(14px, 4vw, 28px) 88px' }}>
        <DetailBody gap={18}>
          {error && <ErrorText msg={error} />}
          {papers.length > 1 && (
            <Segmented value={String(at)} onChange={(v) => setAt(Number(v))}
              options={papers.map((p, i) => ({ value: String(i), label: `${p.word} ${i + 1}` }))} />
          )}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <div style={{ width: '100%', maxWidth: 640 }}>
              <DocumentPaper url={null} mime="text/html" html={shown.html} />
            </div>
          </div>
        </DetailBody>
      </div>
    </Sheet>
  );
}
