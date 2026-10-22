/**
 * Die Bausteine der Konto-Seite (Gestaltung der Website, Stile `.kt-*` in `app/globals.css`):
 * ein Abschnitt mit zwei Spalten und ein Feld. Konto-Abschnitte bauen nur hieraus.
 */

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
export function KtField({ id, label, value, onChange, onEnter, type = 'text', placeholder, missing, readOnly, autoComplete }: {
  id: string; label: string; value: string; onChange?: (v: string) => void; onEnter?: () => void;
  type?: string; placeholder?: string; missing?: boolean; readOnly?: boolean; autoComplete?: string;
}) {
  return (
    <div className="kt-f">
      <label htmlFor={id}>{label}{missing && <em> · fehlt</em>}</label>
      <input
        id={id} className="kt-input" type={type} value={value} placeholder={placeholder}
        readOnly={readOnly} autoComplete={autoComplete}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onEnter?.(); }}
      />
    </div>
  );
}
