// Optimistic Locking (Frontend-Seite): erkennt den Versions-Konflikt (HTTP 409)
// anhand der Server-Meldung. Der Datensatz-Stand (`updated_at`) wird mitgesendet;
// hat ihn jemand anders geändert, blockt der Server und der Client lädt frisch nach.

export function isVersionConflict(e: unknown): boolean {
  return e instanceof Error && /zwischenzeitlich|neu laden/i.test(e.message);
}
