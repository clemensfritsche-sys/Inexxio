'use client';

import { useEffect, useId, useRef, useState } from 'react';
import type { ElementType, ReactNode } from 'react';
import { type LucideIcon } from 'lucide-react';

// ►►► **Die Bedienelemente** – die eine Feldform (`inputClass`), Beschriftung (`Label`),
// Schieber (`IconSwitch`), Umschalter (`Segmented`), Dialog, Palette, Zahlenfelder und der
// Symbol-Knopf im Feld (`FieldAction`). ◄◄◄

/**
 * ►►► **EINE Form für jedes Eingabefeld** – ERP, Konto-Formulare im ERP, Zeiterfassung,
 * Spezifikation: 8 px Radius, Haarlinie, 14 px Schrift, 8 × 12 px Polsterung, Fokus als
 * leiser Ring in Slate. Was sich je Lage ändert, ist nur die Farbe (`inputClass`). ◄◄◄
 * Ein Wert auf dem Beleg ist kein Eingabefeld, sondern gedruckter Text mit `.ix-editable`
 * (`beleg/shared.DOC_FIELD`).
 */
const INPUT_FORM = 'w-full rounded-ds-md border px-3 py-2 text-sm outline-none placeholder:text-fg-4 transition-colors focus:ring-[3px] focus:ring-accent-soft';
const INPUT_TONE = {
  normal: 'border-border-2 bg-bg-1 text-fg-1 focus:border-accent',
  /** Pflicht und leer, oder das Format stimmt nicht – gemeldet, nicht gesperrt. */
  warn: 'border-warning bg-warning-bg text-fg-1',
  read: 'border-border-1 bg-bg-2 text-fg-4 cursor-default',
} as const;

export function inputClass(tone: keyof typeof INPUT_TONE = 'normal'): string {
  return `${INPUT_FORM} ${INPUT_TONE[tone]}`;
}

export const inputCls = inputClass();

/**
 * **Schieber** für eine Wahl mit wenigen, einander ausschliessenden Optionen: EIN Gleis,
 * ein Reiter, der zur aktiven Option gleitet. Nebeneinanderstehende Knöpfe lassen offen,
 * dass sie sich ausschliessen – die Bewegung zeigt es ohne ein Wort Erklärung.
 *
 * Gesperrte Optionen bleiben sichtbar und nennen ihren Grund im Hover.
 *
 * **Der Hover kommt sofort** (Testnotiz #618): über `data-tip` wie überall sonst im ERP,
 * nicht über `title`. Der native Browser-Tooltip wartet rund eine Sekunde – wo das Symbol
 * die Bedeutung allein nicht trägt, ist das genau die Sekunde, in der man ratlos ist. Weil
 * es hier an EINER Stelle steht, gilt es für jeden Umschalter im Haus.
 */
