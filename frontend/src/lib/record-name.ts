import type { Article, CompanySettings, Instance, OrderSummary, UserProfile } from '@/types';
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
 * - **Auftrag** → sein Name aus dem Feld: «Auftrag <Objektnummer>», vergeben bei der
 *   Freigabe (Notiz #672). Feed und Detail lesen dasselbe Feld, es kann also nicht
 *   auseinanderlaufen.
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
 * Der Auftrag trägt seinen Namen im Feld: «Auftrag <Objektnummer>», vergeben **im selben
 * Zug wie die Nummer** (Notiz #672). Vorher gab es keinen, denn vorher gibt es den
 * Auftrag nicht – ein Entwurf lebt nur im Browser.
 *
 * Der Name wird hier nur gelesen, nie zusammengesetzt: würde die Oberfläche ihn selbst
 * bauen, gäbe es zwei Stellen, an denen er entsteht, und die erste Umbenennung liesse
 * sie auseinanderlaufen.
 */
export function orderName(o: Pick<OrderSummary, 'name'>): string | null {
  return o.name?.trim() || null;
}

export function instanceName(i: Instance): string | null {
  return i.article_name?.trim() || null;
}

/** Standort **und** Unternehmen tragen ihren Namen im selben Feld – der Hauptsitz führt
 *  die Firma, eine Aussenstelle ihren Standortnamen («Werk Nord»). */
export function organizationName(c: Pick<CompanySettings, 'company_name'>): string | null {
  return c.company_name?.trim() || null;
}
