'use client';

/**
 * PRIMÄRE Dokument-Sicht am ERP-Benutzer-Datensatz: die vollständige Dokument-Beteiligung
 * einer Person – offene Freigaben (als Partei), offene Anerkennungen (als Publikum) und die
 * erledigten Vorgänge. Read-only (Personal-Oversight; unterschrieben/anerkannt wird von der
 * benannten Person selbst im Konto/Auftrag). Das Profil «Meine Dokumente» spiegelt dieselben
 * Daten – hier ist die Quelle/Verwaltung.
 */

import { useEffect, useState } from 'react';
import { PenLine, ShieldCheck, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { UserDocumentOverview, CompanySettings } from '@/types';
import { DocumentView } from '@/components/erp/document-editor';
import { formatObjectId } from '@/lib/utils';

type AnyContent = Parameters<typeof DocumentView>[0]['content'];

export function UserDocumentsOverview({ objectId }: { objectId: number | null | undefined }) {
  const [ov, setOv] = useState<UserDocumentOverview | null>(null);
  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (objectId == null) { setLoading(false); return; }
    let cancelled = false;
    api.getUserDocumentOverview(objectId)
      .then((o) => { if (!cancelled) setOv(o); })
      .catch(() => { if (!cancelled) setOv({ signoffs: [], acks: [], history: [] }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    api.getPublicSettings().then((s) => { if (!cancelled) setCompany(s); }).catch(() => {});
    return () => { cancelled = true; };
  }, [objectId]);

  if (loading) {
    return <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-4)', fontSize: 13, padding: '4px 0' }}><Loader2 size={15} className="animate-spin" /> Wird geladen…</div>;
  }
  const signoffs = ov?.signoffs ?? [];
  const acks = ov?.acks ?? [];
  const history = ov?.history ?? [];
  const nothing = signoffs.length === 0 && acks.length === 0 && history.length === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {nothing && (
        <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Diese Person ist an keinem Dokument beteiligt.</div>
      )}

      {signoffs.length > 0 && (
        <Group icon={PenLine} label="Offen: zur Freigabe">
          {signoffs.map((s) => (
            <Row key={`so-${s.signoff_id}`} title={s.title} objectNumber={s.object_number ?? null}
              status={s.status === 'rejected' ? 'Abgelehnt' : (s.actionable ? 'Offen · an der Reihe' : 'Wartet auf andere Partei')}
              tone={s.status === 'rejected' ? 'red' : 'amber'} content={s.content as AnyContent} company={company}
              icon={s.actionable ? undefined : Clock} />
          ))}
        </Group>
      )}

      {acks.length > 0 && (
        <Group icon={ShieldCheck} label="Offen: zur Anerkennung">
          {acks.map((a) => (
            <Row key={`ack-${a.kind}-${a.object_number}`} title={a.title} objectNumber={a.object_number ?? null}
              status="Anerkennung offen" tone="amber" content={a.content as AnyContent} company={company} />
          ))}
        </Group>
      )}

      {history.length > 0 && (
        <Group icon={CheckCircle2} label="Erledigt">
          {history.map((h, i) => (
            <Row key={`h-${i}`} title={h.title} objectNumber={h.object_number ?? null}
              status={`${h.label}${h.acted_at ? ` · ${new Date(h.acted_at).toLocaleDateString('de-CH')}` : ''}`}
              tone="green" content={h.content as AnyContent} company={company} />
          ))}
        </Group>
      )}
    </div>
  );
}

function Group({ icon: Icon, label, children }: { icon: React.ElementType; label: string; children: React.ReactNode }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, font: '700 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)' }}>
        <Icon size={13} /> {label}
      </div>
      {children}
    </section>
  );
}

function Row({ title, objectNumber, status, tone, content, company, icon: Icon }: {
  title: string; objectNumber: number | null; status: string;
  tone: 'amber' | 'green' | 'red'; content: AnyContent; company: Partial<CompanySettings> | null;
  icon?: React.ElementType;
}) {
  const [open, setOpen] = useState(false);
  const c = tone === 'green' ? { bg: '#DCFCE7', fg: '#15803D' } : tone === 'red' ? { bg: '#FDECEA', fg: '#dc2626' } : { bg: '#FBF1DE', fg: '#C8861A' };
  return (
    <div style={{ border: '1px solid var(--border-1)', borderRadius: 10, background: '#fff', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 13.5px var(--font-body)', color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</div>
          {objectNumber != null && <div style={{ fontSize: 11.5, color: 'var(--fg-4)' }}>{formatObjectId(objectNumber)}</div>}
        </div>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 999, background: c.bg, color: c.fg, font: '600 11px var(--font-body)', whiteSpace: 'nowrap' }}>
          {Icon && <Icon size={11} />} {status}
        </span>
        {content && <button onClick={() => setOpen((v) => !v)} style={{ padding: '5px 11px', borderRadius: 8, border: '1px solid var(--border-1)', background: '#fff', color: 'var(--fg-2)', font: '600 12px var(--font-body)', cursor: 'pointer', flexShrink: 0 }}>{open ? 'Schliessen' : 'Ansehen'}</button>}
      </div>
      {open && content && (
        <div style={{ padding: 14, background: 'var(--bg-2)' }}>
          <DocumentView content={content} objectNr={objectNumber ? formatObjectId(objectNumber) : null} company={company} />
        </div>
      )}
    </div>
  );
}
