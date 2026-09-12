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

/**
 * ►►► **Unternehmensname · Abstand · Rechtsform** (Testnotiz #910). ◄◄◄
 *
 * «Inexxio» ist keine Rechtsperson, «Inexxio AG» ist eine – und der Datensatzname ist
 * überall derselbe: im Feed, in der Kopfzeile, in der Halter-Kette und auf dem Beleg.
 *
 * Zusammengesetzt wird er **nicht hier**: die Regel kennt eine Ausnahme (wer die Form
 * schon im Namen führt, bekommt sie nicht zweimal – «Muster AG», nicht «Muster AG AG»),
 * und eine zweite Fassung davon sähe richtig aus und wäre es nicht. Er kommt fertig vom
 * Server (`sites.legal_name`); der blosse Name bleibt der Rückfall, solange eine Antwort
 * ihn nicht mitbringt.
 */
export function organizationName(
  c: Pick<CompanySettings, 'company_name'> & { legal_name?: string },
): string | null {
  return c.legal_name?.trim() || c.company_name?.trim() || null;
}
