'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { CameraOff, AlertTriangle, Flashlight, Search } from 'lucide-react';
import {
  objectCodes, offersFor, scanKindLabel,
  type ScanCandidate, type ScanStep, type ScanRequest, type ScanVia,
} from '@/lib/scan';
import { SCAN_RECORD_TYPE, TYPE_META } from '@/lib/erp-record';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
import { OptionRow } from '@/components/erp/fields';
import { formatObjectId } from '@/lib/utils';

export type { ScanRequest };

// Mehrfach-Lesungen desselben Codes kurz ignorieren (der Decoder feuert laufend).
const THROTTLE_MS = 1200;
// Wie lange der grüne Rahmen den Treffer quittiert, bevor es weitergeht.
const ACK_MS = 380;
// Vorschläge: höchstens so viele, und erst wenn das Tippen kurz ruht (die Suche geht
// ggf. an den Server – jeder Tastendruck wäre eine Anfrage).
const SUGGEST_MAX = 6;
const SUGGEST_DEBOUNCE_MS = 220;

type Feedback = { kind: 'ok' | 'bad'; text: string } | null;

/**
 * **Der Scanner.** Er besitzt die Kamera, führt durch eine Sequenz von Schritten und
 * liefert am Ende die Ergebnisse.
 *
 * **Was ein Ergebnis BEDEUTET, weiss er nicht** – das steht in der Deutung
 * (`lib/scan.ScanReading`, heute `objectCodes`), die er als Vertrag bekommt. Er kennt
 * weder den Decoder noch die Objektnummer-Semantik; er zeigt, quittiert und schaltet
 * weiter. Genau diese Naht macht eine zweite Deutung später zu einem neuen Objekt statt
 * zu einem Umbau.
 */
