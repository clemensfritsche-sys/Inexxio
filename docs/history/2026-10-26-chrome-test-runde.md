# Runde «Chrome-Test» – Zahlung und Eigentum (26.10.2026)

Ausgangslage: ein automatischer Test mit Claude for Chrome auf inexxio-dev (Auftrag 100000964–966,
Testperson Monika Fritsche). Die Eigentums-Logik hat ohne Fehler funktioniert; die Runde
behebt, was beim Bedienen auffiel. Freigegeben vom Auftraggeber Punkt für Punkt.

## Was gemacht wurde

| Befund | Ursache | Änderung |
|---|---|---|
| Hover am verkauften Stück «müsste erst ausgebaut werden» | ein Satz für alles, was nicht im Regal liegt | eigener Satz je Status (Verbaut · Verkauft · übrige). **Wählbar bleibt es** – Greifen ist Aufheben (Reparatur, Retoure). |
| «2 von 1» | die Auswahl wuchs über die Menge | ist sie voll, ersetzt der neue Klick das zuletzt gewählte Stück |
| Auswahlliste schliesst nicht beim Klick daneben | fehlte | `pointerdown` ausserhalb schliesst (Scan-Dialog ausgenommen) |
| Klick auf eine Nummer verwirft den Entwurf | die Nummer navigierte; der Entwurf lebt nur im Browser | im Entwurf gibt es keine Navigation (`ErpNavContext` = `null`) |
| «Korrektur zu —» rot auf einer neuen Offerte | als Pflicht markiert | kein Pflichtwert; «keine» ist eine Antwort |
| Hover «Anbieten» nennt nur einen Punkt | `ask_problem` endete beim ersten Fund | alle Gründe untereinander; derselbe Text ist das Tor |
| Zoll-Hover «reist vom Artikel» | stimmte nicht für einen Eintrag an der Position | Satz korrigiert: am Artikel → überall, an der Position → nur dieser Beleg |
| Parteiname wechselt (Firma ↔ Person) | Kandidat las den Belegkopf, Angebot den Anzeigenamen | beide wie der Kopf: Firma, darunter «z. H. Person» |
| Seite springt beim Partner-Wählen | «z. H.» und Anschrift erschienen über der Klickstelle | Zeile «z. H.» hat immer ihren Platz; jede Beleg-Handlung hält den bearbeiteten Abschnitt an seiner Stelle (`lib/hold-place.ts`) |
| Ausfuhrnachweis: nur Kamera, Speichern ging nicht | (1) im Büro keine Kamera, (2) Nummer und Link kamen in zwei Aufrufen auf denselben alten Formularstand – die Nummer ging verloren, «Buchen» blieb gesperrt (auch Lieferantenrechnung) | Upload PDF oder Bild (`file-upload.tsx`, `attachments.store_file`, PDF unverändert); `PhotoShot` meldet in EINEM Aufruf |
| Storno-Hover unverständlich | Satz für Entwickler | je Stufe ein klarer Satz |
| «×» allein im Kasten | stand unter dem Formular | in der Zeile des Betrags |
| Suche: «Keine Treffer» vor der Antwort, Feed blitzt ungefiltert | Treffer ohne Bezug zur Eingabe | `useSearch.pending` («Sucht …»); Instanzen gelten nur für ihre Suche |
| «+» überdeckt den Feedback-Knopf | beide links unten | «+» rechts unten in der Liste |
| Neu: Seriennummer auf den Dokumenten | – | je Position «Seriennummer …» (Instanznummern, `voucher.serials_of`, aus den eingefrorenen Stücken) |

## Bewusst nicht gemacht
- Verkaufte Stücke sperren – sie sind wählbar (Abweichung), FIFO nimmt sie nie.
- Eigentum auf Offerte/AB drucken – der Eigentumsvorbehalt steht in den AGB.
- Bestandsbalken umfärben, E-Mail in der Partnersuche – abgelehnt.
- «Abgeschlossen» bei offener Rechnung – so gewollt: der Auftrag beschreibt die Stücke, das Geld
  steht in Beleg, Zahlungen-Liste und «zu tun».

## Gemessen
Lokal mit Playwright: Partner wählen bei 1100/820/390 px – «Angebote» bleibt auf dem Pixel
(vorher 18 bzw. 39 px Versatz). Ausfuhrnachweis mit PDF: hochgeladen, gebucht, «Erledigt».
Backend 825 Tests grün gegen ein Schema nur aus den Migrationen.
