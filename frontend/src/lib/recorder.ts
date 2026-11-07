/**
 * ►►► **Aufnehmen – die reine Logik** (Phase 4 «Sprache», `docs/konzept/phase4-bauplan.md`). ◄◄◄
 *
 * Ohne React und ohne Browser-Schnittstellen: was ein Recorder ist, wie hochgeladen und wie
 * gewartet wird, kommt von aussen (`SessionDeps`). So prüft `scripts/recorder.test.mjs` die
 * Zählung der Abschnitte und Stücke und die Warteschlange mit Attrappen. Den Browser schliesst
 * `lib/use-recorder.ts` an (Mikrofon, `MediaRecorder`, Pegel, Wake Lock).
 *
 * - **Ein Stück alle 30 s** (`CHUNK_MS`, `MediaRecorder.start(timeslice)`): jedes
 *   `dataavailable` ist ein Stück und geht sofort hoch – bricht die Aufnahme ab, ist alles bis
 *   zum letzten Stück da.
 * - **Ein Abschnitt = 5 Minuten** (`SEGMENT_MS`): danach endet der Recorder und ein neuer
 *   beginnt am selben Mikrofon – jeder Abschnitt ist eine eigene, vollständige Datei, die
 *   Stück-Zählung beginnt wieder bei 0.
 * - **Höchstens 3 Stunden** (`MAX_MS`), dann hält die Aufnahme von selbst an.
 * - **Der Reihe nach hoch – ein Stück wird nie aufgegeben, solange die Seite lebt**
 *   (`UploadQueue`): wiederholt mit wachsender Pause bis höchstens 30 s, ohne Ende, jeder
 *   Versuch mit Zeitgrenze (`UPLOAD_TIMEOUT_MS`). Aufgegeben wird nur, was der Server abweist
 *   (`retryable`), und das meldet sich (`onFail`).
 *
 * Ohne Imports, damit der Test die echte Quelle transpiliert.
 */

export const CHUNK_MS = 30_000;
export const SEGMENT_MS = 5 * 60_000;
export const MAX_MS = 3 * 60 * 60_000;
export const BITRATE = 24_000;
/** Die Pausen vor den Wiederholungen eines Stücks – danach immer `RETRY_MAX_MS`, ohne Ende. */
export const RETRY_MS: readonly number[] = [1_000, 2_000, 4_000, 8_000, 16_000];
const RETRY_MAX_MS = 30_000;
/** So lange darf ein Versuch dauern – dann wird er abgebrochen und wiederholt (nichts hängt). */
export const UPLOAD_TIMEOUT_MS = 30_000;
/** Die Sicherheitsgrenze, wie lange der Stopp auf das `stop`-Ereignis eines Recorders wartet –
 *  davor kommt garantiert sein letztes Stück; meldet er sich nie, hält das den Stopp nicht ewig. */
export const STOP_WAIT_MS = 60_000;

/** Die Pause vor dem `n`-ten neuen Versuch (ab 0): 1, 2, 4, 8, 16, dann 30 s. */
function retryPause(n: number): number {
  return n < RETRY_MS.length ? RETRY_MS[n] : RETRY_MAX_MS;
}

/** Was der Browser aufnehmen kann – Opus in WebM, sonst MP4 (Safari), sonst seine Vorgabe (''). */
export function pickMime(supported: (mime: string) => boolean): string {
  for (const mime of ['audio/webm;codecs=opus', 'audio/mp4']) if (supported(mime)) return mime;
  return '';
}

/** Die Laufzeit einer Aufnahme: «04:07», ab einer Stunde «1:04:07». Kein Datum – eine Dauer. */
export function runtime(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const two = (n: number) => String(n).padStart(2, '0');
  return h ? `${h}:${two(m)}:${two(s)}` : `${two(m)}:${two(s)}`;
}

/** Ein Stück der Aufnahme: Abschnitt (ab 0), Stück im Abschnitt (ab 0), die Daten. */
export interface Chunk<B = unknown> { segment: number; seq: number; blob: B }

