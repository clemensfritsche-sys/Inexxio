'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { api } from '@/lib/api';
import type { CompanySettings, LegalDocument } from '@/types';
import { DocumentView } from '@/components/erp/document-editor';
import { formatObjectId } from '@/lib/utils';

/**
 * Öffentliche Rechtsdokument-Ansicht (D — Zeiger auf einen Artikel).
 *
 * Löst den am Unternehmen gepflegten Artikel-Zeiger auf: trägt der hinterlegte Artikel
 * (bzw. sein Nachfolger via «Ersetzen») eine freigegebene, ausgestellte Dokument-Instanz
 * für ``kind``, wird sie im offiziellen Inexxio-Layout (identisch zum PDF, inkl. Briefkopf)
 * gerendert. Sonst greift der eingebaute ``fallback``-Rechtstext (migrationsfreundlich,
 * nie eine leere Seite).
 */
export function LegalDocument({ kind, fallback }: { kind: string; fallback: ReactNode }) {
  const [doc, setDoc] = useState<LegalDocument | null | undefined>(undefined);   // undefined = lädt
  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getLegalDocument(kind).then((d) => { if (!cancelled) setDoc(d); }).catch(() => { if (!cancelled) setDoc(null); });
    api.getPublicSettings().then((s) => { if (!cancelled) setCompany(s); }).catch(() => {});
    return () => { cancelled = true; };
  }, [kind]);

  if (doc === undefined) {
    return <div className="py-10 text-center text-sm text-fg-4">Wird geladen…</div>;
  }
  if (!doc || !doc.content) {
    return <>{fallback}</>;   // kein Zeiger / nicht auflösbar → eingebauter Text
  }
  return (
    <DocumentView
      content={doc.content}
      objectNr={doc.object_number ? formatObjectId(doc.object_number) : null}
      issuedAt={doc.document_date}
      company={company}
    />
  );
}