export function ScanDialog({ steps, onComplete, onClose, reading = objectCodes }: ScanRequest & { onClose: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [query, setQuery] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);
  // Refs vermeiden veraltete Closures im Kamera-Callback (robustes Weiterschalten).
  const stepIndexRef = useRef(0);
  const results = useRef<number[]>([]);
  // **Wie bestätigt wurde** – gescannt, bis das erste Mal getippt oder gewählt wurde.
  // Vorsichtig gerechnet: eine Bestätigung ist so viel wert wie ihr schwächstes Glied.
  const via = useRef<ScanVia>('scan');
  const lock = useRef(false);                 // während Prüfung und Quittierung sperren
  const completed = useRef(false);
  const lastRef = useRef<{ id: number; at: number } | null>(null);
  // Lebt der Dialog noch? Und läuft ein Quittierungs-Timer?  → §2.1
  const alive = useRef(true);
  const ackTimer = useRef<number | null>(null);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const step: ScanStep | undefined = steps[stepIndex];
  const multi = steps.length > 1;

  // **Ein abgebrochener Scan darf nichts auslösen.** Der Quittierungs-Timer lief früher
  // ungebremst weiter: Esc oder Klick daneben in diesen 380 ms → der Dialog war weg, der
  // Timer feuerte trotzdem, und `onComplete` bewegte eine Instanz, die niemand mehr
  // bewegen wollte.
  useEffect(() => {
    // Beim Betreten **wieder** auf «lebt» stellen: React ruft einen Effekt in der
    // Entwicklung absichtlich zweimal auf (mount → cleanup → mount). Ohne diese Zeile
    // bliebe die Marke nach dem ersten Cleanup für immer auf «tot» – der Dialog nähme
    // dann nichts mehr an. Genau das hat der Browser-Durchlauf gemeldet.
    alive.current = true;
    return () => {
      alive.current = false;
      if (ackTimer.current) window.clearTimeout(ackTimer.current);
    };
  }, []);

  async function handle(objectId: number, how: ScanVia) {
    if (lock.current || completed.current) return;
    const cur = steps[stepIndexRef.current];
    if (!cur) return;
    if (how === 'manual') via.current = 'manual';

    // Schon während der Prüfung sperren: der Decoder feuert weiter, und eine
    // Existenzabfrage darf nicht n-mal parallel laufen.
    lock.current = true;
    const reason = await reading.check(objectId, cur);
    if (!alive.current) return;
    if (reason) { setFeedback({ kind: 'bad', text: reason }); lock.current = false; return; }

    results.current = [...results.current, objectId];
    setFeedback({ kind: 'ok', text: `Erkannt: ${formatObjectId(objectId)}` });
    ackTimer.current = window.setTimeout(() => {
      ackTimer.current = null;
      if (!alive.current) return;
      const next = stepIndexRef.current + 1;
      if (next >= steps.length) {
        completed.current = true;
        onComplete(results.current, via.current);
      } else {
        stepIndexRef.current = next;
        setStepIndex(next);
        setQuery('');
        setFeedback(null);
        lock.current = false;
      }
    }, ACK_MS);
  }

  // Decoder-Treffer: Rohtext → Wert; ungültige bleiben sichtbar, die Kamera läuft weiter.
  // lastRef wird NICHT bei Schrittwechsel zurückgesetzt → ein im Bild verbleibender
  // (bereits quittierter) Code löst auf dem Folgeschritt keinen Fehlalarm aus.
  function handleText(raw: string) {
    if (lock.current || completed.current) return;
    const id = reading.read(raw);
    if (id == null) { setFeedback({ kind: 'bad', text: 'Kein gültiger Objekt-Code' }); return; }
    const now = Date.now();
    if (lastRef.current && lastRef.current.id === id && now - lastRef.current.at < THROTTLE_MS) return;
    lastRef.current = { id, at: now };
    void handle(id, 'scan');
  }

  const { videoRef, state, torch, setTorch } = useBarcodeScanner(true, handleText);
  const cameraLive = state === 'starting' || state === 'scanning';

  // **Der Fokus richtet sich nach der Kamera** (§3.2): läuft sie, bleibt er am Dialog –
  // auf dem Telefon poppte sonst die Tastatur sofort über das Bild, um das es geht.
  // Läuft sie nicht, ist die Tastatur der einzige Weg und bekommt den Fokus.
  useEffect(() => {
    if (cameraLive) sheetRef.current?.focus();
    else inputRef.current?.focus();
  }, [cameraLive]);

  // Esc schliesst – am Fenster, damit es unabhängig davon gilt, wo der Fokus gerade steht.
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  function onKeyDown(e: React.KeyboardEvent) {
    // **Hardware-Scanner bleiben bedienbar.** Ein USB-/Bluetooth-Gerät tippt die Nummer
    // plus Enter – ohne Fokus im Feld ginge das ins Leere. Die erste Ziffer holt den
    // Fokus und wird mitgenommen, damit nichts verloren geht. (Auf dem Telefon tippt
    // niemand Ziffern, also geht dort auch keine Tastatur auf.)
    if (/^\d$/.test(e.key) && document.activeElement !== inputRef.current) {
      setQuery((q) => q + e.key);
      inputRef.current?.focus();
      e.preventDefault();
      return;
    }

    // Fokusfalle: im Dialog gibt es zwei bis vier bedienbare Dinge – sie im Kreis zu
    // führen kostet acht Zeilen und macht ihn tastaturfähig.
    if (e.key !== 'Tab') return;
    const items = sheetRef.current?.querySelectorAll<HTMLElement>('button, input');
    if (!items?.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // Semantische Suche, Teil 1: **was dieser Schritt annimmt** (`offersFor`). Bei einem
  // Verifikationsschritt ist das genau die erwartete Nummer – deshalb genügt hier eine
  // Teileingabe, ohne dass irgendein Aufrufer eine Liste oder eine Suche mitgeben müsste.
  // Erweitert wird nie: die Vorschlagsmenge ist die Gültigkeitsmenge.
  const known = useMemo<ScanCandidate[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return offersFor(step)
      .filter((c) => formatObjectId(c.objectId).includes(q) || c.label.toLowerCase().includes(q))
      .slice(0, SUGGEST_MAX);
  }, [query, step]);

  // Teil 2: die **gesuchte** Menge. Wo die Kandidaten das halbe ERP wären (der freie
  // Lookup im Feed), gibt der Aufrufer keine Liste mit, sondern seine Suche
  // (`step.suggest`). Bei einem **eingeschränkten oder verifizierenden** Schritt bleibt
  // sie aussen vor: eine breitere Vorschlagsquelle darf nichts anbieten, was der Schritt
  // gar nicht annehmen würde.
  const [found, setFound] = useState<ScanCandidate[]>([]);
  useEffect(() => {
    const q = query.trim();
    const ask = step?.suggest;
    if (!q || !ask || step?.restrict || step?.expected != null) { setFound([]); return; }
    let stale = false;
    const t = window.setTimeout(() => {
      ask(q)
        .then((r) => { if (!stale) setFound(r); })
        .catch(() => { if (!stale) setFound([]); });
    }, SUGGEST_DEBOUNCE_MS);
    // Eine ältere Antwort darf eine neuere nie überholen (tippen und sofort löschen).
    return () => { stale = true; window.clearTimeout(t); };
  }, [query, step]);

  const suggestions = useMemo<ScanCandidate[]>(() => {
    const seen = new Set(known.map((c) => c.objectId));
    return [...known, ...found.filter((c) => !seen.has(c.objectId))].slice(0, SUGGEST_MAX);
  }, [known, found]);

  /**
   * **Dieselbe Anatomie wie das Referenzfeld, aus dem der Dialog kommt**: die **Sorte**
   * als Beschriftung darüber, der **Platzhalter** darin – und der Platzhalter ist
   * wortgleich derselbe (`objectCodes.prompt` ↔ {@link LOOKUP_HINT}).
   *
   * Getrennt, weil ein Platzhalter beim ersten Zeichen verschwindet: stand die Sorte
   * darin, wusste man ab dem ersten Buchstaben nicht mehr, wonach man sucht. Eine
   * Beschriftung bleibt stehen. Was der Dialog TUT, sagt er nur noch der Vorlesehilfe –
   * im Bild sagen es Zielrahmen und Suchstrahl.
   */
  const kind = scanKindLabel(step);
  const kindType = step?.kind ? SCAN_RECORD_TYPE[step.kind] : undefined;
  const KindIcon = kindType ? TYPE_META[kindType].icon : null;
  const hint = reading.prompt(step);
  const empty = step?.emptyOption;

  /**
   * **Enter geht durch – oder sagt, warum nicht.** Es gibt keinen Zwischenschritt.
   *
   * Der frühere «Übernehmen»-Knopf war ein zweiter Klick für eine Entscheidung, die
   * bereits getroffen war: die Nummer stand im Feld. Schlimmer noch, er war **gesperrt**,
   * wenn die Eingabe nicht passte – die Meldung, die der Mensch gebraucht hätte
   * («das ist nicht das erwartete Objekt»), blieb damit aus, und der Knopf sagte nur,
   * dass etwas nicht geht.
   *
   * Jetzt geht jede Eingabe durch dieselbe Prüfung wie ein Kamerabild (`reading.check`),
   * und ihr Grund erscheint dort, wo der Blick ist: im Zielrahmen.
   */
  function submitQuery() {
    const typedId = reading.read(query);
    if (typedId == null) {
      setFeedback({ kind: 'bad', text: 'Keine gültige Objektnummer' });
      return;
    }
    void handle(typedId, 'manual');
  }

  return (
    // Der ganze Container IST die Kameraansicht. Kein Kopf, kein Erklärtext, kein zweiter
    // Kasten: was zu tun ist, steht im Bild – und was man sucht, tippt man im Bild.
    // Klick daneben schliesst, Esc ebenso.
    <div style={backdrop} onClick={onClose}>
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${kind} scannen oder suchen`}
        tabIndex={-1}
        style={sheet}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        {cameraLive ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video ref={videoRef} style={video} muted playsInline autoPlay />
        ) : (
          <div style={cameraOff}>
            <CameraOff size={30} strokeWidth={1.5} />
            <span style={{ fontSize: 12, marginTop: 8, maxWidth: 260, textAlign: 'center' }}>
              {state === 'denied' ? 'Kein Kamerazugriff – bitte suchen.' : 'Kamera nicht verfügbar – bitte suchen.'}
            </span>
          </div>
        )}

        {/* Schritt-Fortschritt (nur bei Sequenz) – hauchdünn am oberen Rand */}
        {multi && (
          <div style={progressBar}>
            {steps.map((_, i) => (
              <span key={i} style={{ height: 3, flex: 1, borderRadius: 2, background: i < stepIndex ? 'var(--success)' : i === stepIndex ? '#fff' : 'rgba(255,255,255,.28)' }} />
            ))}
          </div>
        )}

        {/* Taschenlampe – nur, wo das Gerät sie hat. Im Regal entscheidet sie darüber,
            ob überhaupt etwas zu lesen ist. */}
        {torch !== null && (
          <button
            type="button"
            onClick={() => void setTorch(!torch)}
            aria-label={torch ? 'Licht aus' : 'Licht an'}
            aria-pressed={torch}
            style={{ ...torchBtn, background: torch ? '#fff' : 'rgba(15,23,42,.5)', color: torch ? 'var(--fg-1)' : '#fff' }}
          >
            <Flashlight size={17} />
          </button>
        )}

        {/* Zielrahmen mit Suchstrahl + der EINEN Angabe, die zählt: was soll gescannt
            werden. **Der Grund steht IM Rahmen** – dort schaut der Mensch ohnehin hin,
            und dort meldet auch die Farbe den Zustand. Darunter oder daneben war er eine
            zweite Stelle für dieselbe Aussage, und die untere Bildkante gehört der Suche. */}
        <div style={{ ...frame, borderColor: feedback?.kind === 'bad' ? 'var(--danger)' : feedback?.kind === 'ok' ? 'var(--success)' : 'rgba(255,255,255,.85)' }}>
          {cameraLive && !feedback && <div className="ix-scanbeam" style={beam} />}
          {/* Erfolg meldet der **Rahmen** (er wird grün und der Scanner schaltet weiter) –
              eine zweite grüne Meldung sagte dasselbe noch einmal (Notiz #253). Ein Text
              braucht es nur beim Fehlschlag: dort zählt der GRUND. */}
          {feedback?.kind === 'bad' && (
            <div style={reasonBox} role="status">
              <AlertTriangle size={15} style={{ flex: 'none' }} />
              <span>{feedback.text}</span>
            </div>
          )}
        </div>

        {/* Suche – im Bild statt darunter: eine milchige Leiste am unteren Rand, mit
            derselben Anatomie wie das Referenzfeld: Beschriftung · Eingabe · Liste. */}
        <div style={searchBar}>
          {/* **Ein Bauteil statt zweier** (Notiz #758). Die Sorte stand als eigener Chip
              über der Leiste, der Platzhalter trug nur die nackte Nummer – zwei Stellen
              für EINE Auskunft. Jetzt sagt der Platzhalter beides («Instanz 100000825
              suchen»), und das **Symbol** sitzt am Innenrand des Feldes: dass gesucht
              wird, sagt das Feld selbst; *was* gesucht wird, sagt das Symbol – dasselbe,
              das der Feed und jeder Detail-Kopf trägt (`TYPE_META`).

              Ohne bekannten Datensatztyp (`process`/`object`) bleibt die Lupe: ein
              ausgeliehenes Symbol wäre eine Behauptung. */}
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,.7)', pointerEvents: 'none', display: 'flex' }}>
              {KindIcon ? <KindIcon size={15} /> : <Search size={15} />}
            </span>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setFeedback(null); }}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submitQuery(); } }}
              placeholder={hint}
              aria-label={hint}
              style={input}
            />
          </div>

          {/* **Ein Klick genügt.** Die Auswahl IST die Eingabe – es gibt keinen zweiten
              Knopf, der sie noch einmal bestätigt. Gescrollt wird weiterhin, nur der
              Balken bleibt weg (Notiz #146). */}
          {(empty || suggestions.length > 0) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 152, overflowY: 'auto' }}>
              {/* **«Nichts» steht auch hier zur Wahl** – als erste Zeile, wie im Feld.
                  Ohne sie müsste man den Dialog schliessen, um eine Entscheidung zu
                  treffen, die er selbst anbietet. Der Scanner erfindet dafür keine
                  Nummer: der Aufrufer sagt, was «nichts» bedeutet. */}
              {empty && (
                <button
                  type="button"
                  onClick={() => { if (lock.current || completed.current) return; empty.pick(); onClose(); }}
                  style={suggestionBtn}
                >
                  <OptionRow option={{ value: '', label: empty.label }} />
                </button>
              )}
              {/* **Dieselbe Zeile wie im Feld** – buchstäblich dasselbe Bauteil
                  (`fields.OptionRow`), nicht dieselbe Absicht: Nummer tabellarisch,
                  Name leise daneben. Ein Klick genügt, die Auswahl IST die Eingabe. */}
              {suggestions.map((c) => (
                <button key={c.objectId} type="button" onClick={() => void handle(c.objectId, 'manual')} style={suggestionBtn}>
                  <OptionRow option={{ value: String(c.objectId), label: formatObjectId(c.objectId), name: c.label }} />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const backdrop: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15,23,42,0.62)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
// Die Sheet-Fläche IST die Kamera: dunkel, randlos, alles Weitere liegt darüber.
const sheet: React.CSSProperties = {
  position: 'relative', width: '100%', maxWidth: 420, aspectRatio: '3 / 4', maxHeight: '82vh',
  background: '#0B1220', borderRadius: 18, overflow: 'hidden',
  boxShadow: '0 24px 60px rgba(15,23,42,0.4)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', outline: 'none',
};
const video: React.CSSProperties = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' };
const cameraOff: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', color: 'rgba(255,255,255,.6)', padding: 24,
};
const progressBar: React.CSSProperties = {
  position: 'absolute', top: 10, left: 14, right: 14, display: 'flex', gap: 5,
};
const torchBtn: React.CSSProperties = {
  position: 'absolute', top: 14, right: 14, width: 38, height: 38, borderRadius: 999,
  border: '1px solid rgba(255,255,255,.22)', display: 'flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer', backdropFilter: 'blur(10px)',
};
const frame: React.CSSProperties = {
  position: 'absolute', width: '64%', aspectRatio: '1 / 1', border: '2px solid rgba(255,255,255,.85)',
  borderRadius: 18, boxShadow: '0 0 0 9999px rgba(4,8,16,0.42)', transition: 'border-color .15s',
  overflow: 'hidden',
};
// Der Suchstrahl: eine weiche Linie, die den Rahmen abtastet.
const beam: React.CSSProperties = {
  position: 'absolute', left: '6%', right: '6%', top: '50%', height: 2, borderRadius: 2,
  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.95), transparent)',
  boxShadow: '0 0 12px rgba(255,255,255,.6)',
};
/**
 * **Der Grund – im Rahmen, nicht darunter.** Er füllt die untere Hälfte des Zielrahmens:
 * dort ist der Blick, dort ist der rote Rand, und die Aussage steht damit an genau einer
 * Stelle. Kein Schweben über der Kamera, kein Streifen ausserhalb.
 */
const reasonBox: React.CSSProperties = {
  position: 'absolute', left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center',
  justifyContent: 'center', gap: 7, padding: '10px 12px', textAlign: 'center',
  background: 'var(--danger)', color: '#fff', fontSize: 12.5, fontWeight: 600, lineHeight: 1.35,
};
const searchBar: React.CSSProperties = {
  position: 'absolute', left: 14, right: 14, bottom: 14, display: 'flex', flexDirection: 'column', gap: 6,
};
const input: React.CSSProperties = {
  width: '100%', paddingLeft: 36, paddingRight: 12, paddingTop: 11, paddingBottom: 11, fontSize: 14,
  border: '1px solid rgba(255,255,255,.22)', borderRadius: 12, outline: 'none', boxSizing: 'border-box',
  background: 'rgba(15,23,42,.5)', backdropFilter: 'blur(10px)', color: '#fff',
};
const suggestionBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', width: '100%', textAlign: 'left',
  border: '1px solid rgba(255,255,255,.18)', borderRadius: 10, cursor: 'pointer', fontSize: 13,
  background: 'rgba(15,23,42,.55)', backdropFilter: 'blur(10px)', color: '#fff',
};
