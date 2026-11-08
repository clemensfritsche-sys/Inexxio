'use client';

import { useErpNav } from './obj-id';

/**
 * **Die Nummer einer Einzelinstanz — `100000736-1`, mit leisem Suffix.** Die Objektnummer
 * normal, der Suffix kleiner und leiser – vollständig, denn sie wird gescannt und zitiert.
 *
 * Sie führt zu ihrem Datensatz (Auftrag §3) über die bestehende Navigation (`ErpNavContext`);
 * ohne Navigation im Kontext (Etikett, Dialog) bleibt sie stiller Text. Wer eine
 * Einzelinstanz-Nummer zeigt, nimmt dieses Bauteil.
 */
export function UnitNumber({ value, size = 12.5 }: {
  /** `<Objektnummer>-<Suffix>`. Etwas anderes wird unverändert durchgereicht. */
  value: string;
  size?: number;
}) {
  const nav = useErpNav();
  const cut = value.lastIndexOf('-');
  const base = cut > 0 ? value.slice(0, cut) : value;
  const suffix = cut > 0 ? value.slice(cut) : '';
  const objectId = /^\d+$/.test(base) ? Number(base) : null;
  const body = (
    <>
      {base}
      {suffix && (
        <span style={{ fontSize: size - 1.5, color: 'var(--fg-4)', letterSpacing: '.01em' }}>
          {suffix}
        </span>
      )}
    </>
  );

  if (!nav || objectId === null) {
    return (
      <span className="ix-tnum" style={{ fontSize: size, whiteSpace: 'nowrap' }}>{body}</span>
    );
  }
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); nav(objectId); }}
      className="ix-tnum"
      style={{ fontSize: size, whiteSpace: 'nowrap', color: 'inherit', textAlign: 'left' }}
      data-tip={`Einzelinstanz ${value} – Datensatz öffnen`}
    >
      {body}
    </button>
  );
}
