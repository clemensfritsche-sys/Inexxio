# Archiv

**Alles hier beschreibt einen Zustand, den es nicht mehr gibt.** Diese Dokumente sind
nicht falsch – sie waren richtig, als sie geschrieben wurden. Wer nach dem heutigen Stand
sucht, ist hier falsch; wer wissen will, **warum** etwas so entschieden wurde, richtig.

| Datei | beschreibt |
|---|---|
| `2026-06-vorgaenger-system.md` | Das System **vor** dem Basis-Neuaufbau (Prozessschritte am Artikel, Verkauf/Shop, Dokumente, KI, Logistik). Stand bis August 2026 in `CLAUDE.md`. |
| `2026-06-architektur-review.md` | Performance-/Infrastruktur-Review, Juni 2026 |
| `2026-07-02-cleanup-report.md`, `2026-07-03-cleanup-report.md` | Aufräum-Runden Juli 2026 |
| `2026-07-architektur-review.md` | Logik-Review mit 15 Befunden, Juli 2026 |
| `2026-07-cleanup.md` | Code-Cleanup + Härtung, Juli 2026 |
| `2026-07-concept-review.md` | Konzept-Review |
| `2026-07-vorschlaege-D-E-F.md` | Ausgearbeitete Vorschläge D/E/F |
| `2026-08-test-report.md` | Testkampagne Prozessmodell (vormals `TEST_REPORT.md`, 71 Fälle; die Matrix ist seither gewachsen – laufend: `python -m scripts.scenario_report`) |
| `2026-08-cleanup.md` | Altlasten-Bereinigung August 2026 (vormals `docs/cleanup-2026-08.md`) |
| `2026-09-zahlungsmodul-vorgaenger.md` | Das gelöschte `deal`-Modul «Zahlung (alt)» – Prosa aus `CLAUDE.md`/`frontend/CLAUDE.md` und, als Anhang, PROCESS_CORE §9.12–§9.14c im Wortlaut |
| `2026-09-neuaufbau-zahlungsmodul.md` | Der Bauplan des Belegs (`beleg`), umgesetzt mit Migration 134 |
| `2026-09-arbeitsauftrag-beleg.md`, `2026-09-arbeitsauftrag-beleg-2.md`, `2026-09-beleg-pflichtangaben.md` | Arbeitsaufträge und Pflichtangaben-Analyse zum Beleg (umgesetzt, Migrationen 131–133) |
| `2026-09-konzept-eine-rechnung-je-modul.md` | «Der Beleg IST die Rechnung» (umgesetzt, Migration 138) |
| `2026-09-17-analyse-retoure.md` | Retoure/Gutschrift-Analyse – durch Migration 138 überholt |
| `2026-10-claude-md-chronik.md` | **Die Chronik der Runden** aus `CLAUDE.md` (August–Oktober 2026), wörtlich |
| `2026-10-backend-claude-md-chronik.md`, `2026-10-frontend-claude-md-chronik.md` | Die bisherigen `backend/CLAUDE.md` und `frontend/CLAUDE.md`, wörtlich (mit ihren Rundenberichten) |
| `2026-10-website-plan-chronik.md` | Der vollständige Website-Plan mit allen 124 Entscheiden (die Nummern gelten als Verweis weiter) |
| `2026-10-03-website-report.md`, `2026-10-04-website-report.md` | Abschlussberichte der Website (Fassung 1 und Umbau v2) |
| `2026-10-21-spezialloesungen-neu.md` | Neue Seite Speziallösungen (Kopf wie Porsche, Feld-Karten, Weg, Fragen-Grundbild) |
| `2026-10-21-mobil-menue.md` | Handy-Menü mit einer Ebene (Karten zum Wischen, «Alles zu …», Sprache als Karten) |
| `2026-10-22-handy-feinschliff.md` | Handy-Feinschliff: Menü zu, «Alles zu …» ohne Kärtchen, Fragen gleiten, Leiste ohne Fläche, Pfadnavigation nur breit |
| `2026-10-22-pfad-und-kontakt.md` | Pfadangabe auch am Desktop weg (nur noch JSON-LD), `/kontakt` bildschirmhoch |
| `2026-10-22-ueber-uns-und-kopf.md` | «Über uns» neu, Kopf-Menü mit «Alles zu», Profil-Menü als Auskunft |
| `2026-10-22-login-glas.md` | Login-Pop-up als Glas (ohne ✕, Handy als Blatt), Sprachen-Reihenfolge, Kürzel linksbündig |
| `2026-10-22-konto-neu.md` | «Mein Konto» als eine Seite im Stil der Website (Entwurf A) |
| `2026-10-22-fahrzeugtechnik-neu.md` | Fahrzeugtechnik, Trommeltausch und Verschleissteile im Layout von Speziallösungen |
| `2026-10-22-konto-feinschliff.md` | Konto: Name im Kopf, Adresssuche und Bearbeiten in der neuen Haut, Datum, Telefon, Anmelde-E-Mail ändern |
| `2026-10-23-krantechnik-neu.md` | Krantechnik neu (vier Seiten), Krane nach Mass für schwierige Gebäude, Heukran mit Funk statt Kabine |
| `2026-10-23-menu-titelbilder.md` | Menü-Kacheln zeigen das Titelbild ihrer Seite, Menübilder laden erst beim Berühren des Kopfs |

> **Regel:** Ein Rundenbericht gehört hierher, nicht in `CLAUDE.md` – `CLAUDE.md`
> beschreibt nur den Ist-Stand. Dateiname `JJJJ-MM[-TT]-<thema>.md`.

**Der heutige Stand steht in:** `CLAUDE.md` (Kontext und was gebaut ist) ·
`PROCESS_CORE.md` (die Prozesslogik) · `SYSTEM_LOGIC.md` (die Regeln als prüfbare Sätze) ·
`docs/attic.md` (was entfernt wurde und wo es liegt) · `docs/adr/` (Entscheidungen, jede
mit Kopfstatus).
