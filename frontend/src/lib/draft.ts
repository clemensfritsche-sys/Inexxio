/**
 * ►►► **Der Entwurf im «+»** – was in der Eingabe steht, bis es gesendet ist. ◄◄◄
 *
 * Wie bei Claude: schliesst man das «+», steht der Text beim nächsten Öffnen noch da. Er gehört
 * nur diesem Browser (eine Bequemlichkeit, kein Datensatz – vor dem Senden gibt es nichts am
 * Server). `recordings` = die Aufnahmen, deren Text schon im Feld steht: sie kommen nicht ein
 * zweites Mal hinein und gelten erst mit dem Senden als gesendet. Ohne Speicher im Browser (privat,
 * blockiert) geht nur das Behalten verloren, sonst nichts.
 */

export interface Draft { text: string; place: string; recordings: number[] }

const KEY = 'inexxio.capture.draft';
export const EMPTY_DRAFT: Draft = { text: '', place: '', recordings: [] };

export function loadDraft(): Draft {
  try {
    const d = JSON.parse(localStorage.getItem(KEY) || 'null') as Partial<Draft> | null;
    return {
      text: typeof d?.text === 'string' ? d.text : '',
      place: typeof d?.place === 'string' ? d.place : '',
      recordings: Array.isArray(d?.recordings) ? d.recordings.filter((x): x is number => typeof x === 'number') : [],
    };
  } catch { return EMPTY_DRAFT; }   // kein Speicher im Browser: ein leerer Entwurf
}

export function saveDraft(d: Draft): void {
  try {
    if (!d.text && !d.place && !d.recordings.length) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, JSON.stringify(d));
  } catch { /* kein Speicher im Browser: der Entwurf lebt nur, solange das «+» offen ist */ }
}
