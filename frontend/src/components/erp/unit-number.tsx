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
 * **Eine Stelle für alle** (Testnotiz #681): wer eine Einzelinstanz-Nummer zeigt, nimmt
 * dieses Bauteil. Vier Orte hatten vorher vier Schreibweisen.
 */
export function UnitNumber({ value, size = 12.5 }: {
  /** `<Objektnummer>-<Suffix>`. Etwas anderes wird unverändert durchgereicht. */
  value: string;
  size?: number;
}) {
  const cut = value.lastIndexOf('-');
  const base = cut > 0 ? value.slice(0, cut) : value;
  const suffix = cut > 0 ? value.slice(cut) : '';
  return (
    <span className="ix-tnum" style={{ fontSize: size, whiteSpace: 'nowrap' }}>
      {base}
      {suffix && (
        <span style={{ fontSize: size - 1.5, color: 'var(--fg-4)', letterSpacing: '.01em' }}>
          {suffix}
        </span>
      )}
    </span>
  );
}
