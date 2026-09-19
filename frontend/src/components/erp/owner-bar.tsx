'use client';

import type { OwnerShare } from '@/types';
import { ValueBar } from '@/components/erp/module-ui';

/**
 * **Die Eigentums-Leiste — die zweite Aufteilung DERSELBEN Stücke.**
 *
 * *«Ich muss den globalen Überblick behalten und zugleich wissen, mit was ich als
 * jeweiliges Unternehmen wirtschaften kann.»* – Das sind zwei Fragen über dieselbe Menge:
 * die **Zustands**-Leiste teilt sie nach *was passiert damit*, diese hier nach *wem gehört
 * sie*. Übereinander gelesen beantworten sie die Lage vollständig, und weil beide über
 * denselben Umfang gehen, summieren sie sich auf dieselbe Zahl.
 *
 * ►►► **Dasselbe Bauteil, andere Segmente** (`module-ui.ValueBar`). ◄◄◄ Eine zweite
 * Leisten-Bauart wäre die Stelle, an der die eine eine Haarlinie bekommt und die andere
 * nicht.
 *
 * **Eine Auskunft, kein Bedienelement** – kein `onPick`, und das ist Absicht: der
 * Durchgriff auf die Nummern ist die **Zustands**-Leiste (ein Zustand → seine Instanzen →
 * ihre Nummern), und dort nennt jede Nummer ihren Eigentümer. Zwei Leisten, die beide
 * einen Ausschnitt öffnen, wären zwei Auswahlzustände über derselben Liste – und die
 * Frage «welcher gilt jetzt» hat dann keine Antwort. Ohne Handler ist `ValueBar` von
 * sich aus reine Anzeige (dieselbe Bauart wie der Verlauf eines Moduls).
 *
 * **Und es gibt sie nur, wenn es etwas zu unterscheiden gibt**: der Server liefert die
 * Liste leer, wenn alles uns gehört (`owners.shares`). Ein einziges Segment «Uns 20» über
 * einer Leiste, die ohnehin die Gesamtmenge zeigt, sagt nichts und kostet eine Zeile.
 */
export function OwnerBar({ owners, height = 10 }: {
  owners: OwnerShare[];
  height?: number;
}) {
  if (owners.length === 0) return null;
  return (
    <ValueBar
      height={height}
      segments={owners.map((o) => ({
        key: String(o.owner_object_id ?? 'us'),
        label: o.name,
        value: o.quantity,
        // ►►► **Kein Ampelton.** ◄◄◄ Fremdes Eigentum ist kein *Problem* – eine
        // Beistellung ist der Normalfall der Lohnfertigung. Die drei Farben des Hauses
        // sagen «gut · offen · Problem», und keine davon trifft hier zu. Also die leise
        // Stimme für das Eigene und gedämpftes Neutral für das Fremde; **unterschieden
        // wird über das Wort** – dieselbe Antwort wie bei drei Ampeltönen für sechs
        // Zustände (#789).
        color: o.ours ? 'var(--accent)' : 'var(--fg-4)',
        text: String(o.quantity),
        hint: o.ours
          ? `${o.quantity} × ${o.name} – damit lässt sich wirtschaften`
          : `${o.quantity} × ${o.name} – fremdes Eigentum`,
      }))}
    />
  );
}