/** Wie weit die Aufnahme oben ist – für die Anzeige. */
export interface QueueState {
  /** Stücke, die noch nicht oben sind (inkl. dem, das gerade hochgeht). */
  pending: number;
  /** Stücke, die der Server abwies (aufgegeben). */
  failed: number;
  /** Bis wohin (Sekunden Aufnahme, geschätzt aus Abschnitt und Stück) alles oben ist. */
  uploadedSeconds: number;
  /** Ein Stück ist gescheitert und wartet auf den nächsten Versuch – «wartet auf Netz». */
  waiting: boolean;
}

interface QueueDeps<B> {
  /** Ein Stück hochladen; `signal` bricht den Versuch nach `timeoutMs` ab. */
  send: (chunk: Chunk<B>, signal: AbortSignal) => Promise<unknown>;
  wait: (ms: number) => Promise<void>;
  /** Lohnt ein neuer Versuch? (Eine Abweisung wie 409 «schon fertig» nicht.) */
  retryable?: (error: unknown) => boolean;
  /** Ein Stück wurde aufgegeben (abgewiesen). */
  onFail?: (chunk: Chunk<B>, error: unknown) => void;
  /** Das erste Mal, dass ein Stück warten muss – einmal je Warteschlange. */
  onStall?: (error: unknown) => void;
  onChange?: (state: QueueState) => void;
  timeoutMs?: number;
}

/**
 * **Die Warteschlange der Stücke** – eines nach dem anderen, in der Reihenfolge, in der sie
 * kamen. `drain()` wartet, bis sie leer ist (Stopp).
 */
export class UploadQueue<B = unknown> {
  private items: Chunk<B>[] = [];
  private running: Promise<void> | null = null;
  private failedCount = 0;
  private uploadedUntil = 0;
  private waiting = false;
  private stalled = false;

  constructor(private readonly deps: QueueDeps<B>) {}

  push(chunk: Chunk<B>): void {
    this.items.push(chunk);
    this.changed();
    if (!this.running) this.running = this.run().finally(() => { this.running = null; });
  }

  /** Bis alles oben (oder abgewiesen) ist. */
  async drain(): Promise<void> {
    while (this.running) await this.running;
  }

  get state(): QueueState {
    return { pending: this.items.length, failed: this.failedCount, uploadedSeconds: this.uploadedUntil, waiting: this.waiting };
  }

  private changed() { this.deps.onChange?.(this.state); }

  private async run(): Promise<void> {
    while (this.items.length) {
      const chunk = this.items[0];
      if (await this.attempt(chunk)) {
        // Das letzte Stück eines Abschnitts ist kürzer – über das Ende des Abschnitts hinaus zählt nichts.
        const end = (chunk.segment * SEGMENT_MS + Math.min((chunk.seq + 1) * CHUNK_MS, SEGMENT_MS)) / 1000;
        this.uploadedUntil = Math.max(this.uploadedUntil, end);
      }
      this.items.shift();
      this.changed();
    }
  }

  /** Ein Versuch mit Zeitgrenze – hängt die Verbindung, wird er abgebrochen. */
  private async once(chunk: Chunk<B>): Promise<void> {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), this.deps.timeoutMs ?? UPLOAD_TIMEOUT_MS);
    try {
      await this.deps.send(chunk, ctl.signal);
    } finally {
      clearTimeout(timer);
    }
  }

  /** Ein Stück: Versuche, bis es oben ist – `false` nur, wenn der Server es abweist. */
  private async attempt(chunk: Chunk<B>): Promise<boolean> {
    for (let i = 0; ; i++) {
      try {
        await this.once(chunk);
        if (this.waiting) { this.waiting = false; this.changed(); }
        return true;
      } catch (e) {
        if (!(this.deps.retryable?.(e) ?? true)) {
          this.failedCount += 1;
          this.waiting = false;
          this.deps.onFail?.(chunk, e);
          return false;
        }
        if (!this.waiting) { this.waiting = true; this.changed(); }
        if (!this.stalled) { this.stalled = true; this.deps.onStall?.(e); }
        await this.deps.wait(retryPause(i));
      }
    }
  }
}

/** Was die Sitzung von einem Recorder braucht – `MediaRecorder` erfüllt es. */
export interface RecorderLike<B = unknown> {
  start(timeslice: number): void;
  stop(): void;
  /** Das Aufgenommene sofort als Stück liefern (Seite wird verlassen). */
  requestData?(): void;
  ondataavailable: ((e: { data: B }) => void) | null;
  onstop: ((e: unknown) => void) | null;
}

