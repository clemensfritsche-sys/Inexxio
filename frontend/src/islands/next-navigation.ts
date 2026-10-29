/**
 * Ersatz für `next/navigation` ausserhalb von Next (nur für `src/islands/`): auf der
 * Website ist jede Seite ein eigener Seitenaufruf, der Pfad steht also fest.
 */
export const usePathname = (): string => window.location.pathname;
