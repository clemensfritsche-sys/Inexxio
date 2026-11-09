import { Briefcase, Shield, UserCircle } from 'lucide-react';
import type { Article, CompanySettings, UserProfile } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-tone';
import { FREIGEGEBEN, INAKTIV, statusCfg } from '@/lib/process-status';
import { STAFF_ROLES, lookup, type InstanceKind, type Role } from '@/lib/vocab';

/**
 * **Der Zustand eines ERP-Datensatzes – EINE Regel für alle Typen**; Feed und Detail lesen
 * dieselbe Funktion. Die Wörter stehen in `lib/process-status`; hier steht nur, *welchen*
 * Status ein Typ zeigt:
 *
 * - **Benutzer** → seine **Rolle** (grün: ein Datensatz in Betrieb ist gültig).
 * - **Artikel** → Freigegeben · Inaktiv (einen Entwurf gibt es nicht).
 * - **Auftrag** → Im Prozess · Abgeschlossen · Abgebrochen, vom Server abgeleitet.
 * - **Instanz** → **keinen** – der Zustand steht an der Einzelinstanz.
 * - **Unternehmen** → Freigegeben · Inaktiv.
 */

/**
 * ►►► **Drei Rollen, und sie sagen den ZUGANG** ◄◄◄ – Lieferant ↔ Kunde ist eine Eigenschaft
 * des Vorgangs, nicht der Person.
 */
export const ROLE_CFG: Record<Role, StatusCfg> = {
  admin: { label: 'Admin', ...TONE.done, icon: Shield },
  employee: { label: 'Mitarbeiter', ...TONE.done, icon: Briefcase },
  user: { label: 'Benutzer', ...TONE.done, icon: UserCircle },
};

export function userStatus(u: Pick<UserProfile, 'role'>): StatusCfg {
  return lookup(ROLE_CFG, u.role) ?? ROLE_CFG.user;
}

/**
 * ►►► **Darf diese Person ins ERP?** ◄◄◄ `domain/policy.STAFF_ROLES`, generiert (`lib/vocab`) –
 * erlaubend gefragt, damit ein unbekannter Rollenwert nicht hereinkommt.
 */
export function isStaff(role: string | null | undefined): boolean {
  return (STAFF_ROLES as readonly string[]).includes(role ?? '');
}

/** Ist das der Admin? – nur für Anzeigen; ob man etwas darf, sagt der Server. */
export function isAdmin(role: string | null | undefined): boolean {
  return role === 'admin';
}

/** «Ausser Betrieb» – dieselben zwei Wörter und derselbe Ton für Person und Gesellschaft. */
const INACTIVE: StatusCfg = statusCfg(INAKTIV);

export function articleStatus(a: Pick<Article, 'status'>): StatusCfg {
  return statusCfg(a.status);
}

/** Der Auftragsstatus ist **abgeleitet** (`process.order_status`); «Freigegeben» ist eine
 *  Aktion, kein Zustand. */
export function orderStatus(o: { status?: string }): StatusCfg {
  return statusCfg(o.status ?? '');
}

export function organizationStatus(c: Pick<CompanySettings, 'is_active'>): StatusCfg {
  return c.is_active === false ? INACTIVE : statusCfg(FREIGEGEBEN);
}

/** Instanz-Typ → Beschriftung; getippt gegen `InstanceKind` (generiert aus `models/instance.KINDS`). */
const KIND_LABEL: Record<InstanceKind, string> = {
  einzeln: 'Einzeln',
  batch: 'Charge',
};

export function kindLabel(kind: string): string {
  return lookup(KIND_LABEL, kind) ?? kind;
}
