'use client';

/**
 * **Was aus einem Vorschlag nicht in den Entwurf passte** (`lib/proposal-draft`, `left`) – es
 * verschwindet nicht still, der Entwurf nennt es oben. Leer: nichts.
 */
export function ProposalLeft({ left }: { left: readonly string[] }) {
  if (!left.length) return null;
  return (
    <div className="mb-3 text-sm max-w-[880px] mx-auto px-3 py-2 rounded-ds-lg"
      style={{ color: 'var(--warning)', background: 'var(--warning-bg)' }}>
      <div style={{ fontWeight: 600 }}>Aus dem Vorschlag nicht übernommen – bitte selbst prüfen:</div>
      <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
        {left.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    </div>
  );
}
