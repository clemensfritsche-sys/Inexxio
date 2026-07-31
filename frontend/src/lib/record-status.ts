import { Ban, Briefcase, CheckCircle2, Repeat, Shield, Truck, UserCircle } from 'lucide-react';
import type { Article, CompanySettings, Instance, Order, OrderSummary, UserProfile } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-flow';
import { statusConfig as articleStatusConfig } from '@/lib/article';
import { orderStatusConfig } from '@/lib/order';
import { instanceStatusConfig } from '@/lib/process';

/**
 * **Der Zustand eines ERP-Datensatzes – EINE Regel für alle Typen.**
 *
 * Ein Datensatz zeigt im ERP überall dasselbe: **Name · Objektnummer · Status**. Für den
 * *Namen* gibt es diese eine Ableitung längst (`record-name.ts`, Notiz #177) – für den
 * *Zustand* gab es sie nicht: der Feed baute die Badge selbst in einer fünfarmigen
 * Fallunterscheidung, jedes Detailfenster noch einmal. Zwei Stellen für dieselbe Aussage,
 * und sie sind auseinandergelaufen (Testnotiz #379): der Feed zeigte an einem Unternehmen
 * hart verdrahtet «Unternehmen» – die Datensatzart also, nicht den Zustand –, während das
 * Detail längst «Freigegeben»/«Inaktiv» sagte. Leiser, aber gleicher Fehler: das
 * Benutzer-Detail liess das Symbol der Rollen-Badge weg.
 *
 * Darum steht die Ableitung jetzt hier, und **Feed wie Detail lesen dieselbe Funktion**.
 * Sie können nicht mehr auseinanderlaufen – nicht, weil jemand daran denkt, sondern weil es
 * keinen zweiten Ort mehr gibt, an dem sie gebaut wird.
 *
 * Die Ableitung je Typ:
 *
 * - **Benutzer** → deaktiviert ≻ seine **Rolle**. Solange die Person in Betrieb ist, sagt
 *   die Badge, wofür sie da ist (grün: ein aktiver Datensatz ist gültig – Grau läse sich
 *   als «aus»); ist sie ausser Betrieb, zählt genau das und nichts anderes.
 * - **Artikel** → Entwurf · Freigegeben · Inaktiv (`lib/article`).
 * - **Auftrag** → wiederkehrend & fällig ≻ Status des Auftrags, «Abgebrochen» als
 *   Projektion über `abort_into_id` (`lib/order`). Ausdrücklich **nicht** der Stand eines
 *   einzelnen Schritts: der steht im Ablauf, nicht am Datensatz.
 * - **Instanz** → Projektion der zwei Achsen `quality` × `disposition` (`lib/process`).
 * - **Unternehmen** → Freigegeben · Inaktiv. Eine Gesellschaft kennt dieselben zwei
 *   Zustände wie alles andere, also dieselben zwei Wörter (Notiz #364).
 */

/** Rolle = Identität, nicht Ampel – aber ein aktiver Datensatz ist gültig, also grün. */
export const ROLE_CFG: Record<string, StatusCfg> = {
  admin: { label: 'Admin', ...TONE.done, icon: Shield },
  employee: { label: 'Mitarbeiter', ...TONE.done, icon: Briefcase },
  supplier: { label: 'Lieferant', ...TONE.done, icon: Truck },
  customer: { label: 'Kunde', ...TONE.done, icon: UserCircle },
};

export function userStatus(u: Pick<UserProfile, 'role'> & { is_active?: boolean }): StatusCfg {
  if (u.is_active === false) return INACTIVE;
  return ROLE_CFG[u.role] ?? ROLE_CFG.customer;
}

/** «Ausser Betrieb» – dieselben zwei Wörter und derselbe Ton für Person und Gesellschaft. */
const INACTIVE: StatusCfg = { label: 'Inaktiv', ...TONE.danger, icon: Ban };

export function articleStatus(a: Pick<Article, 'status'>): StatusCfg {
  return articleStatusConfig(a.status);
}

type OrderLike = Pick<Order | OrderSummary, 'status'> & Partial<Pick<Order, 'abort_into_id' | 'recurrence_due'>>;

export function orderStatus(o: OrderLike): StatusCfg {
  // «fällig» sagt mehr als «Entwurf»: ein wiederkehrender Auftrag, dessen Termin erreicht
  // ist, wartet auf einen Menschen. Das gilt im Feed wie im Detail – derselbe Datensatz.
  if (o.recurrence_due) return { label: 'fällig', ...TONE.danger, icon: Repeat };
  return orderStatusConfig(o.status, o.abort_into_id != null);
}

export function instanceStatus(i: Pick<Instance, 'quality' | 'disposition' | 'reserved_quantity'>): StatusCfg {
  return instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0);
}

export function organizationStatus(c: Pick<CompanySettings, 'is_active'>): StatusCfg {
  return c.is_active === false
    ? INACTIVE
    : { label: 'Freigegeben', ...TONE.done, icon: CheckCircle2 };
}