export function IconSwitch<T extends string>({ value, onChange, options, labelActiveOnly }: {
  value: T; onChange: (v: T) => void;
  /** ``mark`` setzt einen dezenten Punkt an eine (nicht gewählte) Option – z. B. die
   *  abgeleitete Empfehlung: sie markiert sich selbst, statt einen Erklärsatz zu brauchen. */
  options: { value: T; icon: ElementType; label: string; hint?: string; disabled?: boolean; mark?: boolean }[];
  /** Nur die AKTIVE Option zeigt ihr Wort, die übrigen nur ihr Symbol – für Achsen mit
   *  vielen Werten (Mengeneinheit): man sieht auf einen Blick, was gilt, ohne dass sechs
   *  Wörter nebeneinander um Aufmerksamkeit ringen. */
  labelActiveOnly?: boolean;
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  const wrapRef = useRef<HTMLDivElement>(null);
  // Der gleitende Reiter wird **gemessen**, nicht gerechnet: sobald die Optionen
  // unterschiedlich breit sind (aktives Wort sichtbar, übrige nur Symbol), stimmt ein
  // «100/N %»-Raster nicht mehr.
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const measure = () => {
      const el = wrap.querySelector<HTMLElement>(`[data-ix-idx="${index}"]`);
      if (el) setThumb({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [index, options.length, labelActiveOnly]);

  return (
    // ``labelActiveOnly`` hat naturgemäss ungleich breite Optionen – dann soll sich der
    // Regler an seinen Inhalt schmiegen statt die ganze Spalte zu füllen (Notizen #224/#225).
    <div ref={wrapRef} style={{
      position: 'relative', display: labelActiveOnly ? 'inline-flex' : 'flex',
      alignSelf: 'flex-start', maxWidth: '100%', flexWrap: 'wrap',
      padding: 3, borderRadius: 999, background: 'var(--bg-2)', border: '1px solid var(--border-1)',
    }}>
      <span aria-hidden style={{
        position: 'absolute', top: 3, bottom: 3,
        left: thumb ? thumb.left : 3, width: thumb ? thumb.width : 0,
        opacity: thumb ? 1 : 0,
        transition: 'left .18s cubic-bezier(.4,0,.2,1), width .18s cubic-bezier(.4,0,.2,1)',
        borderRadius: 999, background: 'var(--bg-1)', boxShadow: '0 1px 2px rgba(0,0,0,.12)',
      }} />
      {options.map((o, i) => {
        const active = o.value === value;
        const Icon = o.icon;
        const showLabel = !labelActiveOnly || active;
        return (
          <button key={o.value} type="button" role="tab" aria-selected={active} data-ix-idx={i}
            aria-label={o.label}
            // Der **Name** wächst im Hover heraus (siehe unten); die längere **Erklärung**
            // bleibt der Tooltip – aber nur, wenn sie mehr sagt als der Name.
            data-tip={o.hint && o.hint !== o.label ? o.hint : undefined} data-tip-pos="bottom"
            className="ix-seg"
            onClick={o.disabled ? undefined : () => onChange(o.value)} disabled={o.disabled}
            style={{
              position: 'relative', flex: labelActiveOnly ? '0 0 auto' : 1,
              display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', gap: 6, padding: '7px 12px',
              border: 'none', background: 'none', borderRadius: 999,
              font: '600 12px var(--font-body)', cursor: o.disabled ? 'not-allowed' : 'pointer',
              opacity: o.disabled ? 0.4 : 1, transition: 'color .18s',
              color: active ? 'var(--accent-ink)' : 'var(--fg-3)', whiteSpace: 'nowrap',
            }}>
            <Icon size={14} />
            {/* **Der Buttonname erscheint daneben** (Testnotiz #624) – dieselbe Geste wie an
                der Palette. Wo das Wort ohnehin steht (aktive Option, voller Modus), gibt es
                nichts einzublenden; sonst wächst es im Hover heraus. Der gleitende Reiter
                wird ohnehin gemessen (ResizeObserver), also folgt er der neuen Breite. */}
            {showLabel ? o.label : (
              <span className="ix-seg-label"><span>{o.label}</span></span>
            )}
            {o.mark && !active && <span aria-hidden style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--accent)', flexShrink: 0 }} />}
          </button>
        );
      })}
    </div>
  );
}

/**
 * **Dialog** – die EINE Fensterform für eine Entscheidung. Klick daneben und `Esc`
 * schliessen; ein × wäre ein zweiter Weg für dasselbe, ein «Abbrechen» ein dritter
 * (Notizen #153/#154). Der Inhalt ist die Entscheidung, sonst nichts.
 */
export function Dialog({ icon: Icon, title, tone = 'var(--warning)', width = 520, onClose, children }: {
  icon?: ElementType; title: string; tone?: string; width?: number;
  onClose: () => void; children: ReactNode;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  // **Fokus hinein und zurück**: beim Öffnen auf das erste Bedienelement (sonst den Dialog
  // selbst), beim Schliessen dorthin, wo er vorher war. Escape schliesst.
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const node = panel.current;
    if (node && !node.contains(document.activeElement)) {
      (node.querySelector<HTMLElement>(FOCUSABLE) ?? node).focus();
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') close.current(); }
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      before?.focus?.();
    };
  }, []);
  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'color-mix(in srgb, var(--bg-dark) 45%, transparent)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: 16 }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        style={{ background: 'var(--bg-1)', borderRadius: 'var(--r-lg)', width: `min(${width}px, 100%)`, maxHeight: '86vh', overflowY: 'auto', boxShadow: 'var(--shadow-lg)', outline: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', borderBottom: '1px solid var(--border-1)' }}>
          {Icon && <Icon size={18} aria-hidden style={{ color: tone }} />}
          <h2 id={titleId} style={{ font: '700 15px var(--font-display)', color: 'var(--fg-1)', margin: 0 }}>{title}</h2>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>{children}</div>
      </div>
    </div>
  );
}

