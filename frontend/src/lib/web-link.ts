/**
 * **Ein Link führt nur ins Web** – `http://` oder `https://`, sonst ist es Text. Ein
 * `javascript:`- oder `data:`-Wert in einem Stammdatenfeld liefe als Link beim Klick im
 * ERP. Dieselbe Regel prüft der Dienst beim Anlegen (`schemas/article._cad_url_web`).
 */
export function webHref(value: string | null | undefined): string | null {
  const v = value?.trim();
  return v && /^https?:\/\/[^\s/]/i.test(v) ? v : null;
}
