# Befunde beim ersten Test des Verlaufs (06.11.2026)

Clemens testete den Verlauf auf dev an einem Dokument und an seiner Person.

1. **Eine Zeichnung wurde bei jedem Öffnen neu gelesen.** «Noch nicht gelesen» hiess
   «kein Text» – eine Zeichnung hat keinen. Jedes Öffnen rief die KI (Kosten) und
   schrieb neue Stichworte. Jetzt EINE Regel `documents.unread` (weder Text noch
   Stichworte noch Angaben); ein Lesen ohne Text hinterlässt `""`. Test
   `test_a_drawing_without_text_is_read_once`, gegen die Fehlerform geprüft.
2. **Im Verlauf der Person stand alles doppelt.** Eine Handlung, die über mehrere
   Transaktionen läuft (der Mail-Abgleich speichert je Postfach), kam auf der nächsten
   Seite mit ihrer älteren Zeile ein zweites Mal. `_BLOCKS` nimmt eine Handlung nur noch,
   wenn keine ihrer Zeilen am Cursor oder danach liegt. Test
   `test_a_handling_over_several_transactions_stands_once` (Fehlerform nachgestellt). Die
   Oberfläche zeigt zudem jeden Eintrag nur einmal (`history.entriesOf`).
3. **«Postfach synced_at» stand im Verlauf der Person**, die das Postfach verbunden hatte.
   Das Postfach gehört der Gesellschaft: `domain/log.OBJECT["mailboxes"]` liest die
   Nummer aus dem Kanal `c<Objektnummer>`. Ältere Einträge bleiben, wo sie sind (das Log
   ist unveränderlich).
4. Ein Ereignis stand mit seinem Namen zweimal da («document.read document.read»): der
   Name steht jetzt nur im Kopf des Blocks.
