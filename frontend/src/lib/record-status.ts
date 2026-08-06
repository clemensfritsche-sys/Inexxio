import { Ban, Briefcase, CheckCircle2, Repeat, Shield, Truck, UserCircle } from 'lucide-react';
import type { Article, CompanySettings, Instance, UserProfile } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-flow';
import { statusConfig as articleStatusConfig } from '@/lib/article';

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

/**
 * Instanz und Einzelinstanz tragen ein **Status-Feld ohne Logik** (Basis-Neuaufbau):
 * die Werte und ihre Übergänge kommen mit der neuen Prozesslogik. Bis dahin zeigt die
 * Badge den gespeicherten Wert – und «inaktiv» sticht ihn, wie überall sonst.
 *
 * Bewusst KEINE Vorwegnahme: eine erfundene Zustandskarte («neu → in Arbeit → fertig»)
 * wäre genau die Art Annahme, die dieser Umbau loswerden wollte.
 */
const NEUTRAL: StatusCfg = { label: 'Neu', ...TONE.pending, icon: CheckCircle2 };

export function instanceStatus(
  i: Pick<Instance, 'status'> & { is_active?: boolean },
): StatusCfg {
  if (i.is_active === false) return INACTIVE;
  return { ...NEUTRAL, label: i.status === 'new' ? 'Neu' : i.status };
}

export function organizationStatus(c: Pick<CompanySettings, 'is_active'>): StatusCfg {
  return c.is_active === false
    ? INACTIVE
    : { label: 'Freigegeben', ...TONE.done, icon: CheckCircle2 };
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