/** Was im Dialog den Fokus nehmen kann – das erste davon bekommt ihn beim Öffnen. */
const FOCUSABLE = 'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

/**
 * **Eine Palette: Symbole in einer Reihe.** Mehr nicht – der Name steht im Hover des
 * einzelnen Symbols (#518). Der Baustein bleibt, damit dieselbe Geste an allen drei
 * Stellen (Module · Erfassungsfelder · Unterdeckung) gleich aussieht.
 */
export function Palette({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
      {children}
    </div>
  );
}

/**
 * Die EINE Regel für Zahlenfelder (Mengen, Perioden, Prozente): nur Ziffern, optional
 * EIN Dezimaltrenner. Das Komma wird zum Punkt – wer «2,5» tippt, meint 2.5, und das
 * Backend rechnet mit Punkt.
 *
 * Bewusst eine Filterfunktion statt `<input type="number">`: dessen Spinner, Scroll-Rad
 * und länderabhängige Trennzeichen sind in Formularen mehr Ärger als Hilfe – und ein
 * `type="number"` liefert bei ungültiger Eingabe einen LEEREN Wert, wodurch getippte
 * Zeichen spurlos verschwinden. Hier bleibt der Wert immer sichtbar und sauber.
 */
export function numericOnly(
  raw: string, opts: { decimals?: boolean | number; signed?: boolean } = {},
): string {
  const { decimals = true, signed = false } = opts;
  // **Ein Minus ist an genau einer Stelle richtig: ganz vorn.** Wo negative Beträge eine
  // Aussage sind (eine Gutschrift ist eine negative Rechnung), muss man es tippen können
  // – aber nicht mittendrin, und nicht zweimal.
  const minus = signed && raw.trimStart().startsWith('-') ? '-' : '';
  const cleaned = raw.replace(',', '.').replace(/[^\d.]/g, '');
  if (decimals === false || decimals === 0) return minus + cleaned.replace(/\./g, '');
  const [head, ...rest] = cleaned.split('.');       // höchstens EIN Trenner
  // ►►► **Wie viele Nachkommastellen erlaubt sind, sagt die WÄHRUNG** (Testnotiz #931).
  // ◄◄◄ Nicht «immer zwei»: JPY hat null, KWD drei. `true` heisst «unbegrenzt» und bleibt
  // richtig, wo kein Betrag getippt wird (eine Menge, ein Messwert).
  const tail = rest.join('');
  const kept = typeof decimals === 'number' ? tail.slice(0, decimals) : tail;
  return minus + (rest.length ? `${head}.${kept}` : head);
}

/** Tastatur/Verhalten passend zum Zahlenfeld (Mobile: Ziffernblock). */
export const numericInputProps = { inputMode: 'decimal' as const, autoComplete: 'off' };

export function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-4)', marginBottom: 4 }}>
      {/* **Die Warnfarbe kommt aus dem Token**, nicht als Hex: eine zweite Rotstufe
          neben `--danger` wäre eine zweite Farbsprache (Design-System §4). */}
      {children}{required && <span style={{ color: 'var(--danger)' }}> *</span>}
    </div>
  );
}

