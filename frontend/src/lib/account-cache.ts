/**
 * ►►► Der Anzeige-Cache des Kontos – nur Anzeige, nie ein Ausweis. ◄◄◄
 *
 * Die öffentliche Website (`website/`) liegt auf derselben Domain, hat aber kein
 * Firebase-SDK. Damit ihr Kopf «Anmelden» bzw. das Profilmenü (mit Profilbild) und den
 * ERP-Punkt zeigen kann, liest sie diese vier Schlüssel (WEBSITE_PLAN §7.5, Schnittstellen S1/S2). Sie
 * entscheidet damit **nichts**: den Schutz von `/konto` und `/erp` hat das ERP.
 *
 * Die Schlüssel stehen gleichlautend in `website/src/scripts/account.ts`;
 * `website/scripts/account.test.mjs` hält beide Seiten deckungsgleich.
 */

export const ROLE_KEY = 'inexxio_user_role';
export const NAME_KEY = 'inexxio_user_fullname';
/** S2: `{ email, phone, company }` – zum Vorausfüllen des Anfrage-Formulars der Website. */
export const CONTACT_KEY = 'inexxio_user_contact';
/** Das Profilbild (Google), wie es das ERP zeigt – im Profilknopf der Website (#1105). */
export const PHOTO_KEY = 'inexxio_user_photo';

type Contact = { email?: string | null; phone?: string | null; company_name?: string | null };

/** Schreibt die Kontaktangaben, die das Anfrage-Formular vorausfüllt (S2). */
export function rememberContact(p: Contact): void {
  try {
    localStorage.setItem(
      CONTACT_KEY,
      JSON.stringify({ email: p.email ?? '', phone: p.phone ?? '', company: p.company_name ?? '' }),
    );
  } catch {
    // Kein Speicher (privates Fenster) – dann füllt die Website eben nichts vor.
  }
}

/** Merkt das Profilbild – oder räumt es, wenn es keines (mehr) gibt. */
export function rememberPhoto(url: string | null | undefined): void {
  try {
    if (url) localStorage.setItem(PHOTO_KEY, url);
    else localStorage.removeItem(PHOTO_KEY);
  } catch {
    // Kein Speicher – dann bleiben es die Initialen.
  }
}

/** Räumt den ganzen Anzeige-Cache – beim Abmelden und wenn keine Sitzung mehr besteht. */
export function clearAccountCache(): void {
  try {
    for (const key of [ROLE_KEY, NAME_KEY, CONTACT_KEY, PHOTO_KEY]) localStorage.removeItem(key);
  } catch {
    // Kein Speicher, nichts zu räumen.
  }
}
