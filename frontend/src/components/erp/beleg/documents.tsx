'use client';

import { formatWhen } from '@/lib/when';
import { Section } from './shared';
import type { Filled } from './shared';

/**
 * **Die Dokumente – so, wie sie hinausgingen.** Jedes Dokument (Offerte,
 * Auftragsbestätigung, Rechnung, Gutschrift, Stornierung, Mahnung) ist beim Versand
 * eingefroren; der Link öffnet genau diese Fassung (in einem neuen Tab, zum Drucken als PDF).
 */
export function Documents({ d }: { d: Filled }) {
  if (!d.documents.length) return null;
  return (
    <Section title={d.docs_title} aside="so, wie sie hinausgingen">
      <div className="flex flex-col" style={{ gap: 6, minWidth: 0 }}>
        {d.documents.map((doc) => {
          const sent = formatWhen(doc.sent_at);
          return (
            <div key={doc.id} className="flex items-baseline" style={{ gap: 10, padding: '3px 0',
                                                                       minWidth: 0 }}>
              <span className="truncate" style={{ fontSize: 12.5, color: 'var(--fg-1)',
                                                  flex: '1 1 auto', minWidth: 0 }}>
                {doc.label}
                {doc.number && (
                  <span style={{ color: 'var(--fg-3)', fontSize: 11.5, marginLeft: 8 }}>
                    {doc.number}
                  </span>
                )}
              </span>
              <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: 'none' }}
                {...(sent.title ? { 'data-tip': sent.title } : {})}>
                {sent.text} · eingefroren
              </span>
              <a href={doc.url} target="_blank" rel="noopener noreferrer" style={{
                fontSize: 12, color: 'var(--accent-ink)', textDecoration: 'none', flex: 'none',
                borderBottom: '1px solid var(--accent)',
              }}>PDF</a>
            </div>
          );
        })}
      </div>
    </Section>
  );
}
