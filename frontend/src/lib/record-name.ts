import type { Article, CompanySettings, Instance, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';

/**
 * **Der Name eines ERP-Datensatzes – EINE Regel für alle Typen.**
 *
 * Ein Datensatz zeigt im ERP überall dasselbe: **Name · Objektnummer · Status**. *Welcher
 * Typ* er ist, sagt sein Symbol – nie das Namensfeld. Vorher stand im Namen eines Auftrags
 * das Wort «Auftrag» und im Namen einer Instanz das Wort «Instanz»: der Typ war in den Namen
 * gerutscht, und zwei Datensätze desselben Typs sahen im Feed identisch aus (Notiz #177).
 *
 * Die Ableitung je Typ:
 *
 * - **Benutzer** → Anzeigename (Vor-/Nachname, sonst E-Mail).
 * - **Artikel** → sein Name (frei vergeben).
 * - **Auftrag** → kommt fertig vom Backend (`orders.order_display_name`): bewusst vergebener
 *   Titel ≻ Artikel ≻ erster Positions-Artikel «+N» ≻ «Auftrag». Feed und Detail lesen
 *   dasselbe Feld, es kann also nicht auseinanderlaufen.
 * - **Instanz** → der Artikel, dessen Exemplar sie ist. Eine Instanz trägt keinen eigenen
 *   Namen – ihre Identität ist die Objektnummer.
 * - **Unternehmen** → Firmenname.
 *
 * `null` heisst «dieser Datensatz hat (noch) keinen Namen» – die Oberfläche setzt dann ihren
 * eigenen Platzhalter, statt hier einen zu erfinden.
 */
export function userName(u: UserProfile): string | null {
  const n = userDisplayName(u);
  return n && n !== u.email ? n : null;
}

export function articleName(a: Article): string | null {
  return a.name?.trim() || null;
}

/**
 * Der Auftrag trägt heute **kein** Namensfeld – also gibt es keinen Namen, und `null`
 * sagt genau das. Die Oberfläche setzt dafür ihren Platzhalter; ein Rückfall auf das
 * Typ-Wort «Auftrag» wäre der Fehler, den `record-name` gerade abstellt (Notiz #177):
 * der Typ steht im Symbol, nie im Namen.
 */
export function orderName(): string | null {
  return null;
}

export function instanceName(i: Instance): string | null {
  return i.article_name?.trim() || null;
}

/** Standort **und** Unternehmen tragen ihren Namen im selben Feld – der Hauptsitz führt
 *  die Firma, eine Aussenstelle ihren Standortnamen («Werk Nord»). */
export function organizationName(c: Pick<CompanySettings, 'company_name'>): string | null {
  return c.company_name?.trim() || null;
}
