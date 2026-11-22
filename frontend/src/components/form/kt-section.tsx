/**
 * Die Bausteine der Konto-Seite (Gestaltung der Website, Stile `.kt-*` in `app/globals.css`):
 * ein Abschnitt mit zwei Spalten, ein Feld und ein Datum. Konto-Abschnitte bauen nur hieraus;
 * Adressbuch und Firmenfeld tragen dieselbe Haut, wenn das Konto sie zeigt (`cards` / `look`).
 */

import { useEffect, useId, useState } from 'react';
import { Input } from './field';
import { useT } from '@/lib/lang';

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
export function KtField({ id: given, name, label, value, onChange, onEnter, type = 'text', placeholder, missing, readOnly, autoComplete, list }: {
  /** API-Schlüssel und Datensatz des Feldes (`useField`). */
  name: string;
  id?: string; label: string; value: string; onChange?: (v: string) => void; onEnter?: () => void;
  type?: string; placeholder?: string; missing?: boolean; readOnly?: boolean; autoComplete?: string;
  /** Vorschläge (`<datalist>`), z. B. die Rechtsformen. */
  list?: string;
}) {
  const auto = useId();
  const id = given ?? auto;
  const t = useT();
  return (
    <div className="kt-f">
      <label htmlFor={id}>{label}{missing && <em> · {t('fehlt')}</em>}</label>
      <Input
        id={id} name={name} className="kt-input" type={type} value={value}
        placeholder={placeholder} readOnly={readOnly} autoComplete={autoComplete} list={list}
        onChange={onChange} onEnter={onEnter}
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

/**
 * ►►► **Tag · Monat · Jahr, wie man sie tippt.** ◄◄◄ Ein Trennzeichen (`.` `/` `-` Leerschlag)
 * schliesst Tag oder Monat ab und wird zum Punkt; eine dritte Ziffer nach zwei setzt den Punkt
 * selbst. So werden «15081980», «15.08.1980», «17/12/1997» und «1.5.1980» zum selben Muster –
 * und wer den Punkt löscht, kann ihn löschen (gesetzt wird er erst mit der nächsten Ziffer).
 */
export function maskDate(raw: string): string {
  const parts = ['', '', ''];
  let at = 0;
  for (const ch of raw) {
    if (/\d/.test(ch)) {
      if (at < 2 && parts[at].length === 2) at += 1;
      if (parts[at].length < (at === 2 ? 4 : 2)) parts[at] += ch;
    } else if (/[./\-\s,]/.test(ch) && at < 2 && parts[at]) {
      at += 1;
    }
  }
  return parts[0] + (at > 0 ? `.${parts[1]}` : '') + (at > 1 ? `.${parts[2]}` : '');
}

/**
 * Ein Datum zum Tippen (Geburtsdatum) – «TT.MM.JJJJ» statt des Kalenders des Browsers: ein
 * Geburtstag liegt Jahrzehnte zurück, und dorthin blättert niemand gern. Weitergegeben wird
 * nur ein gültiger Tag (oder leer); bis dahin sagt die Beschriftung «· ungültig».
 */
export function KtDate({ id, name, label, value, onChange, onEnter, missing }: {
  name: string;
  id: string; label: string; value: string; onChange: (iso: string) => void; onEnter?: () => void;
  missing?: boolean;
}) {
  const [text, setText] = useState(() => isoToText(value));
  const t = useT();
  // Ein neuer Wert von aussen (anderer Datensatz) ersetzt die Eingabe – der eigene nicht.
  useEffect(() => {
    setText((t) => (textToIso(t) ?? '') === value ? t : isoToText(value));
  }, [value]);
  const iso = text ? textToIso(text) : '';
  const invalid = iso === null && text.length >= 8;
  return (
    <div className="kt-f">
      <label htmlFor={id}>{label}{invalid ? <em> · {t('ungültig')}</em> : missing && !text && <em> · {t('fehlt')}</em>}</label>
      <Input
        id={id} name={name} className="kt-input" inputMode="numeric"
        autoComplete="bday" placeholder={t('TT.MM.JJJJ')} value={text}
        onChange={(raw) => {
          const next = maskDate(raw);
          setText(next);
          const nextIso = next ? textToIso(next) : '';
          if (nextIso !== null && nextIso !== value) onChange(nextIso);
        }}
        onEnter={onEnter}
      />
    </div>
  );
}
