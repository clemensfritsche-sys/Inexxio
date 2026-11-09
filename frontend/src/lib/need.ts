import type { StepNeed } from '@/types';

/**
 * ►►► **Was eine Zeile der Stückliste anbietet – nur, was gerade Sinn ergibt** (#723). ◄◄◄
 *
 *     am Arbeitsort genug           →  nichts. Einfach scannen.
 *     genug da, liegt nur woanders  →  «Holen lassen» – die Handlung ist ein Transport.
 *     reicht nicht, Bestand da      →  «Andere Instanz wählen».
 *     gar kein Bestand              →  nur «Nachschub». Wählen liesse sich nichts.
 *
 * **Verglichen wird gegen den Bedarf des MODULS, nicht gegen den Anteil einer Zeile** (#1027):
 * zugeteilt wird erst beim Bestätigen (`consumption.plan`, FIFO), Reservierungen gibt es nicht.
 * Der gemeinsame freie Bestand steht darum gegen `need.required` (Menge je Stück × alle Stücke
 * vor dem Modul) – derselbe Massstab, gegen den der Dienst prüft. Wie viel «am Ort» liegt,
 * sagt der Server (`here`, über die Halter-Kette); die Oberfläche vergleicht keine Halter.
 */
interface NeedOffer {
  /** Gebraucht an diesem Modul (nicht an dieser Zeile). */
  required: number;
  /** Wie viele Produkt-Stücke am Modul davorstehen – die Bezugsgrösse der Zahl. */
  units: number;
  /** Wie viel davon am Arbeitsort liegt (ohne Ortsbedarf: alles Verfügbare). */
  here: number;
  /** Reicht der freie Bestand für das Modul? */
  enough: boolean;
  /** Genug da, nur nicht am Arbeitsort. */
  misplaced: boolean;
  /** «Andere Instanz wählen» anbieten. */
  choose: boolean;
  /** «Holen lassen» mit dieser Menge – `0` heisst: nicht anbieten. */
  haul: number;
  /** «Nachschub» anbieten. */
  supply: boolean;
}

export function needOffer(
  need: Pick<StepNeed, 'required' | 'per_unit' | 'available' | 'here' | 'place'>,
): NeedOffer {
  const required = need.required;
  const units = need.per_unit > 0 ? required / need.per_unit : 0;
  const enough = need.available >= required;
  const empty = need.available <= 0;
  const here = need.place ? (need.here ?? 0) : need.available;
  const misplaced = enough && here < required;
  return {
    required, units, here, enough, misplaced,
    choose: misplaced || (!enough && !empty),
    haul: misplaced ? required - here : 0,
    supply: empty,
  };
}
