import type { Article, CompanySettings, Instance, OrderSummary, UserProfile } from '@/types';
import { personFullName } from '@/lib/utils';

/**
 * **Der Name eines ERP-Datensatzes – EINE Regel für alle Typen.** Name · Objektnummer · Status;
 * den Typ sagt das Symbol, nie das Namensfeld.
 *
 * - **Benutzer** → Anzeigename (Vor-/Nachname, sonst E-Mail).
 * - **Artikel** → sein Name.
 * - **Auftrag** → das Feld «Auftrag <Objektnummer>», vergeben bei der Freigabe.
 * - **Instanz** → der Artikel, dessen Exemplar sie ist.
 * - **Unternehmen** → Firmenname.
 *
 * `null` heisst «(noch) kein Name» – die Oberfläche setzt ihren eigenen Platzhalter.
 */
export function userName(u: UserProfile): string | null {
  return personFullName(u) || null;
}

export function articleName(a: Article): string | null {
  return a.name?.trim() || null;
}

/**
 * Der Auftrag trägt seinen Namen im Feld, vergeben im selben Zug wie die Nummer – hier nur
 * gelesen, nie zusammengesetzt.
 */
export function orderName(o: Pick<OrderSummary, 'name'>): string | null {
  return o.name?.trim() || null;
}

export function instanceName(i: Instance): string | null {
  return i.article_name?.trim() || null;
}

/**
 * ►►► **Unternehmensname · Abstand · Rechtsform** («Muster AG», nie «Muster AG AG»). ◄◄◄
 * Kommt fertig vom Server (`sites.legal_name`); der blosse Name ist der Rückfall.
 */
export function organizationName(
  c: Pick<CompanySettings, 'company_name'> & { legal_name?: string },
): string | null {
  return c.legal_name?.trim() || c.company_name?.trim() || null;
}
