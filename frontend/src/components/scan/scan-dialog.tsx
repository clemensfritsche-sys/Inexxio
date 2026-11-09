'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { CameraOff, AlertTriangle, Flashlight, Search } from 'lucide-react';
import {
  objectCodes, offersFor, scanKindLabel,
  type ScanCandidate, type ScanStep, type ScanRequest, type ScanVia,
} from '@/lib/scan';
import { SCAN_RECORD_TYPE, TYPE_META } from '@/lib/erp-record';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
import { OptionRow } from '@/components/erp/search-select';
import { formatObjectId } from '@/lib/utils';
import { useSearch } from '@/lib/use-search';
import { useDialog } from '@/lib/use-dialog';

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
 * **Der Scanner.** Er besitzt die Kamera, führt durch eine Sequenz von Schritten und liefert
 * die Ergebnisse. Was ein Ergebnis bedeutet, weiss er nicht – das steht in der Deutung
 * (`lib/scan.ScanReading`, heute `objectCodes`), die er als Vertrag bekommt.
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
  // Escape, Fokus zurück, Tab im Kreis – das eine Verhalten (`lib/use-dialog`); WOHIN der
  // Fokus geht, entscheidet die Kamera (unten).
  const dialog = useDialog(onClose, { focus: 'none' });
  const sheetRef = dialog.ref;
  const inputRef = useRef<HTMLInputElement | null>(null);

  const step: ScanStep | undefined = steps[stepIndex];
  const multi = steps.length > 1;

  // Ein abgebrochener Scan darf nichts auslösen (der Quittierungs-Timer prüft, ob der Dialog lebt).
  useEffect(() => {
    // Beim Betreten wieder auf «lebt» stellen – React ruft Effekte in der Entwicklung zweimal auf.
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

  // Der Fokus richtet sich nach der Kamera (§3.2): läuft sie, bleibt er am Dialog (sonst
  // poppt auf dem Telefon die Tastatur auf); läuft sie nicht, bekommt das Feld den Fokus.
  // Dieselbe Regel bei jedem neuen Schritt.
  useEffect(() => {
    if (cameraLive) sheetRef.current?.focus();
    else inputRef.current?.focus();
  }, [cameraLive, stepIndex, sheetRef]);

  function onKeyDown(e: React.KeyboardEvent) {
    // Hardware-Scanner bleiben bedienbar: die erste Ziffer holt den Fokus und wird mitgenommen.
    if (/^\d$/.test(e.key) && document.activeElement !== inputRef.current) {
      setQuery((q) => q + e.key);
      inputRef.current?.focus();
      e.preventDefault();
      return;
    }

    dialog.onKeyDown(e);
  }

  // Vorschläge, Teil 1: was dieser Schritt annimmt (`offersFor`) – bei einer Verifikation die
  // erwartete Nummer. Die Vorschlagsmenge ist die Gültigkeitsmenge.
  const known = useMemo<ScanCandidate[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return offersFor(step)
      .filter((c) => formatObjectId(c.objectId).includes(q) || c.label.toLowerCase().includes(q))
      .slice(0, SUGGEST_MAX);
  }, [query, step]);

  // Teil 2: die gesuchte Menge (`step.suggest`) für den freien Lookup – nie bei einem
  // eingeschränkten oder verifizierenden Schritt.
  const ask = step?.restrict || step?.expected != null ? null : step?.suggest;
  const { hits: found } = useSearch(query, ask, { delay: SUGGEST_DEBOUNCE_MS });

  const suggestions = useMemo<ScanCandidate[]>(() => {
    const seen = new Set(known.map((c) => c.objectId));
    return [...known, ...found.filter((c) => !seen.has(c.objectId))].slice(0, SUGGEST_MAX);
  }, [known, found]);

  /**
   * Dieselbe Anatomie wie das Referenzfeld: die Sorte als Beschriftung darüber (sie bleibt
   * stehen), der Platzhalter darin, wortgleich (`objectCodes.prompt` ↔ {@link LOOKUP_HINT}).
   */
  const kind = scanKindLabel(step);
  const kindType = step?.kind ? SCAN_RECORD_TYPE[step.kind] : undefined;
  const KindIcon = kindType ? TYPE_META[kindType].icon : null;
  const hint = reading.prompt(step);
  const empty = step?.emptyOption;

  /**
   * **Enter geht durch – oder sagt, warum nicht.** Jede Eingabe geht durch dieselbe Prüfung
   * wie ein Kamerabild (`reading.check`); der Grund erscheint im Zielrahmen.
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
    // Der ganze Container IST die Kameraansicht; was zu tun ist, steht im Bild.
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

        {/* Taschenlampe – nur, wo das Gerät sie hat. */}
        {torch !== null && (
          <button
            type="button"
            onClick={() => void setTorch(!torch)}
            aria-label={torch ? 'Licht aus' : 'Licht an'}
            aria-pressed={torch}
            style={{ ...torchBtn, background: torch ? '#fff' : 'color-mix(in srgb, var(--bg-dark) 50%, transparent)', color: torch ? 'var(--fg-1)' : '#fff' }}
          >
            <Flashlight size={17} />
          </button>
        )}

        {/* Zielrahmen mit Suchstrahl und dem, was gescannt werden soll. Der Grund steht IM
            Rahmen, wo auch die Farbe den Zustand meldet. */}
        <div style={{ ...frame, borderColor: feedback?.kind === 'bad' ? 'var(--danger)' : feedback?.kind === 'ok' ? 'var(--success)' : 'rgba(255,255,255,.85)' }}>
          {cameraLive && !feedback && <div className="ix-scanbeam" style={beam} />}
          {/* Erfolg meldet der Rahmen (grün); Text nur beim Fehlschlag. */}
          {feedback?.kind === 'bad' && (
            <div style={reasonBox} role="status">
              <AlertTriangle size={15} style={{ flex: 'none' }} />
              <span>{feedback.text}</span>
            </div>
          )}
        </div>

        {/* Suche im Bild: milchige Leiste am unteren Rand – Beschriftung · Eingabe · Liste. */}
        <div style={searchBar}>
          {/* Der Platzhalter sagt Sorte und Nummer; das Symbol am Innenrand ist das des
              Datensatztyps (`TYPE_META`), ohne bekannten Typ die Lupe. */}
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

          {/* Ein Klick genügt – die Auswahl IST die Eingabe. */}
          {(empty || suggestions.length > 0) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 152, overflowY: 'auto' }}>
              {/* «Nichts» steht auch hier zur Wahl, als erste Zeile; was es bedeutet, sagt
                  der Aufrufer. */}
              {empty && (
                <button
                  type="button"
                  onClick={() => { if (lock.current || completed.current) return; empty.pick(); onClose(); }}
                  style={suggestionBtn}
                >
                  <OptionRow option={{ value: '', label: empty.label }} />
                </button>
              )}
              {/* Dieselbe Zeile wie im Feld (`fields.OptionRow`). */}
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
  position: 'fixed', inset: 0, zIndex: 100, background: 'color-mix(in srgb, var(--bg-dark) 62%, transparent)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
// Die Sheet-Fläche IST die Kamera: dunkel, randlos, alles Weitere liegt darüber.
const sheet: React.CSSProperties = {
  position: 'relative', width: '100%', maxWidth: 420, aspectRatio: '3 / 4', maxHeight: '82vh',
  background: 'var(--bg-dark)', borderRadius: 18, overflow: 'hidden',
  boxShadow: '0 24px 60px color-mix(in srgb, var(--bg-dark) 40%, transparent)',
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
/** **Der Grund – im Rahmen**: er füllt die untere Hälfte des Zielrahmens, an genau einer Stelle. */
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
  background: 'color-mix(in srgb, var(--bg-dark) 50%, transparent)', backdropFilter: 'blur(10px)', color: '#fff',
};
const suggestionBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', width: '100%', textAlign: 'left',
  border: '1px solid rgba(255,255,255,.18)', borderRadius: 10, cursor: 'pointer', fontSize: 13,
  background: 'color-mix(in srgb, var(--bg-dark) 55%, transparent)', backdropFilter: 'blur(10px)', color: '#fff',
};