interface SessionDeps<B> {
  /** Ein neuer Recorder am selben Mikrofon – je Abschnitt einer. */
  createRecorder: () => RecorderLike<B>;
  /** Grösse der Daten – ein leeres Stück geht nicht hoch. */
  sizeOf: (blob: B) => number;
  queue: UploadQueue<B>;
  /** Ein Zeitgeber, der sich abbrechen lässt (Abschnitt, Höchstdauer). */
  every: (fn: () => void, ms: number) => () => void;
  after: (fn: () => void, ms: number) => () => void;
  /** Die Aufnahme hielt von selbst an (Höchstdauer). */
  onLimit?: () => void;
}

/**
 * **Eine Aufnahme** – Abschnitte und Stücke zählen, Recorder wechseln, anhalten.
 *
 * Jeder Recorder kennt seinen Abschnitt und zählt seine Stücke selbst: das letzte Stück eines
 * Abschnitts (es kommt nach `stop()`) trägt noch dessen Nummer, auch wenn der nächste schon
 * läuft.
 */
export class RecordingSession<B = unknown> {
  private segment = -1;
  private current: RecorderLike<B> | null = null;
  private lastStopped: Promise<void> = Promise.resolve();
  /** Abschnitte, aus denen mindestens ein Stück kam. */
  private withData = new Set<number>();
  private cancel: (() => void)[] = [];
  private stopping: Promise<number> | null = null;

  constructor(private readonly deps: SessionDeps<B>) {}

  /** Wie viele Abschnitte es gibt (Stopp → `{segments}`). */
  get segments(): number { return this.withData.size ? Math.max(...this.withData) + 1 : 0; }

  get active(): boolean { return !!this.current && !this.stopping; }

  start(): void {
    if (this.current || this.stopping) return;
    this.next();
    this.cancel.push(this.deps.every(() => this.rotate(), SEGMENT_MS));
    this.cancel.push(this.deps.after(() => { this.deps.onLimit?.(); void this.stop(); }, MAX_MS));
  }

  /** Neuer Abschnitt: den laufenden Recorder beenden, am selben Mikrofon einen neuen starten. */
  rotate(): void {
    if (!this.current || this.stopping) return;
    this.end(this.current);
    this.next();
  }

  /** Was bisher aufgenommen ist, sofort als Stück hochschicken (die Seite wird verlassen). */
  flush(): void {
    if (this.current && !this.stopping) this.current.requestData?.();
  }

  /** Anhalten: letzten Recorder beenden, sein letztes Stück abwarten, Warteschlange leeren.
   *  Gibt die Zahl der Abschnitte. Mehrfach gerufen – dasselbe Versprechen. */
  stop(): Promise<number> {
    if (this.stopping) return this.stopping;
    this.cancel.forEach((c) => c());
    this.cancel = [];
    if (this.current) this.end(this.current);
    this.current = null;
    this.stopping = this.lastStopped.then(() => this.deps.queue.drain()).then(() => this.segments);
    return this.stopping;
  }

  /** Nach dem Stopp: alle Recorder haben ihr letztes Stück geliefert – das Mikrofon darf zu,
   *  auch wenn noch Stücke hochgehen. */
  recorded(): Promise<void> { return this.lastStopped; }

  private next(): void {
    this.segment += 1;
    const segment = this.segment;
    let seq = 0;
    const rec = this.deps.createRecorder();
    rec.ondataavailable = (e) => {
      if (!this.deps.sizeOf(e.data)) return;
      this.withData.add(segment);
      this.deps.queue.push({ segment, seq, blob: e.data });
      seq += 1;
    };
    this.current = rec;
    rec.start(CHUNK_MS);
  }

  /** Einen Recorder beenden – `lastStopped` wartet auf sein `stop`-Ereignis (davor kommt sein
   *  letztes Stück); höchstens `STOP_WAIT_MS`, falls er sich nie meldet. */
  private end(rec: RecorderLike<B>): void {
    const done = new Promise<void>((resolve) => {
      const cancel = this.deps.after(resolve, STOP_WAIT_MS);
      rec.onstop = () => { cancel(); resolve(); };
    });
    const before = this.lastStopped;
    this.lastStopped = before.then(() => done);
    rec.stop();
  }
}
