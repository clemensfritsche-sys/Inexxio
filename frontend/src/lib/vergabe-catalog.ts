// ⚠ GENERIERT aus backend/app/domain/vergabe.py – NICHT EDITIEREN.
//   Neu erzeugen: cd backend && python -m scripts.dump_vergabe
//
// **Der Zyklus ist eine Quelle, kein Spiegel.** Ein neuer Kanal wird ausschliesslich im
// Backend ergänzt und ist damit auch hier wählbar; die Zustände samt Ampelton kommen von
// selbst mit. Was an einer konkreten Vergabe hängt (Beschriftung, Ton, mögliche
// Handlungen), reist mit **ihren** Daten – hier steht nur, was es ohne sie zu wissen gibt.

/** Ampelton eines Zustands. Die Farbwerte stehen in den Design-Tokens. */
export type AwardTone = 'done' | 'pending' | 'danger';

export interface AwardState {
  value: string;
  label: string;
  tone: AwardTone;
  /** Endgültig – für **diese** Vergabe gibt es keinen Weg mehr. */
  terminal: boolean;
  /** Ab hier ist ein **Zweiter gebunden**; das System rührt nichts mehr an, es meldet. */
  binding: boolean;
  /** Verlangt der Übergang hierher einen Grund? */
  needsReason: boolean;
}

export interface AwardChannel {
  value: string;
  label: string;
  hint: string;
  /** Bringt dieser Kanal von sich aus Angebote? «Selbst bestellt» nicht. */
  offers: boolean;
}

export const AWARD_STATES: readonly AwardState[] = [
  {
    "value": "angefragt",
    "label": "Angefragt",
    "tone": "pending",
    "terminal": false,
    "binding": false,
    "needsReason": false
  },
  {
    "value": "angeboten",
    "label": "Angeboten",
    "tone": "pending",
    "terminal": false,
    "binding": false,
    "needsReason": false
  },
  {
    "value": "vergeben",
    "label": "Vergeben",
    "tone": "pending",
    "terminal": false,
    "binding": true,
    "needsReason": false
  },
  {
    "value": "erbracht",
    "label": "Erbracht",
    "tone": "done",
    "terminal": true,
    "binding": true,
    "needsReason": false
  },
  {
    "value": "abgelehnt",
    "label": "Abgelehnt",
    "tone": "danger",
    "terminal": true,
    "binding": false,
    "needsReason": false
  },
  {
    "value": "gescheitert",
    "label": "Gescheitert",
    "tone": "danger",
    "terminal": true,
    "binding": false,
    "needsReason": true
  }
] as const;

export const AWARD_CHANNELS: readonly AwardChannel[] = [
  {
    "value": "plattform",
    "label": "Plattform",
    "hint": "Angebote kommen aus einer Schnittstelle – in Sekunden, günstigstes vorgewählt",
    "offers": true
  },
  {
    "value": "portal",
    "label": "Lieferantenportal",
    "hint": "Der Dritte trägt sein Angebot selbst ein",
    "offers": true
  },
  {
    "value": "selbst",
    "label": "Selbst bestellt",
    "hint": "Kein Angebotsvergleich – der Vorgang wird nur dokumentiert",
    "offers": false
  }
] as const;

/** Ein Zustand zu seinem Schlüssel – unbekannt = `undefined`, kein Rückfall. */
export function awardState(value: string): AwardState | undefined {
  return AWARD_STATES.find((s) => s.value === value);
}

/** Ein Kanal zu seinem Schlüssel. */
export function awardChannel(value: string): AwardChannel | undefined {
  return AWARD_CHANNELS.find((c) => c.value === value);
}
