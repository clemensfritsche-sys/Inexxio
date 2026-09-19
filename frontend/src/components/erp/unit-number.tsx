'use client';

import { useErpNav } from './obj-id';

/**
 * **Die Nummer einer Einzelinstanz — `100000736-1`, mit leisem Suffix.**
 *
 * Die Identität, die ein Mensch kennt und ausspricht, ist die **Objektnummer**; der
 * Suffix sagt nur, welches Stück davon gemeint ist. Beide gleich laut zu setzen macht
 * aus einer Nummer zwei, und in einer Liste von zwanzig Stücken springt dann jede Zeile
 * an, obwohl sich nur die letzte Stelle unterscheidet.
 *
 * Also: Nummer normal, Suffix eine Spur kleiner und in der leisesten Textfarbe – nah
 * genug, um als eine Angabe gelesen zu werden, leise genug, um nicht mitzurufen. Kein
 * Weglassen: die Nummer muss vollständig bleiben, sie wird gescannt und zitiert.
 *
 * **Sie führt zu ihrem Datensatz** (Auftrag §3). Der Teil vor dem Suffix **ist** die
 * Objektnummer der Instanz – es gibt nichts nachzuschlagen, und darum auch keinen Grund,
 * sie nicht anklickbar zu machen. Gesprungen wird über die **bestehende** Navigation
 * (`ErpNavContext`), dieselbe, mit der jede Objektnummer im ERP ihren Datensatz öffnet;
 * ein eigener Handler wäre ein zweiter Weg zur selben Sache. Ohne Navigation im Kontext
 * (Etikett, Dialog) bleibt sie stiller Text – die Fähigkeit hängt am Ort, nicht am
 * Aufrufer.
 *
 * **Eine Stelle für alle** (Testnotiz #681): wer eine Einzelinstanz-Nummer zeigt, nimmt
 * dieses Bauteil. Vier Orte hatten vorher vier Schreibweisen.
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
