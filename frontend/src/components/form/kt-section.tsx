/**
 * Die Bausteine der Konto-Seite (Gestaltung der Website, Stile `.kt-*` in `app/globals.css`):
 * ein Abschnitt mit zwei Spalten, ein Feld und ein Datum. Konto-Abschnitte bauen nur hieraus;
 * Adressbuch und Firmenfeld tragen dieselbe Haut, wenn das Konto sie zeigt (`cards` / `look`).
 */

import { useEffect, useId, useState } from 'react';

/** Ein Abschnitt: links Titel und ein Satz (darunter z. B. «Gespeichert»), rechts die Sache. */
export function KtSection({ id, title, text, aside, children }: {
  id: string; title: string; text: string; aside?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="kt-sec" id={id} aria-labelledby={`${id}-h`}>
      <div className="kt-sec-h">
        <h2 id={`${id}-h`}>{title}</h2>
        <p>{text}</p>
        {aside && <div>{aside}</div>}
      </div>
      <div className="kt-body">{children}</div>
    </section>
  );
}

/** Ein Feld: Beschriftung über einer ruhigen grauen Fläche; ein fehlender Pflichtwert sagt «· fehlt». */
export function KtField({ id: given, label, value, onChange, onEnter, type = 'text', placeholder, missing, readOnly, autoComplete, list }: {
  id?: string; label: string; value: string; onChange?: (v: string) => void; onEnter?: () => void;
  type?: string; placeholder?: string; missing?: boolean; readOnly?: boolean; autoComplete?: string;
  /** Vorschläge (`<datalist>`), z. B. die Rechtsformen. */
  list?: string;
}) {
  const auto = useId();
  const id = given ?? auto;
  return (
    <div className="kt-f">
      <label htmlFor={id}>{label}{missing && <em> · fehlt</em>}</label>
      <input
        id={id} className="kt-input" type={type} value={value} placeholder={placeholder}
        readOnly={readOnly} autoComplete={autoComplete} list={list}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onEnter?.(); }}
      />
    </div>
  );
}

const isoToText = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : '';
};

/** «TT.MM.JJJJ» → «JJJJ-MM-TT», nur ein Tag, den es gab (ab 1900, nicht in der Zukunft). */
function textToIso(text: string): string | null {
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(text.trim());
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const t = new Date(Date.UTC(y, mo - 1, d));
  if (t.getUTCDate() !== d || t.getUTCMonth() !== mo - 1 || y < 1900 || t > new Date()) return null;
  return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

/** Ziffern setzen ihre Punkte selbst («15081980» → «15.08.1980»); wer Punkte tippt, behält seine. */
function maskDate(raw: string): string {
  if (raw.includes('.')) return raw.replace(/[^\d.]/g, '').slice(0, 10);
  const d = raw.replace(/\D/g, '').slice(0, 8);
  return [d.slice(0, 2), d.slice(2, 4), d.slice(4)].filter(Boolean).join('.');
}

/**
 * Ein Datum zum Tippen (Geburtsdatum) – «TT.MM.JJJJ» statt des Kalenders des Browsers: ein
 * Geburtstag liegt Jahrzehnte zurück, und dorthin blättert niemand gern. Weitergegeben wird
 * nur ein gültiger Tag (oder leer); bis dahin sagt die Beschriftung «· ungültig».
 */
export function KtDate({ id, label, value, onChange, onEnter }: {
  id: string; label: string; value: string; onChange: (iso: string) => void; onEnter?: () => void;
}) {
  const [text, setText] = useState(() => isoToText(value));
  // Ein neuer Wert von aussen (anderer Datensatz) ersetzt die Eingabe – der eigene nicht.
  useEffect(() => {
    setText((t) => (textToIso(t) ?? '') === value ? t : isoToText(value));
  }, [value]);
  const iso = text ? textToIso(text) : '';
  const invalid = iso === null && text.length >= 8;
  return (
    <div className="kt-f">
      <label htmlFor={id}>{label}{invalid && <em> · ungültig</em>}</label>
      <input
        id={id} className="kt-input" inputMode="numeric" autoComplete="bday" placeholder="TT.MM.JJJJ"
        value={text}
        onChange={(e) => {
          const next = maskDate(e.target.value);
          setText(next);
          const nextIso = next ? textToIso(next) : '';
          if (nextIso !== null && nextIso !== value) onChange(nextIso);
        }}
        onKeyDown={(e) => { if (e.key === 'Enter') onEnter?.(); }}
      />
    </div>
  );
}
