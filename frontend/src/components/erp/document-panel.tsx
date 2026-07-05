'use client';

import { useState } from 'react';
import { FileText, FileDown, Hash } from 'lucide-react';
import { api } from '@/lib/api';
import type { OrderDocument } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { DocumentView } from '@/components/erp/document-editor';
import { PanelHeader } from '@/components/erp/fields';

// Panel des Dokument-Schritts im Auftrag: zeigt das Dokument im Inexxio-Design + PDF-Download.
// Es gibt keine Aktion – das Dokument wird bei der Auftragsfreigabe eingefroren (nummeriert)
// und ist ab dann unveränderlich. Vor der Freigabe zeigt der Auftrag die Vorlage-Vorschau.
export function DocumentPanel({ document }: { document: OrderDocument | null }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const frozen = !!(document?.done && document?.object_id);

  async function download() {
    if (!document?.object_id) return;
    setBusy(true); setErr(null);
    try { await api.openDocumentPdf(document.object_id); }
    catch (e) { setErr(e instanceof Error ? e.message : 'PDF konnte nicht geladen werden'); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E9E7E1', borderRadius: 12, padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <PanelHeader
        icon={FileText}
        title="Dokument"
        tone="#E51A14"
        info="Wird bei der Auftragsfreigabe als nummeriertes, unveränderliches Dokument eingefroren."
        right={frozen ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 700, color: '#6E6E73', fontVariantNumeric: 'tabular-nums' }}>
            <Hash size={12} /> {fmtObjId(document!.object_id)}
          </span>
        ) : (
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#C8861A', background: '#FBF1DE', padding: '2px 8px', borderRadius: 999 }}>
            Vorschau · noch nicht ausgestellt
          </span>
        )}
      />

      {frozen && (
        <button onClick={download} disabled={busy} style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          alignSelf: 'flex-start', minHeight: 44, padding: '0 18px', borderRadius: 10,
          border: 'none', background: '#E51A14', color: '#fff', fontSize: 14, fontWeight: 600,
          cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
        }}>
          <FileDown size={16} /> {busy ? 'Wird geladen…' : 'Als PDF herunterladen'}
        </button>
      )}
      {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}

      <DocumentView
        content={document?.content ?? null}
        objectNr={frozen ? fmtObjId(document!.object_id) : null}
        issuedAt={document?.issued_at ?? null}
        version={document?.version ?? null}
      />
    </div>
  );
}
