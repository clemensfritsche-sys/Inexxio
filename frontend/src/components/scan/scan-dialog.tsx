'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { CameraOff, AlertTriangle, Flashlight, Search } from 'lucide-react';
import { objectCodes, type ScanCandidate, type ScanStep, type ScanRequest } from '@/lib/scan';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
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

  async function handle(objectId: number) {
    if (lock.current || completed.current) return;
    const cur = steps[stepIndexRef.current];
    if (!cur) return;

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
        onComplete(results.current);
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
    void handle(id);
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

  // Semantische Suche, Teil 1: die **mitgegebene** Menge – dort, wo der Aufrufer sie
  // kennt (die paar Zielorte einer Bewegung). Sie ist zugleich die Gültigkeitsmenge eines
  // eingeschränkten Schritts, also wird hier nur gefiltert, nie erweitert.
  const known = useMemo<ScanCandidate[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q || !step?.candidates) return [];
    return step.candidates
      .filter((c) => formatObjectId(c.objectId).includes(q) || c.label.toLowerCase().includes(q))
      .slice(0, SUGGEST_MAX);
  }, [query, step]);

  // Teil 2: die **gesuchte** Menge. Wo die Kandidaten das halbe ERP wären, gibt der
  // Aufrufer keine Liste mit, sondern seine Suche (`step.suggest`) – bei einem
  // **eingeschränkten** Schritt bleibt sie aussen vor: eine breitere Vorschlagsquelle
  // darf nichts anbieten, was der Schritt gar nicht annehmen würde.
  const [found, setFound] = useState<ScanCandidate[]>([]);
  useEffect(() => {
    const q = query.trim();
    const ask = step?.suggest;
    if (!q || !ask || step?.restrict) { setFound([]); return; }
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

  // Was im Bild steht, sagt die Deutung – der Dialog weiss nicht, was ein Schritt meint.
  const actionText = reading.prompt(step);
  const typedId = reading.read(query);
  const typedDirectOk = typedId != null && (!step?.restrict || step.candidates?.some((c) => c.objectId === typedId));

  function submitQuery() {
    if (typedId == null) { setFeedback({ kind: 'bad', text: 'Keine gültige Objektnummer' }); return; }
    void handle(typedId);
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
        aria-label={actionText}
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

        {/* Zielrahmen mit Suchstrahl + der EINEN Angabe, die zählt: was soll gescannt werden. */}
        <div style={{ ...frame, borderColor: feedback?.kind === 'bad' ? 'var(--danger)' : feedback?.kind === 'ok' ? 'var(--success)' : 'rgba(255,255,255,.85)' }}>
          {cameraLive && !feedback && <div className="ix-scanbeam" style={beam} />}
        </div>
        {/* Erfolg meldet der **Rahmen** (er wird grün und der Scanner schaltet weiter) –
            eine zweite grüne Meldung daneben sagte dasselbe noch einmal (Notiz #253).
            Ein Text braucht es nur beim Fehlschlag: dort zählt der GRUND. */}
        {feedback?.kind === 'bad' && (
          <div style={{ ...badge, background: 'var(--danger)' }} role="status">
            <AlertTriangle size={14} /> {feedback.text}
          </div>
        )}

        {/* Suche – im Bild statt darunter: eine milchige Leiste am unteren Rand. */}
        <div style={searchBar}>
          <div style={{ position: 'relative' }}>
            <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,.7)', pointerEvents: 'none' }} />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setFeedback(null); }}
              onKeyDown={(e) => { if (e.key === 'Enter' && typedDirectOk) submitQuery(); }}
              // Die Zielangabe («Instanz 100000479») lebt HIER statt zusätzlich als Chip im
              // Bild – eine Aussage, eine Stelle (Notiz #126).
              placeholder={actionText}
              aria-label={actionText}
              style={input}
            />
          </div>

          {/* Gescrollt wird weiterhin, nur der Balken bleibt weg (Notiz #146). */}
          {suggestions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 152, overflowY: 'auto' }}>
              {suggestions.map((c) => (
                <button key={c.objectId} onClick={() => void handle(c.objectId)} style={suggestionBtn}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{formatObjectId(c.objectId)}</span>
                  <span style={{ opacity: .8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.label}</span>
                </button>
              ))}
            </div>
          )}

          {suggestions.length === 0 && query.trim() !== '' && (
            <button onClick={submitQuery} disabled={!typedDirectOk} style={{ ...primaryBtn, opacity: typedDirectOk ? 1 : 0.45 }}>
              {typedId != null ? `${formatObjectId(typedId)} übernehmen` : 'Übernehmen'}
            </button>
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
// Die EINE Angabe im Bild: was soll gescannt werden.
const badge: React.CSSProperties = {
  position: 'absolute', top: 'calc(50% + 34%)', display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 14px', borderRadius: 999, color: '#fff', fontSize: 12.5, fontWeight: 700, maxWidth: '86%',
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
const primaryBtn: React.CSSProperties = {
  padding: '10px 14px', borderRadius: 10, border: 'none', background: '#fff', color: 'var(--fg-1)',
  fontSize: 13, fontWeight: 700, cursor: 'pointer',
};