/**
 * ►►► **Eine Aktion sitzt IM Feld, nicht daneben** (Testnotizen #738/#1026). ◄◄◄
 *
 * *«Sollte hier nicht auch die global gültige UI/UX-Logik für Suchfelder angewendet
 * werden, welche nach Objektnummer suchen können?»* – Die Antwort stand schon im
 * Referenzfeld (`SearchSelect.action`): die Kamera ersetzt das Zierzeichen am rechten
 * Innenrand. Dass es eine Liste gibt, sagt der Klick; eine echte Aktion ist den Platz
 * wert. Ein eigener Knopf daneben sind **zwei Flächen für eine Frage**.
 *
 * Sie steht darum als **Bauteil** hier und nicht als Markup in `SearchSelect`: die
 * Stück-Auswahl (`StockPicker`) hatte ihre eigene Fassung daneben, und das ist genau die
 * Form, in der zwei Suchfelder unterschiedlich aussehen, obwohl sie dasselbe tun.
 *
 * `onMouseDown` verhindert, dass der Fokus ins Eingabefeld springt (das öffnete sonst
 * eine Liste, während sich der Dialog davorlegt).
 */
export function FieldAction({ icon, label, disabled, onClick }: {
  icon: ReactNode; label: string; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="erp-fieldaction"
      data-tip={label}
      aria-label={label}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
    >
      {icon}
    </button>
  );
}

/**
 * **Eine Wahl aus wenigen Werten** – zwei bis vier Möglichkeiten nebeneinander, kein
 * Auswahlfeld.
 *
 * ►►► **Mit Symbol wird sie kompakt — das Wort bleibt** (Testnotizen #877/#878). ◄◄◄
 *
 * *«Kann man hier so einen Button machen wie bei der Auswahl der Module – also ein Icon
 * und beim Hover der Text dazu.»* – Gemeldet an den beiden Fristen: drei Blöcke à
 * `flex: 1` in einer 460 px schmalen Modulspalte, doppelt (Liefer- **und** Zahlungsfrist),
 * in 13 px/600. Das ist mehr Gewicht, als eine Frist verdient, und genau das ist behoben:
 * mit Symbol stehen die Möglichkeiten **auf ihrer Inhaltsbreite** nebeneinander statt
 * jede auf einem Drittel der Spalte.
 *
 * **Aber das Wort bleibt stehen**, und das ist die eine Abweichung vom Wortlaut der
 * Notiz. Ein Knopf ist eine **Handlung** – er hat keine Antwort, die dastehen müsste, und
 * wer wissen will, was er tut, zeigt darauf. Eine **Wahl** hat eine: «30 Tage» *ist* die
 * Sache, und eingeklappt stünden dort drei anonyme Quadrate, von denen man jedes einzeln
 * anzeigen müsste, um zu lesen, worunter man wählt – am schlimmsten in dem Zustand, in
 * dem man am meisten Hilfe braucht: **bevor** man gewählt hat.
 *
 * **Ohne Symbole bleibt alles wie bisher** – nicht jede Aufzählung hat ein Bild
 * (Bar ↔ Überweisung), und dort ist die gleichmässige Aufteilung richtig.
 */
export function Segmented({ value, onChange, options, disabled, tip }: {
  // **Ohne Beschriftung darüber**: die Antworten sprechen für sich («Bar», «Überweisung»,
  // «Karte»); ein Wort darüber sagte nur noch einmal, was darunter steht.
  value: string; onChange: (v: string) => void;
  options: { value: string; label: string; icon?: LucideIcon }[];
  /** Gesperrt – der Wert bleibt sichtbar, der Grund steht in ``tip`` (Hover). */
  disabled?: boolean;
  tip?: string;
}) {
  const tucked = options.some((o) => o.icon);
  return (
    <div data-tip={tip}>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {options.map((o) => {
          const active = value === o.value;
          const Icon = o.icon;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(o.value)}
              disabled={disabled}
              aria-label={o.label}
              aria-pressed={active}
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                gap: 6,
                // **Mit Symbol so breit wie ihr Inhalt** – ohne Symbol die gleichmässige
                // Aufteilung von früher.
                flex: tucked ? 'none' : 1,
                padding: '6px 10px',
                fontSize: 13, fontWeight: 600,
                borderRadius: 8, cursor: disabled ? 'default' : 'pointer',
                border: `1px solid ${active ? 'var(--accent)' : 'var(--border-2)'}`,
                background: active ? 'var(--accent-soft)' : 'var(--bg-1)',
                color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
              }}
            >
              {Icon && <Icon size={14} style={{ flex: 'none' }} />}
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
