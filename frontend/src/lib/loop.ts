import { LOOP_EVERY, LOOP_TAKES, type LoopEvery, type LoopTake } from '@/lib/vocab';

/** Ein Takt aus einer Eingabe – nur einer, den es gibt (`domain/loop.EVERY`). */
export function everyOf(v: unknown): LoopEvery | null {
  return (Object.keys(LOOP_EVERY) as LoopEvery[]).find((k) => k === v) ?? null;
}

/** Was eine Lager-Zeile nimmt – nur ein Wert, den es gibt (`domain/loop.TAKES`). */
export function takeOf(v: unknown): LoopTake | null {
  return (Object.keys(LOOP_TAKES) as LoopTake[]).find((k) => k === v) ?? null;
}
