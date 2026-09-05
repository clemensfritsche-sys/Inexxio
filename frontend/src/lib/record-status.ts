import { Briefcase, Shield, Truck, UserCircle } from 'lucide-react';
import type { Article, CompanySettings, UserProfile } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-flow';
import { FREIGEGEBEN, INAKTIV, statusCfg } from '@/lib/process-status';

/**
 * **Der Zustand eines ERP-Datensatzes – EINE Regel für alle Typen.**
 *
 * Ein Datensatz zeigt im ERP überall dasselbe: **Name · Objektnummer · Status**. Für den
 * *Namen* gibt es diese eine Ableitung längst (`record-name.ts`, Notiz #177) – für den
 * *Zustand* gab es sie nicht: der Feed baute die Badge selbst in einer fünfarmigen
 * Fallunterscheidung, jedes Detailfenster noch einmal. Zwei Stellen für dieselbe Aussage,
 * und sie sind auseinandergelaufen (Testnotiz #379).
 *
 * Darum steht die Ableitung hier, und **Feed wie Detail lesen dieselbe Funktion**.
 *
 * **Die Wörter selbst stehen nicht hier**, sondern in `lib/process-status` – der einen
 * Statusliste, die das Backend spiegelt (Testnotiz #669). Diese Datei sagt nur, *welchen*
 * Status ein Datensatztyp zeigt; *wie* er heisst und aussieht, ist überall dasselbe.
 * Vorher trug jede Achse ihre eigene Karte: derselbe Zustand hiess am Artikel
 * «Freigegeben», am Auftrag ebenfalls «Freigegeben» (obwohl das gar kein Zustand ist)
 * und an der Instanz «Neu».
 *
 * Die Ableitung je Typ:
 *
 * - **Benutzer** → deaktiviert ≻ seine **Rolle**. Solange die Person in Betrieb ist, sagt
 *   die Badge, wofür sie da ist (grün: ein aktiver Datensatz ist gültig – Grau läse sich
 *   als «aus»); ist sie ausser Betrieb, zählt genau das und nichts anderes.
 * - **Artikel** → Freigegeben · Inaktiv. Einen Entwurf gibt es nicht: der Artikel
 *   entsteht erst mit seiner Freigabe.
 * - **Auftrag** → Im Prozess · Abgeschlossen · Abgebrochen, **abgeleitet** aus dem
 *   Zustand seiner Einzelinstanzen (`process.order_status`). Der Server rechnet ihn –
 *   hier wird er nur angezeigt.
 * - **Instanz** → **keinen**. Eine Gruppe hat keinen Zustand; ihn aus ihren Stücken zu
 *   projizieren geht nur, solange genau eines darunter liegt, und bei einer Charge mit
 *   gemischten Zuständen gäbe es keine richtige Antwort (Testnotiz #675). Der Zustand
 *   steht an der **Einzelinstanz** – dort ist er eindeutig.
 * - **Unternehmen** → Freigegeben · Inaktiv, dieselben zwei Wörter wie überall (#364).
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
const INACTIVE: StatusCfg = statusCfg(INAKTIV);

export function articleStatus(a: Pick<Article, 'status'>): StatusCfg {
  return statusCfg(a.status);
}

/**
 * Der Auftragsstatus ist **abgeleitet** (`process.order_status`): Im Prozess, solange
 * Stücke unterwegs sind · Abgeschlossen, sobald eines das Ziel erreicht hat ·
 * Abgebrochen, wenn keines es mehr erreichen kann. «Freigegeben» ist bewusst nicht
 * dabei – Freigeben ist die Aktion, mit der der Auftrag entstanden ist, kein Zustand
 * (Testnotiz #669).
 */
export function orderStatus(o: { is_active?: boolean; status?: string }): StatusCfg {
  if (o.is_active === false) return INACTIVE;
  return statusCfg(o.status ?? '');
}

export function organizationStatus(c: Pick<CompanySettings, 'is_active'>): StatusCfg {
  return c.is_active === false ? INACTIVE : statusCfg(FREIGEGEBEN);
}

/**
 * Instanz-Typ → Beschriftung. Die Werte spiegeln `models/instance.KINDS`; der Abgleich
 * ist getestet (`tests/test_frontend_mirrors.py`), damit die Oberfläche keinen Typ
 * kennt, den es nicht gibt – und keinen übersieht.
 */
export const KIND_LABEL: Record<string, string> = {
  'einzeln': 'Einzeln',
  'batch': 'Charge',
};

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? kind;
}
