# 2026-11-10 · Dokumente, Assistent, Zeiterfassung: Prüfung und Fehler

## Anlass
Der Inhaber bemerkte zwei Fehler im Assistenten (Firma im Entwurf leer, Amazon-Link nicht
lesbar) und wollte Dokumente, Assistent und Zeiterfassung geprüft haben.

## Umgesetzt (Entscheide des Inhabers)
- **Firma im Entwurf**: der Personen-Entwurf übernahm aus einem Vorschlag nur Vorname, Nachname,
  E-Mail. Jetzt auch Firma und Rolle (Personal-Rollen nur für Admins).
- **Website-«+»**: «Öffnen» eines Artikel- oder Auftragsvorschlags öffnete einen Dokument-Entwurf,
  der Auftrag kam leer an. Jetzt reist nur die Nummer des Vorschlags; die Feed-Seite liest ihn
  selbst (`capture-context.draftFrom`, eine Stelle). Der Weg `?werte=` ist weg.
- **Webseiten lesen**: Werkzeug `web_fetch` des Anbieters im Gespräch (höchstens 3 je Antwort,
  20'000 Tokens je Seite), nie bei Mails; `pause_turn` geht weiter.
- **Kosten**: der Verlauf eines Gesprächs liegt im Zwischenspeicher (ein Merkpunkt).
- **Assistent klein**: ein Platzhalter-Ersatz (`handgriff.route_of`), Sperre bei «Weg».
- **Dokumente 1**: «Senden» eines Papiers ist Teilen, nicht Ausstellen – Mahnstufe, gültige
  Offerte, Partei und Storno-Mail bleiben richtig (`voucher.issued_link`).
- **Dokumente 3**: Zusatzangaben (`facts`) nur als Objekt mit Grenze (`documents.clean_facts`).
- **Zeit 7**: «Ende ändern» an einer Absenz; die 7-Tage-Regel prüft nur die geänderten Tage.
- **Zeit 8**: vergangene Feiertage im Vorschlag blass, nicht wählbar; der Server weist ab statt
  still zu übergehen.
- **Zeit 9**: Schlussstand eines Austritts erst ab dem Austrittstag.
- **Wisch-Schlüssel je Person** (Migration 187).

## Bewusst nicht (Entscheid des Inhabers)
Zweites Arztzeugnis sperrt das erste (Dokumente 2) · AGB-Darstellung (Dokumente 4) · Spätschicht
vor 20 Uhr (Zeit 6) · B-Vorschläge (Rechtstexte an einer Stelle, Papiere setzt der Server,
«Auf einen Blick» nur bei Änderungen von Menschen).

## Geprüft
Backend 839 grün, Frontend Typen · Lint · 161 Tests grün; neue Tests je rot gegen den alten Stand.
