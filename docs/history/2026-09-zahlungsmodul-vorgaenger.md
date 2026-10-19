# Das Vorgänger-Zahlungsmodul (`deal-work.tsx`) — Archiv

> **Diesen Text nicht als Vorlage verwenden.** Er beschreibt eine Oberfläche, die es
> **nicht mehr gibt**: `domain/deal` · `services/deal` · `schemas/deal` · `models/deal`
> und `deal-work.tsx` sind mit **Testnotiz #960** ersatzlos gelöscht. Was das Modul
> konnte, kann der **Beleg** (`components/erp/beleg-work.tsx`, PROCESS_CORE §9.15) – in
> einer Datenform, die dazu passt.
>
> Er steht hier, weil in ihm **fachliche Entscheidungen** stecken, die weiter gelten und
> in der Prosa des Nachfolgers nur in ihrem Ergebnis auftauchen: warum eine Gutschrift
> eine negative Rechnung ist, warum ein Storno den Weg behält, warum die Währung an den
> Betrag gehört. Wer eine dieser Regeln neu stellt, liest zuerst, warum sie so lautet.
>
> `CLAUDE.md` liest **jede** Sitzung als Erstes – und eine Beschreibung, die nicht mehr
> stimmt, kostet dort mehr, als sie nützt. Darum liegt sie hier.

## Zahlung (`components/erp/deal-work.tsx`) — bis September 2026
►►► **Die Karte IST der Beleg — und sie WÄCHST** (Testnotiz #899). ◄◄◄ *Belegkopf ·
Positionen · Bedingungen · Rückläufe · Rechnung & Zahlungen · Handlungen*, in **beide**
Richtungen dasselbe. Was Einnahme von Ausgabe unterscheidet, **reist fertig mit**
(`DealEmbed.label`, `stages[].label/verb`, `party_word`, `ask_verb`, `charge_word`,
`money_label`, `stage_label`, `undo`) – die Karte braucht dafür **kein einziges `if` auf
die Richtung**; ein Wächter zählt sie.

- ►►► **Ein Dokument, kein Stapel von Blöcken.** ◄◄◄ Vorher war die Karte eine **Kette**:
  Positionen, Abschnitt «Angebot», Abschnitt «Auftrag», Geld – und mit der Zusage kam ein
  Block dazu (`Agreed`), der Partner, Summe und Fristen **noch einmal** zeigte, in anderer
  Reihenfolge als oben. Jetzt ist es **ein** Beleg in der Ordnung, die ein Beleg hat:
  **Kopf** (`DocHead` – Belegart · An <Partner> · Datum) → **Positionen** mit Summe
  (`Goods` → `Totals`) → **Bedingungen** (`Terms` – Währung und die beiden Fristen) →
  **Rückläufe** (`Offer` – der Angebotsspiegel) → **Rechnung & Zahlungen** (`Money`) →
  **Handlungen** unter einer Haarlinie, wie die Unterschrift.
- **Er wächst, statt umzuschalten**: der Kopf heisst nach der Zusage «Auftrag» statt
  «Angebot» und nennt den Empfänger, die Preisspalte trägt die gebuchten Zahlen statt des
  Entwurfs, die Bedingungen stehen als Auskunft statt als Feld, die Rückläufe klappen auf
  **eine** Zeile zusammen, und darunter kommt das Geld dazu. *Ein späterer PDF-Export ist
  damit dieselbe Komponente ohne Knöpfe.*
- **Jede Beleg-Angabe steht an GENAU einem Ort** (Empfänger · Zusagedatum · Zahlungsfrist ·
  Liefertermin · Steueraufteilung · Nettosumme) – gezählt, nicht behauptet. Und die
  **Summe** gibt es einmal (`Totals`): Vorschau aus getippten Preisen und gebuchte Zahlen
  des Servers sind dieselbe Aufstellung; zwei Bauteile wären zwei Schreibweisen für Netto,
  Steuer und Total.
- **Zusammengeklappt wird erst NACH dem Zuschlag** («1 von 2 Angeboten gewählt»): solange
  verhandelt wird, versteckt der Beleg nichts. Danach sind die unterlegenen Zeilen der
  **Nachweis**, warum so entschieden wurde – und der gehört auf Klick.
- **Die Zahlungsfrist steht über der Lieferfrist** (#897) – im Beleg wie an der
  Angebotszeile, und auch in deren **Anzeige**: sie ist die folgenreichere Angabe (aus ihr
  kommt die Fälligkeit, und null heisst Vorauszahlung), und zwei Formulare für dieselben
  zwei Fragen dürfen nicht anders herum fragen.

- **Zwei Stufen, und der dritte Schritt ist KEINE.** Unumkehrbar sind zwei Dinge: nichts
  zugesagt · zugesagt. «Abgeschlossen» stand einmal als dritte Stufe da und war genau das
  Missverständnis – ein **Zustand** in einer Reihe von **Schritten**. Der dritte Schritt ist
  das **Geld**: eine Zahlung macht aus einem Angebot keine Zusage, sie ist reversibel, und
  sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach. Er steht dort, wo man
  ihn erwartet, und ist ab der Zusage bedienbar. Das Geld trägt darum auch **keinen
  eigenen Schlüssel** mehr: der Abschnitt nennt sich über `d.money_label` vom Server.
- ►►► **Der Verlauf steht AN den Abschnitten** (Testnotiz #868). ◄◄◄ *«Kann man diese
  Anzeige nicht vertikal machen und es so visuell etwas besser strukturieren – mir passt
  das da oben nicht.»* Über der Karte stand eine waagrechte Stufen-Leiste. Sie entstand als
  **Bedienelement** (#863 nahm ihr den Handler), und was blieb, war eine Zeile mit
  denselben drei Wörtern wie die Abschnitte darunter. **Die Abschnitte SIND die vertikale
  Fassung**: ein Punkt vor der Überschrift (`ModuleSection state`) sagt dasselbe an der
  Stelle, an der man den Namen ohnehin liest – vorbei (dunkel) · dran (Akzent) · steht noch
  aus (Haarlinie). Damit sind `ModuleSteps`, `ALL_STEPS`, die drei Schlüssel (`OFFER`,
  `AGREED`, `MONEY`) und `moneyValue` entfallen.
- **Der Angebotsspiegel ist der Kern der ersten Zeile** (`quotes`): je angefragter
  Gegenpartei eine Zeile mit Preis, Lieferfrist und Zahlungsfrist. **Wo niemand zugelassen
  ist, wird gesucht** (`ObjectSelect` + `api.searchDealParties`); wo genau einer steht, gibt
  es nichts zu wählen und der Knopf heisst schlicht `ask_verb` (#793).
- **Worum es geht, steht oben und ist abgeleitet** (`lines`) – Menge, Name, Objektnummer je
  Artikel; die **Spezifikation erst auf Klick**. Sie wird nicht getippt und nicht ausgewählt.
- **Die Knöpfe hängen an `can`** (`services/deal.ACTIONS`) – nie an der Rolle und nie an
  der Stufe: dieselbe Tabelle ist Auskunft **und** Tor. Eine **Gegenpartei** bekommt
  dieselbe Komponente; dass sie weniger sieht, entscheidet die **Antwort**, nicht die
  Oberfläche (`open == null` → die Geld-Zeile rendert nichts; wer nicht den Zuschlag hat,
  bekommt Name, Preis und Frist des Gewählten gar nicht erst geliefert).
- ►►► **Die Geld-Zeile hängt an `can`, nicht an «ist dieses Modul dran».** ◄◄◄ Bei einem
  **Zahlungsziel** ist es das längst nicht mehr, wenn das Geld kommt: gemessen erlaubte der
  Dienst Rechnung und Zahlung an einem abgeschlossenen Auftrag, die Karte bot **null**
  Knöpfe an – eine erfundene Sperre ohne Schlüssel. Die beiden **Stufen** behalten `active`:
  dort ist es richtig, man verhandelt nicht an einem Modul, das nicht dran ist.
- ►►► **Jeder Knopf trägt eine Ausprägung.** ◄◄◄ Ein blosser `.erp-actbtn` hat
  `border: 1px solid transparent` und keine Fläche – er **sieht aus wie Text**. Erst
  `-primary` (der Vorschlag) / `-neutral` (die übrigen) / `-danger` (Storno) machen daraus
  einen Knopf, `-icon` daraus ein Quadrat. Das war die Ursache von «die Buttons gefallen
  mir nicht», nicht der Geschmack.
- **Und «Weitere» gibt es nicht.** Ein Auswahlmenü ist die richtige Form für viele
  gleichrangige Dinge; hier waren es drei, und eines davon (der Storno) ist die
  Gegenhandlung des ganzen Vorgangs. **Was man jetzt tun kann, muss man sehen** – welches
  das naheliegende ist, sagt die Fläche des Knopfes, kein Klick, der es erst hervorholt.
- **Wo man steht, sagt die Zeile** – gefüllter Punkt in der Akzentfarbe, Beschriftung in
  Versalien. Punkt und Wort teilen dafür **eine** Zeilenhöhe (`HEAD_H`) statt zweier
  geratener Abstände (#798, gemessen: Δy 0,0 px).
- **Offerte und Absage sind Symbol-Knöpfe** wie im Beschaffungs-Beleg (#800): «Offerte»
  beschreibt einen *Zustand*, der Knopf löst eine *Handlung* aus.
- **Die Angabe «Was ist zu tun?» steht an SEINER Zeile** (`quote.ref`) – seine
  Artikelnummer, sein Shop-Link oder ein Satz; sieht sie aus wie eine Adresse, ist sie ein
  Link. Sie gilt in **beiden** Richtungen (#803): beim Einkauf sagt sie, wie man bei ihm
  bestellt, beim Verkauf, was er bekommt.
- **Gerechnet wird nichts im Browser** – *berechnet · bezahlt · offen · noch nicht
  berechnet* kommen vom Server. «Bezahlt» heisst «gefordert UND beglichen»; ohne die
  Unterscheidung stünde direkt nach der Zusage «Bezahlt» da, weil *offen* null ist.
- **EINE naheliegende Handlung, und der Server sagt welche** (`next_charge` ↔
  `next_payment`): erst fordern, dann kassieren. Die Rangfolge sagt die **Fläche** des
  Knopfes (`-primary` ↔ `-neutral`), nicht ein Umweg – alle stehen da.
- **Die Richtung ist ein SYMBOL mit Hover, kein Dauertext** (#797): Plus und Minus sind die
  Buchhaltungssprache selbst – ein Wort daneben sagt dieselbe Sache ein zweites Mal.
- **Die Referenz nimmt den Rest und wird gekappt, das Datum nicht.** Umgekehrt war es
  falsch: das Datum bekam `flex-1` und behielt bei einer 227 px breiten QR-Referenz 39 px –
  «20.8.2026» hat keine Umbruchstelle und malte sich über seine Box hinaus (gemessen
  380,1 px bei 375 px; **kein Element-Rahmen zeigte es, nur der Text selbst**). Wer auf
  Überlauf misst, muss darum auch **Textknoten** messen – **und sie an jedem `overflow:
  hidden`-Vorfahren kappen**: ein `truncate`-Text ist wirklich abgeschnitten, und eine
  Messung, die die Lösung als Fehler meldet, ist so falsch wie eine, die ihn übersieht.
- **Im Editor** (`MoneyFields`) **zwei** Angaben – und **kein einziges Label darüber**
  (#816/#817/#819): der Schieber **Einnahme ↔ Ausgabe** (Vorgabe Einnahme, #791/#831) und
  die **Partner** (`ObjectSelect`, leer = `RUNTIME_CHOICE`, Beschriftung schlicht
  «Partner», #830). Was ein Bedienelement selbst sagt, sagt man nicht daneben. **Kein
  Betragsfeld** und kein Satz am Vorgang: beides stünde beim Modellieren nicht fest bzw.
  doppelt.
  ►►► **Der dritte Schalter ist weg** (#854): «Zahlung abwarten ↔ nicht abwarten» sagte,
  was die vereinbarte **Zahlungsfrist** ohnehin sagt (null Tage = Vorauszahlung) – zwei
  Aussagen über dieselbe Sache, und die zweite steht in einer **Vorlage**, während die
  Entscheidung dort fällt, wo man das Angebot schreibt. `ModuleDraft.prepaid` ist damit
  ebenfalls entfallen. *Die Regel aus #834 gilt weiter – nur gibt es den Wert nicht mehr,
  an dem sie gelernt wurde.*
- ►►► **Eine Frist ist ein `TermField`** (#854–#856, `fields.tsx`) – die üblichen Werte mit
  **Namen**, der Rest getippt. «Vorauszahlung» ist ein Geschäftsbegriff, «0» eine Ziffer,
  die man erklären muss; *«soll ich bei einer Software einfach 0 eintragen?»* beantwortet
  darum **«Sofort»**. **Kein Schieberegler**: zwischen «Vorauszahlung» und «30 Tage» liegt
  nichts, was man durch Ziehen findet – es ist eine Aufzählung mit freiem Rest, und dafür
  gibt es `Segmented`. Die freie Eingabe beginnt bei `freeMin` (geklemmt beim **Verlassen**,
  nicht beim Tippen – wer eine 3 vor die 0 setzen will, muss die 0 schreiben dürfen), und
  **die Werte kommen vom Server** (`d.payment_terms`/`d.lead_terms`): eine zweite Liste im
  Browser liefe beim ersten neuen Regelwert auseinander. Dasselbe Bauteil im Angebot
  (`Terms`) wie an der Angebotszeile (`QuoteRow`) – zwei Bauarten für dieselbe Frage
  liefen beim nächsten üblichen Wert auseinander. Gemessen in Chromium: 1440 · 1280 · 1024 ·
  834 · 375 · 320 px, **0 px** waagrechter Überlauf (Bug-Form mit einem unteilbaren Wort:
  +140 px bei 375, +195 px bei 320 – die Messung ist nicht blind).
- ►►► **Alles zu EINEM Partner steht auf EINER Zeile** (#833, `.erp-partyrow`). ◄◄◄
  Nummer, Name und die Pflichtangabe «Was ist zu tun?» (#805/#808, benannt über
  `aria-label`, gesagt vom Platzhalter) gehören zusammen – bei mehreren Partnern ist die
  Zeile die **einzige** Stelle, an der die Zugehörigkeit steht. Gemessen: ab 834 px eine
  Zeile, darunter bricht das Feld um (auf einem Telefon geht es nicht anders).
- **Der Löschen-Knopf erscheint beim Hovern** (#832, `.erp-rowaction` in `globals.css`) –
  **und bleibt auf Touch sichtbar** (`@media (hover: none)`): eine Funktion, die nur ein
  Zeiger findet, gibt es am Telefon gar nicht. `:focus-within` deckt die Tastatur ab. Als
  **eine** Regel im Blatt, nicht als `onMouseEnter`-Zustand je Zeile.
- **Und «Was ist zu tun?» ist an der Angebotszeile eine AUSKUNFT** (#836): dort steht das
  Ergebnis, also Symbol + Wert mit Erklärung im Hover – ein Fragezeichen über einer Antwort
  liest sich schräg. Im Editor bleibt die Frage richtig, dort füllt man sie aus.
- ►►► **Ein Wort für beide Richtungen** (`DEAL_PARTY`, `DEAL_TASK`, #802). ◄◄◄ «Kunde» ↔
  «Lieferant» ist dieselbe Rolle; Singular = Plural, damit es keine Beugung gibt, die
  jemand rechnet. Ein Rollen-Wort als Literal in der Oberfläche ist ein Wächter-Fehler.
- **Nummer und Name brechen nicht um** (#838) – der Name wird gekappt; umgebrochen las er
  sich wie eine zweite Angabe. Und **was eine Zahl ist, steht tabellarisch** (#839, `mono`):
  Betrag, Zahlungsfrist und Datum. Die **Objektnummer** bleibt bewusst anders – sie ist eine
  **Kennung**, kein Messwert (#282/#784).
- **Der Kopf trägt Symbol UND Wort** (#815) – als kompakte Marke, nicht als Symbol allein
  auf einer eigenen Reihe. Daneben der **Liefertermin** und, wenn er vorbei ist, «überfällig
  seit …» (#814) – eine Ableitung des Servers, kein Zustand.
- **Abgesagt ist abgesagt** (#811): an einer abgelehnten Zeile stehen weder Preis noch
  Frist. Die Zahlen bleiben in den Daten – der Log ist die Historie.
- **Alle Knöpfe einer Angebotszeile sind gleich hoch** (`ACT_H`, #810): zwei Knöpfe, die
  sich um einen Pixel unterscheiden, lesen sich als Rangfolge.
- **Wen man anfragt, wählt man aus** (#809): die **Zeile ist der Schalter** –
  «Anfragen (2)» war eine Ansage, keine Wahl.
- **Kein Referenz-Feld** (#812): niemand wusste, was hineingehört, und die Rechnungsnummer
  erzeugt der Server selbst. Damit hatte `note` keinen Aufrufer mehr. **Kein Betragsfeld** – beim
  Modellieren steht er nicht fest. **Kein Erklärsatz darunter** (#792): er sagte, was das
  Feld darüber zeigt.
- ►►► **Storniert wird, nicht gelöscht** (#823/#824). Der Papierkorb verspricht, dass die
  Zeile verschwindet – eine Rechnungsnummer ist aber vergeben. Das Zeichen ist darum
  `CircleSlash` (dasselbe, mit dem das Haus überall «storniert» schreibt), und was
  passiert, ist eine **Gegenbuchung**: die Zeile bleibt und heisst «storniert», die neue
  heisst «Storno». Beide Richtungen der Angabe kommen vom Server (`reverses` ·
  `reversed`) – im Browser müsste die zweite über die ganze Liste gesucht werden.
- ►►► **…aber nur eine RECHNUNG** (#842). Eine **Zahlung** ist ein Ereignis der
  Aussenwelt; an ihr steht «Korrigieren», und das ist **kein neues Verb**: es öffnet die
  gewöhnliche Erfassung mit dem **negativen Betrag vorbelegt** (`negate`, als Zeichenkette
  gerechnet – Beträge reisen als String). Ob es ein Erfassungsfehler war oder ob das Geld
  zurückkam, weiss nur ein Mensch: angeboten wird es, angelegt nicht. Die Sperre steht im
  **Dienst**; dies ist die freundliche Hälfte.
- **Ein Nummernfeld gibt es nur, wo die Nummer von aussen kommt** (#840,
  `charge_ref_label` ↔ `payment_ref_label`). `null` heisst «wir nummerieren» – dann gibt es
  **kein Feld**; ein Platzhalter «automatisch» war ein Feld, das nichts aufnimmt. Wie es
  heisst, sagt der Server, nie ein `if` auf die Richtung.
- **Was WIR anbieten, füllen wir vor dem Hinausgehen** (#837, `Terms` + `we_quote`):
  bei einer Einnahme nennen wir den Preis, und ein Angebot ohne Betrag ist keines. Es sind
  **dieselben drei Felder** wie an einer Angebotszeile, nur eine Ebene früher. Und die
  **Abwahl gilt für die Anfrage, die man gerade stellt** (#835) – sie fällt mit dem
  Absenden; sonst blieb der zweite Partner abgewählt, nachdem man den ersten gefragt hatte.
- **Ohne Rechnung kein Zahlungs-Knopf** (#822) – nicht ausgegraut, sondern gar nicht da:
  `can` führt `pay` erst, wenn etwas gefordert ist.
- **Der Modul-Abschluss steht am ENDE der Karte** (#829), hinter der Geld-Zeile. Er stand
  in der Stufe «Auftrag», also mitten in der Kette, und darunter kam noch etwas – ein
  Knopf, der ein Modul abschliesst, sagt so «hier ist Schluss», während sichtbar noch
  etwas folgt. Die Sperre (`d.prepaid`, jetzt aus der vereinbarten Zahlungsfrist) ersetzt
  an genau dieser Stelle den Knopf.
- ►►► **Ein Name steht nie ohne seine Nummer** (#853). ◄◄◄ *«Der Objektname allein darf nie
  ohne die Objektnummer stehen – immer beides in Kombination.»* Gemeldet an der Preiszeile
  des Angebots («1×Blech»), während dieselbe Sache eine Zeile höher **mit** ihrer Nummer
  stand: derselbe Datensatz in zwei Schreibweisen, und die schlechtere ist die, an der man
  ihn nicht wiedererkennt – ein Name ist nicht eindeutig, die Nummer ist die Kennung. Der
  Wächter prüft die **Regel** (jede `*_name`-Anzeige hat ihren `<ObjId>` in Sichtweite),
  nicht die gemeldete Zeile.
- ►►► **Nach dem Bezahlen wird kurz nachgefragt** (#857, `Money`). ◄◄◄ Gebucht wird vom
  **Webhook** – das bleibt so (der Browser des Zahlenden ist keine Quelle). Zwischen dem
  «bezahlt» der Karte und der Meldung liegen ein bis drei Sekunden, und in denen lädt ein
  einzelnes Nachladen zu früh. Nachgefragt wird alle 1.5 s, bis sich `d.paid` ändert,
  höchstens zehnmal: **kein zweiter Kanal** (WebSocket/SSE) für ein Ereignis, das einmal je
  Zahlung eintrifft. Bleibt die Meldung aus, steht die Karte still da, statt sie zu
  behaupten.
- **Und die Bezahlkarte nennt die Rechnung** (#858, `pay-online.tsx`): kassiert wird über
  **eine** Rechnung, nicht über einen Saldo – dieselbe Nummer steht danach beim
  Zahlungsdienst in Beschreibung und Metadaten.
- **Das Partner-Feld hält die frische Wahl nur, bis sie als Zeile dasteht** (#794 → #820).
  Gehalten wird sie, weil sie im Moment des Klicks noch nicht gespeichert ist; sobald der
  Server sie als Angebotszeile zurückgibt, stünde derselbe Partner zweimal da. Eine
  **Ableitung**, kein zweiter Zustand – ein Zurücksetzen an der Antwort wäre die Stelle,
  die der nächste Pfad vergisst.
- **Eine Karte, an der man noch handeln kann, wird nicht gedämpft** (#821,
  `DiagramStep.openActions` ← `ProcessStepResponse.open_actions`). Gemessen war es der Fix
  des letzten Fixes: die Geld-Knöpfe funktionierten an einem abgeschlossenen Auftrag, die
  Karte lag trotzdem bei 55 % Deckkraft da – eine erfundene Sperre, nur in Farbe. **Und
  die Angabe muss durchgereicht werden**: fehlt sie, ist sie `undefined`, `!undefined` ist
  wahr, und die Karte wäre danach **nie** gedämpft.
- **Das Modul-Protokoll erscheint nur, wo es etwas zu berichten hat** (#825,
  `DiagramStep.records`): erfasste Werte · ein Zustandswechsel · eine Verifikation. Kein
  `if module_type` – bei einem Modul ohne physisches Gegenstück blieben sonst Nummer, Name
  und Uhrzeit übrig. Entfernt wird es nirgends; es ist der Nachweis.
- **Die Wörter der Richtung stehen in `lib/modules.DEAL_DIRECTION`** (Symbol, Label,
  Hinweis) – der Editor braucht sie, bevor es einen Vorgang gibt. Mehr trägt sie nicht:
  «Partner» ist ein Wort für beide Richtungen und Singular = Plural (#787/#802).
  `test_frontend_mirrors` hält sie mit `domain/deal.DIRECTIONS` deckungsgleich.
  ►►► **Die Symbole kommen aus `FLOW`** (#845) – Handschlag ↔ Einkaufswagen, eine
  Bildsprache im Haus. Zwei gespiegelte Pfeile waren auf 15 px dasselbe Zeichen mit
  anderer Neigung: man musste hinsehen, statt zu erkennen. Die **Wörter** bleiben
  «Einnahme» ↔ «Ausgabe» – der Einwand aus #831 galt ihnen, und ein Symbol behauptet
  keinen Namen; es zeigt die häufigste Gestalt der Sache.
- **«Partner» steht im PLATZHALTER, nicht darüber** (#843): die Beschriftung kostete eine
  Zeile für ein Wort, und darunter erklärte «Nummer oder Name» dasselbe Feld ein zweites
  Mal. Zusammengelegt sagt der Platzhalter beides. Im **Scan-Vollbild** bleibt die Sorte
  eine Beschriftung (`scanLabel`) – dort liegt Text auf einem Foto.
- **Der Löschen-Knopf einer Zeile sieht aus wie der am Modul** (#844, `RowDelete`): ein
  26-px-Quadrat, kein Rahmen, keine Fläche, allein die Warnfarbe – nicht ein
  `erp-actbtn`-Kasten mitten in einer Zeile aus Nummer, Name und Eingabefeld. **Ob er sich
  einblendet, sagt der Aufrufer** (`reveal`), nicht das Bauteil: der Erfassungspunkt hatte
  ihn immer sichtbar, und das bleibt so.
- ►►► **Der Steuersatz steht NICHT im Editor** (Testnotiz #851). ◄◄◄ Er stand dort als
  «Vorbelegung jeder neuen Position» (`ModuleDraft.vatRate`) und war damit eine
  Eigenschaft des **Moduls** – eine Vorlage, die für jeden künftigen Auftrag denselben
  Satz behauptet, obwohl er an der **Sache** hängt. Gefragt wird er je Position an der
  Ausführungsstelle (`Goods`), und der Katalog reist mit dem **Vorgang**
  (`DealEmbed.vat_rates`). Mit ihm sind `DEFAULT_VAT`, `VAT_LABEL`, der
  `ModuleCatalog.vat_rates`-Weg und die ganze `vatRates`-Prop-Kette entfallen: ein
  Spiegel ohne Leser ist kein Spiegel, sondern eine zweite Wahrheit, die niemand
  vergleicht.
- ►►► **Die Währung steht im KOPF, nicht an jeder Zahl** (`Currency`). ◄◄◄ Ein Beleg hat
  *eine* (zwei wären zwei Belege) – fünfzehnmal «CHF» neben fünfzehn Beträgen wäre Fläche
  statt Struktur. **Ob man sie noch wählen darf, sagt `can`**, nie die Stufe; ist sie
  gebunden, **verschwindet sie nicht**, sondern wird zur Auskunft mit dem Grund im Hover.
  Genannt wird sie beim **Total** und beim **offenen Betrag** – den Zahlen, die
  abgeschrieben und überwiesen werden. Ein `<select>` ist hier richtig: Währungen sind
  eine endliche Aufzählung, keine Referenz auf einen Datensatz.
- ►►► **Die Nachkommastellen kommen von der Währung**, nie aus einer festen 2. ◄◄◄
  `formatAmount(v, decimals)` mit `d.currency_decimals`; **JPY** hat null, **KWD** drei.
  Auch die **Vorschau** (`Sums`) rechnet damit – sonst zeigte sie eine andere Zahl als
  die, die der Dienst danach bucht, und hätte genau ihren einen Zweck verfehlt.
- **Das Leistungsdatum ist vorbelegt** (#852, `d.service_date`) – aus dem Prozess, nicht
  aus dem Rechnungsdatum. Überschreibbar: ein Mensch weiss von Teilleistungen.
- **Ohne Verifikation kein Scan-Tor** (`step.verifies`, aus `Module.requires_verification`):
  ein Modul, das keine Stücke bewegt, wird mit **einem** Knopf bestätigt. Die
  Ausführungsstelle fragt die **Eigenschaft**, nie den Modultyp – sonst fehlt beim nächsten
  Modul derselben Art die Zeile.
- ►►► **Der Preis steht an SEINER Position, und der Steuersatz daneben** (MWSTG Art. 26).
  ◄◄◄ Sie hängen an der **Sache**: sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen
  auf demselben Papier. Wo **wir** den Preis nennen (`we_quote`), fragt `Goods` je Zeile
  *Preis netto* und *Satz*, und der Angebotsbetrag ist ihre **Brutto-Summe** – ein
  Betragsfeld daneben ist entfallen, es wäre nicht nur die zweite Aussage über dieselbe
  Sache, sondern eine, die der Dienst abweist. Der **Katalog kommt vom Server**
  (`d.vat_rates`); eine zweite Liste im Browser liefe beim ersten Satzwechsel auseinander.
  Ein `<select>` ist hier richtig – die Sätze sind eine endliche **Aufzählung**, keine
  Referenz auf einen Datensatz.
- **Gerechnet wird nichts, ausser als Vorschau** (`Sums`): dieselbe Regel wie im Dienst –
  **je Satz auf der Summe**, nie je Position aufsummiert. Gebucht wird dort.
- **Der bestätigte Auftrag ist ein BELEG, kein Feldraster** (#847). Vier gleich laute
  Lesefelder in einem `auto-fit`-Raster zerfielen je nach Breite in eine, zwei oder vier
  Spalten, und der **Betrag** stand als drittes Kästchen von links. Jetzt: **wer** (eine
  Zeile) · **was es kostet** (rechtsbündig Netto · Steuer je Satz · Total unter **einer**
  Haarlinie über beide Spalten – an die zwei Zellen geschrieben hätte sie ein Loch in der
  Mitte) · **zu welchen Bedingungen** (klein daneben). Die **Positionen stehen nicht noch
  einmal darin**: sie stehen oben in `Goods`, seit die Zeile ihren Preis trägt.
- **Die Steuer einer gebuchten Zeile steht im HOVER** (`taxTip`): bei zwei Sätzen wären es
  fünf zusätzliche Zahlen neben Betrag, Referenz und Datum, und bei 320 px ist dort kein
  Platz. Eine **Zahlung** trägt keinen Hinweis – Geld trägt keine Steuer, es begleicht sie.
- **Was der Partner ändert, kommt an** (#846). Die drei Felder einer Angebotszeile sind
  lokal, damit man tippen kann – aber ein `useState`-Startwert wird genau **einmal**
  gelesen: ändert die Gegenpartei danach ihre Zahlungsfrist, zeigte das Feld weiter den
  alten Wert, und wer etwas anderes korrigierte, **schrieb die alte Frist zurück**.
  Nachgezogen wird beim **Wechsel des Server-Werts** (`[remote]`), nicht bei jedem
  Rendern – dieselbe Bauart wie `defaultOpen` (#727). Und **beide** Fristen stehen in der
  Zeile, jede mit ihrem Wort im Hover; zwei nackte Tageszahlen wären nicht unterscheidbar.
- **Kein Erklärsatz über den fehlenden Abschluss-Knopf** (#849): die Sperre steht als
  Auskunft im **Kopf**, die Zahlen in der **Geld-Zeile**, und dass der Knopf fehlt, sieht
  man. Ein Hinweis, der nichts Neues sagt, liest sich wie eine Fehlermeldung.
- **Das Mikro-Label ist ein Bauteil** (`fields.MICRO_LABEL`) – es stand als Inline-Stil an
  jeder Stelle, mit leicht verschiedenen Werten (11 ↔ 11.5 px, 600 ↔ 700, .05 ↔ .07 em).
  Genau die Form, in der eine Gestaltungsregel auseinanderläuft, ohne dass es auffällt.
- ►►► **Keine Reiter — alles untereinander** (Testnotiz #863). ◄◄◄ *«Ich mag diese
  Reiter-Ansicht nicht, ich möchte alles auf einmal sehen untereinander.»* Und die Meldung
  hat recht, weil der Vorgang **einer** ist: das Angebot erklärt die Zusage, die Zusage
  erklärt die Rechnung. `open`/`setOpen`/`shows` sind entfallen; die Leiste blieb eine
  Runde lang als **Übersicht** ohne Handler und ist mit #868 ebenfalls gegangen – der
  Verlauf steht jetzt an den Abschnitten. *Die Sorge aus der Vorrunde («bei vier Buchungen
  zwei Bildschirme hoch») bleibt richtig – sie ist eine Frage der **Dichte**, nicht des
  Versteckens, und die drei Antworten darauf stehen unten.*
- ►►► **EINE Positionstabelle** (#862). ◄◄◄ *«Der Positions-Abschnitt ist doppelt.»* – Er
  war es: `Goods` sagte, worum es geht, und der Angebotsblock zeigte dieselben Zeilen noch einmal
  mit Eingabefeldern (und **weniger**: kein Chevron, keine Spezifikation). Jetzt ist es
  eine Tabelle, die tippen lässt, solange man anbieten darf. **Der Entwurf wohnt darum in
  `DealWork`** – beide sehen ihn – und wird **je Artikel** gehalten (`Record<string,
  PriceRow>`), nicht als Liste: eine Liste müsste nachgezogen werden, sobald der Prozess
  eine Position dazustellt, und ein Nachziehen löscht getippte Preise.
- ►►► **Die Zahlungen stehen eingerückt unter ihrer Rechnung** (#861). ◄◄◄ Sie standen
  flach und chronologisch da, die Zugehörigkeit war ein «auf 100000801-1» am Zeilenende.
  Eingerückt sagt es die **Form** (dieselbe Geste wie die Stückliste unter ihrer
  Einzelinstanz, #724) – der Text daneben ist damit entfallen, und in einer engen Zeile
  ist es genau der Platz, den das Datum braucht. **Was zu keiner Rechnung gehört,
  verschwindet nicht**: eine Gruppe «Nicht zugeordnet» am Ende.
- ►►► **Die Geld-Handlungen stehen AN der Rechnung** (#859, `EntryRow`). ◄◄◄ *«Wie kann
  ich bestimmen, welche Rechnung ich bezahle?»* – Ein Knopf **an** der Zeile beantwortet
  die Frage, indem er sie nicht stellt: Zahlung erfassen · Jetzt bezahlen · Überweisen ·
  Stornieren/Gutschrift. Unten bleibt, was dem **Vorgang** gilt (die nächste Forderung,
  die Gegenhandlung). Das Auswahlfeld «welche Rechnung?» im Formular ist damit weg.
- **Storno oder Gutschrift sagt der Server** (`e.reverse_word`, #860): was bezahlt ist,
  nimmt man nicht zurück, man schreibt es gut. Und **erstattet wird auf dem Weg, auf dem
  gezahlt wurde** – `e.refundable` (nur eine Karte) gegen «Korrigieren» daneben, das die
  gewöhnliche Erfassung mit dem negativen Betrag öffnet.
- **Überweisen ist eine AUSKUNFT** (#865, `Transfer`): Bankverbindung, RF-Referenz und die
  **QR-Rechnung** als fertiges SVG vom Server – erst auf Klick. Im Browser gebaut wären es
  einunddreissig Zeilen ein zweites Mal, und eine verrutschte sieht man einem QR nicht an.
  Wo es keinen Code geben kann, steht der **Grund** statt einer leeren Fläche.
- **Wie bezahlt wurde, ist ein `Segmented`** (`d.methods`) – zwei Werte sind ein Schieber,
  keine Auswahlliste; die **Karte** steht nicht darin (sie kommt über den Webhook).
- ►►► **Die Währung steht im ANGEBOT** (#864). ◄◄◄ Sie ist eine **Entscheidung** über das,
  was gleich hinausgeht – ein Auswahlfeld zwischen lauter Auskünften (der Meta-Zeile) liest
  sich wie eine. Sie hängt an **`can`**, nicht an einem zweiten Feld (`currency_locked` ist
  entfallen); was feststeht, steht als Wert da (`Fixed`), nicht als gesperrtes Feld (#749).
  **Und ihre Beschriftung trägt den Code schon** (#869): `currency.label` liefert «CHF ·
  Schweizer Franken» – der Code davor ergab «CHF · CHF · Schweizer Franken». Das Feld ist
  so breit, dass der Name lesbar bleibt; ein natives Auswahlfeld zeigt geschlossen genau
  den Text der gewählten Zeile.
- ►►► **Einen «Anteil» gibt es nicht** (#867). ◄◄◄ Er stand daneben – eine Prozentzahl, die
  sagte, welchen Teil der Positionen dieser Vorgang abrechnet. *«Ich checke diese Funktion
  nicht»*, und gebraucht wird sie nicht: **wer den Preis nennt, nennt ihn je Position**,
  also trägt ein zweites Modul schlicht seine eigenen Positionspreise.
- ►►► **Jeder Knopf der Karte ist ein `ActionButton`** (#877–#896). ◄◄◄ *«Ein Icon und
  beim Hover der Text dazu»* – siebenmal gemeldet, also die Form eines Knopfes im Haus und
  nicht eine Eigenschaft dieser Zeile. Der **Name** steht zuerst in der Blase, ein Grund
  dahinter; was dort stand, waren ganze Sätze statt des Wortes, nach dem gefragt war.
- **Eine WAHL behält ihr Wort** (#877/#878): mit Symbol stehen die Fristen auf ihrer
  **Inhaltsbreite** statt jede auf einem Drittel der Spalte – eingeklappt wären es drei
  anonyme Quadrate, und man müsste auf jedes zeigen, um zu lesen, worunter man wählt. Ein
  **Knopf** ist eine Handlung und hat keine Antwort, die dastehen müsste; eine Frist hat
  eine. Das Symbol folgt aus der **Zahl** (0 = ohne Frist · n = Termin · frei = Eingabe).
- **Die Währung steht bei den BETRÄGEN** (#876/#881): an jeder Zahl, die man abschreibt
  (Angebotszeile · Vorschau · Total). Die Beschriftung über dem Auswahlfeld ist entfallen –
  es zeigt geschlossen «CHF · Schweizer Franken» –, und ab der Zusage steht dort **gar
  nichts** mehr. *Löst #864 ab: die Auskunft gibt es weiterhin, sie steht nur dort, wo die
  Frage entsteht.*
- **«0 Tage» heisst «Vorauszahlung»** (#885, `termText`) – gelesen aus **derselben Liste**,
  aus der man sie wählt; was keine Liste kennt, ist die freie Eingabe («x Tage»).
- **Aus einer Frist folgt ein Datum** (#884, `TermField preview`): die Eingabe bleibt «in x
  Tagen», das Datum rechnet das System. Vorbelegt ist der Wert aus dem Angebot, änderbar
  bleibt er – nachverhandelt wird auch am Telefon.
- **EIN Datum je Geld-Zeile** (#890, `dateText`): «fällig in 30 Tagen» bzw. «überfällig
  seit 17 Tagen», beide Daten im Hover. Ohne Fälligkeit bleibt das Buchungsdatum.
- **Die Offerte wird gespeichert, nicht abgeschickt** (#879, `useAutosave`) – und erst,
  wenn die Zeile **vollständig** ist: der Dienst weist eine halbe Offerte ab, und ein
  Auto-Save beim ersten Tastendruck liefe gegen eine Meldung, die nur sagt, dass man noch
  nicht fertig ist.
- **«Zahlung erfassen» verschwindet an einer bezahlten Rechnung** (#894) – überzahlt bleibt
  er, dann steht die Rückgabe an. Eine Ableitung aus derselben Zahl, die den Punkt daneben
  färbt.
- **Der Hover erklärt, statt zu wiederholen** (#882): «Was ist zu tun? 123456» sagte die
  Frage plus den Wert, der daneben steht. Eine Blase, die den sichtbaren Text wiederholt,
  ist die Stelle, an der man aufhört, Blasen zu lesen.
- **Kleineres:** «Buchen» heisst, was es bucht (#887, vom Server); die Beschriftung
  «Partner» am bestätigten Auftrag ist entfallen (#883); der **«Schliessen»-Knopf** im
  Überweisen-Panel ist gelöscht (#889 – der Knopf, der es geöffnet hat, schliesst es);
  das **Leistungsdatum** ist längst automatisch, und was fehlte, war der Satz, der das
  sagt (#886 – Pflichtangabe nach MWSTG Art. 26 Bst. c, aus dem Prozess vorbelegt).
- ►►► **Der Status steht an der RECHNUNG, nicht als Leiste darüber** (#875). ◄◄◄ `MoneyBar`
  war richtig, solange ein Vorgang mehrere Rechnungen tragen konnte; seit #866 gibt es je
  Modul **eine** – die Leiste fasste damit eine Zeile zusammen, die direkt darunter stand.
  Übrig bleibt **Punkt + Wort** an der Zeile (*Bezahlt · Offen · Überfällig · Überzahlt*),
  **abgeleitet** aus `e.open`/`e.overdue`. Und die **Beleg-Nummer wird dabei nicht bis zur
  Unkenntlichkeit gekappt** («100…»): sie schrumpft nur bis `REF_MIN`, darunter bricht die
  Zeile um – dieselbe Lehre wie bei der Positionszeile (#847).
- ►►► **Zwei Knöpfe sind gefallen** (#874). ◄◄◄ «Gutschrift erfassen» am Vorgang trug
  dasselbe Wort wie die Gutschrift **an der Rechnung** und tat etwas anderes (eine
  freistehende negative Forderung ohne Bezug, die in der Liste als zweite Rechnung
  erschien); «Zahlung erfassen» am Vorgang war **unerreichbar** (`can` führt `pay` erst mit
  einer gebuchten Forderung). **Und «Auftrag stornieren» ist keine Buchung**: es stand
  zwischen den beiden und steht jetzt am **Ende der Karte**, neben dem Abschluss – die eine
  bringt den Vorgang ans Ziel, die andere nimmt ihn zurück.

### Der Beleg ist vollständig (Arbeitsauftrag, #902–#908)
- ►►► **Die Rollen erklären sich selbst** (#903). ◄◄◄ «Leistungserbringer» ↔
  «Leistungsempfänger» sind die Begriffe des MWSTG – und sperrig; der erklärende Satz kommt
  **vom Server** (`DealSide.hint`) und steht im Hover. Ein Rollen-Wort als Literal in der
  Oberfläche ist ein Wächter-Fehler.
- **Die Nummer ist eine eigene Zeile mit «Nr.»** (#904, `PARTY_NUMBER_LABEL`):
  «Objektnummer» ist ein Systembegriff, «Benutzernummer» falsch, sobald die Partei ein
  Unternehmen ist – und der Block darüber sagt bereits, **wessen** Nummer es ist. Klickbar
  bleibt sie.
- **Der Belegkopf trägt «z. H.», Kontaktweg und die UID beider Seiten.** Was fehlt, steht
  als kleines rotes «fehlt» da (`Missing`) – eine erfundene Zeile wäre auf einem Beleg
  schlimmer als eine leere.
- ►►► **Der offene Betrag steht NICHT im Kopf** (#902). ◄◄◄ *«Angebot · Offen 0.00 CHF»* –
  auf einem Angebot ist nichts gefordert, also ist er null, und «Offen 0.00» liest sich wie
  «bezahlt». Er steht **genau einmal**, an der **Rechnung** (Punkt + Wort, #875). *Die
  **Belegart** bleibt – sie ist die eine Angabe, die ein Papier zu einem Beleg macht.*
- ►►► **Was fehlt, sagt das Modul** (`Gaps` ← `DealEmbed.gaps`). ◄◄◄ Dieselbe Anatomie wie
  `StepNeed`: Zeile · Nummer · Klartext, und der Klick führt zum Datensatz – eine Meldung
  ohne Adresse ist eine Sackgasse mit Ausrufezeichen. Gerechnet wird hier nichts; der Knopf
  fehlt ohnehin (`can`), diese Zeilen sagen **warum**.
- **Der Pflichtsatz steht auf dem Beleg, nicht im Hover** (`Totals`, `vat_split[].note`):
  «Steuerfreie Ausfuhrlieferung» ↔ «Steuerschuldnerschaft des Leistungsempfängers» sind zwei
  **verschiedene** Rechtsgründe, die beide 0 % ergeben – und auf einem Papier gibt es keinen
  Hover. **Gewählt wird der Katalog-Schlüssel, nicht die Zahl** (`value={r.key}`): «0.00»
  ist seither mehrdeutig, und `Number('normal')` wäre `NaN` – die Vorschau löst ihn darum
  über den Katalog auf (`rates.find(v => v.key === key)`).
- ►►► **Die Währung steht bei den PREISEN** (#906). ◄◄◄ *«Informationen dort anpassbar
  machen, wo man sie sucht»* – über der Preisspalte sagt schon ihre **Position**, dass sie
  für **alle** Positionen gilt. Sie hängt an **`can`**, nicht daran, ob wir hier Preise
  tippen: bei einer **Ausgabe** nennt die Gegenpartei den Preis, und die Währung ist
  trotzdem unsere Entscheidung. *Löst #864 ab – der Ort ist besser, die Regel dieselbe.*
- ►►► **Die Fristen stehen EINMAL** (#907), und die Auflösung ist die bestehende Regel:
  `we_quote` (← `quoted_by`) sagt, **wer den Preis nennt** – und wer den Preis nennt, nennt
  auch die Fristen. Einnahme → im Beleg (`Terms`), die Zeile des Partners zeigt sie nur an;
  Ausgabe → an **seiner** Zeile (`QuoteRow`), der Beleg liest sie. Kein `if` auf die
  Richtung. **Und steht es fest, liest es sich wie die Fusszeile eines Belegs** (`Fixed`):
  *was man sieht, ist, was gedruckt wird.*
- **Die Lieferbedingung ist ein Katalog mit Erklärung** (`Delivery`, `d.incoterms`): jede
  Zeile trägt sie als `title`, und die **gewählte** steht darunter als Satz – ein Hover
  findet nur, wer weiss, dass es ihn gibt, und das ist genau die Frage, die diese Klauseln
  auslösen. **Der benannte Ort erscheint mit der Klausel** und geht mit ihr; der Satz für
  den Beleg («FCA Rorschach (Incoterms 2020)») kommt vom Server.
- **Wer den Beleg stellt, ist eine Wahl** (#905, `Issuer`): ein `ActionButton` mit Stift am
  Block des Leistungserbringers, dahinter dasselbe `ObjectSelect` wie jede Referenz im Haus.
  Die Liste reist mit dem Vorgang (`d.issuers`) – ein eigener Such-Endpunkt für eine
  Handvoll Gesellschaften wäre ein Weg zu viel. **Ob es die Wahl noch gibt, sagt `can`**:
  ab der Zusage fehlt das Symbol, statt ausgegraut dazustehen.
- **Am Benutzer ist die Gesellschaft eine ANSTELLUNGS-Angabe** (`user-detail.CompanyPick`) –
  darum im ERP und nicht im Profil: wer für wen arbeitet, entscheidet nicht die Person
  selbst. Ohne sie weist der Dienst die Rollenänderung ab (`people.assert_employment`); dies
  ist die freundliche Hälfte.
- **Zolltarifnummer und Ursprungsland stehen am ARTIKEL** (`article-detail`, zwei Zeilen in
  `OPTIONAL_FIELDS`) und reisen über die Spezifikation auf jeden Beleg – der Geldvorgang
  nennt sie nirgends beim Namen, und genau das ist der Beleg für den richtigen Ort. Das
  Ursprungsland wird **grossgeschrieben** gesendet: «ch» und «CH» wären zwei Länder.



---

## Anhang (Oktober 2026): PROCESS_CORE §9.12–§9.14c im Wortlaut

> Aus `PROCESS_CORE.md` (develop @ 8dcd098, Zeilen 1797–2774) hierher verschoben, unverändert
> (Cleanup Paket 6, D-25). Der Abschnitt beschrieb das gelöschte `deal`-Modul als «gebaut»;
> in `PROCESS_CORE.md` steht an seiner Stelle eine Kurzfassung der Entscheidungen, die im
> Beleg (§9.15) weiter gelten. Die Verweise «§9.12», «§9.13», «§9.14» in älteren Texten
> meinen die Abschnitte unten.

### 9.12 Das Modul «Zahlung» — Geld mit einer zweiten Partei

> **Status: gebaut — und heute die EINZIGE Maschine für Geld mit einer zweiten Partei.**
> Es entstand bewusst **neben** «Beschaffen»/«Verkauf», ohne eine Zeile mit ihnen zu
> teilen: weder Tabelle noch Dienst noch Vokabel. Genau das hat sich ausgezahlt — die
> beiden Module sind inzwischen **ersatzlos gelöscht** (§9.9a), und hier musste dafür
> nichts angefasst werden. Ein Quelltext-Wächter hält die Trennung weiterhin.

#### Die Frage, aus der es entstand

Einkauf und Verkauf waren zwei Module, und daneben standen Fälle, die in keines von beiden
passten: eine Spedition, die man beauftragt (ein Einkauf **im** Bewegen-Modul), eine
Leistung ohne Artikel, eine Vorauszahlung. Jeder Fall bekam ein eigenes Stück Mechanik —
und die Mechanik wuchs schneller als die Fälle.

**Der kleinste gemeinsame Nenner ist nicht die Ware, sondern das Geld.** Ein Vorgang hat
genau eine Richtung — es kommt herein oder es geht hinaus —, und alles Weitere ist in
beiden dieselbe Maschine: jemand nennt einen Preis, beide sagen zu, es wird gefordert, es
wird gezahlt.

#### Die eine Regel, die es robust macht

> **Dieses Modul bewegt keine Stücke.**

Ein **Durchläufer** (`Im Prozess` → `Im Prozess`), `terminal = False`, `moves = False`,
kein Ortswechsel, kein neuer Status, `buys = None`. Es hält die Stücke auf, bis die zweite
Partei ihren Teil getan hat, und lässt sie dann weiterlaufen.

Daraus folgt die Robustheit **konstruktiv statt geprüft**: keine andere Regel im System
muss von ihm wissen — keine Kettenregel, keine Statusliste, keine Bestandsansicht, keine
Zeile in der Prozess-Engine. Was physisch geschieht, sagen die Nachbarn: kommissioniert
und ausgeliefert wird mit «Bewegen», ausgesondert mit «Aussondern».

*Ein Verkauf besteht damit aus zwei Modulen statt aus einem, und das ist der Preis. Er ist
der richtige: sobald dieses Modul auch Ware bewegte, bräuchte es für jede Kombination aus
Geld und Ware wieder einen eigenen Fall — genau die Lage, aus der es entstanden ist.*

#### Zwei Angaben beim Definieren (`domain/modules.Zahlung`)

| | |
|---|---|
| `direction` | **Geld kommt** (`in`) ↔ **Geld geht** (`out`). Daraus folgt jedes Wort. |
| `parties` | Die **zugelassenen Partner**. **Leer heisst frei** — dann wird beim Ausführen gesucht. |

►►► **Es waren einmal drei — und der dritte war eine zweite Aussage** (Testnotiz #854).
◄◄◄

`prepaid` («Weiter, wenn zugesagt ↔ bezahlt») stand hier als Schalter und sagte, was die
vereinbarte **Zahlungsfrist** ohnehin sagt: *zahlbar in null Tagen ab Zusage* **ist** die
Vorauszahlung. Zwei Stellen, die dieselbe Sache behaupten, geraten beim ersten Vorgang in
Widerspruch, in dem jemand nur eine davon setzt — «Klinsch» war das Wort dafür.

**Und der Ort war ebenfalls falsch.** Eine Definition ist eine **Vorlage** für jeden
künftigen Auftrag; ob vorausbezahlt wird, entscheidet sich aber dort, wo man das Angebot
schreibt. Die Frist steht darum an der **Angebotszeile** (`quotes[].payment_days`), und
`prepaid` ist ihre Lesart (`dm.prepaid(due_days)`, `Balance.settled` unverändert).

Und **je zugelassenem Partner eine Pflichtangabe**: *«Was ist zu tun?»* — seine
Artikelnummer, sein Shop-Link oder ein Satz.

**Keine Menge** (sie ist die Zahl der Einzelinstanzen davor), **kein Artikel** (den tragen
die Stücke), **kein Termin** (ableitbar), **kein Betrag** (beim Modellieren steht er nicht
fest — ein hier getippter wäre bei der zweiten Ausführung falsch, und zwar stillschweigend)
und **kein Steuersatz** (Testnotiz #851 — siehe unten).

►►► **Ein Pflichtfeld statt zweier optionaler.** ◄◄◄

Es gab einmal beides: einen **freiwilligen** Satz am Vorgang («Was ist daran zu tun?») und
daneben eine **Bestellangabe** je Partner — die nur beim Einkauf existierte. Das ist
dieselbe Aussage zweimal, einmal ohne Adressaten.

*«Ich bin sowieso kein Fan von optionalen Feldern»* — und das ist die richtige Haltung: ein
Feld, das man ausfüllen **kann**, wird an der Hälfte der Stellen leer gelassen, und dann
sagt seine Leere nichts. Übrig bleibt **eine** Angabe, **Pflicht**, in **beiden**
Richtungen, und sie steht **bei dem Partner, den sie betrifft** — denn *bei ihm* bestellt
man anders als bei dem anderen (derselbe Lieferant führt je Teil eine andere Nummer).

**Der Entwurf beginnt als Einnahme** (#791) — die Frage bleibt, sie startet nur bei der
häufigeren Antwort; ein Schalter, der auf nichts steht, ist keine Frage, sondern eine
Lücke, die der Server still mit `out` füllt.

#### Ein Wort statt zweier

«Kunde» ↔ «Lieferant», «Einnahme» ↔ «Ausgabe», «Bestellangabe» nur beim Einkauf: das
waren drei Verzweigungen für Dinge, die auf beiden Seiten dasselbe sind. Jede Aufrufstelle
musste sich das richtige Wort holen — und die falsche Wahl war jederzeit möglich.

| | |
|---|---|
| **Partner** (`deal.PARTY`) | der andere im Geschäft. **Singular = Plural** — damit ist «Kundeen» (#787) *strukturell* erledigt statt durch einen zweiten gepflegten Wert. |
| **Verkauf** ↔ **Einkauf** | dieselben Wörter und dieselben Symbole wie beim Handel (`FLOW`). Ein Haus, eine Sprache. |
| **«Was ist zu tun?»** (`deal.TASK`) | die Angabe am Partner — in beiden Richtungen. |

Was für beide Richtungen gleich lautet, gehört **nicht** in eine Tabelle je Richtung: dort
wäre es ein Wert, den man vergleichen und falsch auswählen kann. `Direction` trägt nur
noch, was wirklich verschieden ist — die Stufen-Wörter, das Verb der Anfrage und die
beiden Geld-Wörter.

#### Worum es geht — ABGELEITET, nie getippt

Je Artikel, dessen Einzelinstanzen im Auftrag stehen, **eine Zeile** mit Menge, Nummer und
Namen; **mehrere sind der Normalfall** — ein Vorgang mit zwei Positionen, wie im echten
Leben. Es braucht dafür keine Regel, nur eine Gruppierung (`deal.process_lines`).

Die **Spezifikation reist mit** (`services/article_fields`) — sie beschreibt die Sache,
damit die Gegenpartei weiss, worum es geht, und sie wird **nicht ausgewählt**: eine
Spezifikation, die je nach Empfänger anders lautet, ist keine. Sie steht **erst auf
Klick**: im Normalfall interessiert die Zeile, nicht das Datenblatt.

Mit der **Zusage frieren die Zeilen ein** (`deals.agreed_lines`) — ab dort ist eine zweite
Partei gebunden, und was sie zugesagt hat, darf sich nicht mehr ändern, weil jemand ein
Stück nachschiebt. Davor gibt es sie gar nicht: sie **sind** der Prozess und ziehen von
selbst nach.

#### Die Steuer — der Satz gehört der POSITION, nicht dem Beleg

> **MWSTG Art. 26** verlangt auf einer Rechnung Steuersatz **und** Steuerbetrag. Bis hier
> trug der Vorgang **eine** Zahl (`deals.amount`), und `agreed_lines` hielt Artikel und
> Menge — **keinen Preis**. Damit fehlte genau das, was einen Beleg zu einem Beleg macht.
>
> **Das Modul muss es selbst können.** Einen Verkaufsbereich am Artikel gibt es nicht, und
> ein Modul, das auf eine Angabe von aussen wartet, kann seine eigene Rechnung nicht
> stellen. Kommt sie später von dort, belegt **sie** vor — vorbelegen, nie erzwingen.

**Die eine Regel, aus der alles folgt: ein Positionspreis ist NETTO, jeder Betrag ist
BRUTTO.** Damit bleibt die ganze bestehende Rechnung unangetastet — *offen · bezahlt ·
uncharged* (`domain/deal.balance`) rechnen weiter mit derselben Zahl, und **keine** der
drei Achsen (Ware · Forderung · Geld) muss von der Steuer wissen. Netto und Steuer sind
**Ableitungen**, null Spalten.

**Der Satz hängt an der Sache, nicht am Papier.** Sechs Wellen zu 8.1 % und eine Ausfuhr
zu 0 % stehen auf demselben Beleg; ein Satz je Beleg wäre bei jedem gemischten Geschäft
falsch — und zwar stillschweigend, weil die Summe trotzdem aufgeht. Er steht darum an der
**Position** (`DealLine.vat`).

►►► **Und am MODUL steht er gar nicht** (Testnotiz #851). ◄◄◄

Er stand dort einmal als «Vorgabe jeder neuen Position» (`Zahlung.VAT_RATE`) — und war
damit eine Eigenschaft des **Moduls**: eine Vorlage, die für jeden künftigen Auftrag
denselben Satz behauptet, obwohl er an der **Sache** hängt und die erst feststeht, wenn
ein Auftrag läuft. Ein Vorgabewert, der bei der Hälfte der Aufträge überschrieben werden
muss, ist kein Komfort, sondern die Zahl, die stehenbleibt, wenn es niemand tut.

Gefragt wird er darum **je Position an der Ausführungsstelle**; vorbelegt ist der
Normalsatz (`deal.DEFAULT_VAT`), und der Katalog reist mit dem Vorgang
(`DealEmbed.vat_rates`) statt über den Modul-Katalog — ein zweiter Weg zur selben Liste
wäre die Stelle, die beim nächsten Satzwechsel jemand vergisst. Ein Wert, der trotzdem
in der Konfiguration ankommt, wird **verworfen**.

**Gerundet wird je Satz auf der SUMME** (`vat_split`), nie je Position aufsummiert:

```
3 × 5.00 zu 8.1 %   je Position gerundet:  3 × 0.41 = 1.23
                    je Satz auf der Summe: 15.00 × 8.1 % = 1.215 → 1.22
```

Bei zwölf Zeilen weicht es entsprechend weiter ab, und eine MWST-Abrechnung kennt keine
Rappen-Toleranz.

**Eine Teilrechnung verteilt sich anteilig über alle Sätze** (`split_for`). Eine Anzahlung
ist zum Satz der zugrunde liegenden Leistung zu versteuern; dem höchsten Satz zugeschlagen
wäre sie zu viel Steuer, dem niedrigsten zu wenig. **Der letzte Anteil bekommt den Rest** —
sonst ist die Summe der Zeilen nicht der Betrag der Rechnung, und der Beleg widerspricht
sich selbst. Wo es **keine** Positionen gibt (eine *Ausgabe*: die Steuer steht auf **ihrer**
Rechnung), nennt der Erfassende den Satz, und `split_at` rechnet das Netto zurück.

**Wer den Preis nennt, entscheidet die Form** — dieselbe Angabe wie überall
(`Direction.quoted_by`, §9.12 «Ein Vorgang hat zwei Parteien»):

===============  ==========================================================
**Einnahme**     wir nennen ihn **als Positionen** (dort hängt der Satz);
                 der Angebotsbetrag ist ihre **Brutto-Summe**
**Ausgabe**      die Gegenpartei nennt eine **Summe**; den Satz erfassen wir
                 mit ihrer Rechnung
===============  ==========================================================

Ein Betragsfeld neben gepreisten Positionen gibt es darum nicht: es wäre nicht nur die
zweite Aussage über dieselbe Sache, sondern eine, die der Dienst abweist.

**Die Menge kommt aus dem PROZESS**, nie aus der Nutzlast (`deal._priced`): sie ist die
Zahl der Einzelinstanzen, die vor dem Modul stehen. Eine getippte Menge daneben gewinnt
auch dann, wenn sie falsch ist.

**Der gebuchte Beleg SPEICHERT seine Steuer** (`deal_entries.vat`, `service_date`), statt
sie nachzurechnen: ein Beleg behält, was auf ihm stand — auch wenn der Vorgang später
andere Positionen trägt oder der Gesetzgeber den Satz ändert. Nachgerechnet wäre die
Vergangenheit eine Funktion der Gegenwart, und eine Abrechnung über ein abgeschlossenes
Quartal ergäbe beim zweiten Lauf andere Zahlen. Der **Storno spiegelt sie** mit negativem
Vorzeichen — sonst nähme er den Betrag zurück und die Steuer nicht.

**Bewusst nicht gebaut und benannt:** Rabatt (er ist eine Position mit negativem Preis, und
ob er das bleiben soll, ist eine fachliche Frage), QR-Rechnung und PDF. Der Beleg lebt
**online**; ein Papierformat ist eine Darstellung, kein Datenmodell.

#### Das Leistungsdatum kommt aus dem PROZESS

**MWSTG Art. 26 Bst. c** verlangt es auf der Rechnung, und bei einem Satzwechsel
entscheidet es, welcher Satz gilt. Das **Rechnungsdatum ist es nicht**: eine Rechnung, die
zwei Wochen später geschrieben wird, verschöbe damit die Steuerperiode.

Der Auftrag weiss es (`deal.service_day`): es ist der Tag, an dem die Stücke dieses Modul
**erreicht** haben — gelesen wird darum das `step`-Ereignis des **Vorgängers**, nicht das
eigene (ein `step` an *diesem* Modul heisst «hier fertig»). Steht das Modul am Anfang, ist
die Ankunft der **Start** des Auftrags.

**Abgeleitet, nicht gespeichert** — eine Spalte daneben wäre die zweite Wahrheit. Und
**vorbelegt, nicht erzwungen**: ein Mensch weiss von Teilleistungen, von denen der Log
nichts weiss; eine gesendete Angabe gewinnt. `None` heisst «hier ist noch nichts
angekommen» — dann gilt der Buchungstag; ein erfundenes Datum wäre schlimmer als keines.

#### Die Währung — EINE je Vorgang, gebunden mit der Zusage

**Ein Betrag ohne Währung ist keine Zahl.** «1000» ist tausend Franken oder tausend Yen,
und das sind zwei sehr verschiedene Beträge. Solange nur eine Währung vorkommt, fällt es
nicht auf — und beim ersten EU-Kunden ist es still falsch.

**Eine je Vorgang, nicht je Zeile** (`deals.currency`, ISO 4217): zwei Währungen auf einem
Beleg gibt es nicht, das wären zwei Belege. Vorbelegt ist die Währung des **Betreibers**
(`company_settings.currency` → `deal.house_currency`) — der Normalfall, und ihn zu tippen
wäre eine Eingabe mit genau einer richtigen Antwort.

**Änderbar bis zur Zusage, danach nicht mehr** — und das ist keine zusätzliche Regel,
sondern dieselbe Tabelle: `currency` steht in `ACTIONS[OFFER]`, also fehlt der Knopf
danach von selbst und `apply` weist ihn ab (`can` ist Auskunft **und** Tor). Draussen liegt
ab der Zusage eine Zusage über *diese* Summe in *dieser* Währung; sie nachträglich
umzuschreiben hiesse, die Zahl stehen zu lassen und ihre Bedeutung zu ändern.

►►► **Die Nachkommastellen sind der Punkt, den man vergisst** (`domain/currency`). ◄◄◄

Fast alle Währungen haben zwei — und darum schreibt man `f"{x:.2f}"` bzw. `NUMERIC(x, 2)`
und merkt nie, dass es falsch ist. **JPY und KRW haben null**, **KWD hat drei**. Ein
Yen-Betrag mit zwei Nachkommastellen ist kein Rundungsfehler, sondern ein Betrag, den es
nicht gibt; ein dreistelliger, auf zwei geschnitten, verliert still seine letzte Stelle —
in der Richtung, in der die Zahl **kleiner** wird.

Die Stelligkeit hängt darum an **einer** Stelle (`currency.minor_units` / `quantum`), und
sie gilt auf **vier** Ebenen: beim Parsen (`deal.amount`), beim Rechnen (`_round`, das an
`currency.round_to` delegiert — **kaufmännisch**, denn `quantize` rundet ohne Angabe
statistisch und wiche damit von der Buchung ab), beim Ausgeben (`currency.money`) und in
der **Spalte** (`NUMERIC(18, 4)`, Migration 128 — vier deckt jede ISO-4217-Währung ab).
Zur Laufzeit reist sie mit den Daten (`DealEmbed.currency_decimals`), damit die Anzeige
nicht rät.

**Umgerechnet wird nichts, und gemischt wird nichts.** Ein Kurs ist eine Angabe mit einem
Datum, einer Quelle und einer buchhalterischen Bedeutung (Stichtagskurs,
Durchschnittskurs, Bewertung zum Bilanzstichtag) — das ist Buchhaltung, nicht ein Feld in
einem Prozessmodul. Wer umrechnet, ohne zu sagen *wann* und *woher*, erfindet Zahlen.

Der Katalog ist bewusst **kurz** (die Währungen, in denen ein Schweizer KMU wirklich
fakturiert, plus die drei null- und dreistelligen als Beleg dafür, dass die Regel keine
Behauptung ist); eine neue Währung ist **eine Zeile**. In der Oberfläche steht sie **im
Kopf des Vorgangs**, nicht an jeder Zahl — fünfzehnmal «CHF» neben fünfzehn Beträgen wäre
Fläche statt Struktur; genannt wird sie beim **Total** und beim **offenen Betrag**, den
Zahlen, die abgeschrieben und überwiesen werden.

#### Ein Vorgang hat zwei Parteien

Der **Angebotsspiegel** (`deals.quotes`) ist der Kern der ersten Zeile: wir fragen an bzw.
bieten an (`ask`), die Gegenpartei nennt ihren Preis (`quote`) oder sagt ab (`decline`),
wir geben den Zuschlag (`agree`). **Eine Liste, auch wenn fast immer einer drinsteht** —
n statt 1: wer vergleichen will, fragt drei, und der Vergleich ist damit kein zweiter
Mechanismus.

*«gewählt» entsteht nicht durch Tippen, sondern dadurch, dass bei dieser Zeile zugesagt
wurde — ein Zustand ist eine Folge.*

**Steht in der Definition genau eine Gegenpartei, gibt es nichts zu wählen** (#793): dann
heisst der Knopf schlicht «Anfragen» bzw. «Anbieten». Nur wo die Definition **niemanden**
nennt, ist die Wahl eine echte Frage — und dann wird gesucht (`ObjectSelect`, dieselbe
Bauart wie jede Referenz im Haus), statt eine leere Liste zu zeigen.

**Eine Angebotszeile wird durch NEUBAU geändert, nie an Ort** (`_write_quotes`): der
geladene JSONB-Wert darf nicht mutiert werden — sonst sind geladener und aktueller Wert
gleich, die Spalte fällt aus dem `UPDATE`, und die Offerte ist stillschweigend weg.

#### Der Zugang der Gegenpartei — ein ZUGANG, keine Rolle im Vorgang

Wer angefragt ist und **nicht** ins ERP darf, sieht eine sehr enge Sicht: **seine**
Angebotszeile, keine fremde, und keine Zahl über Forderung und Geld. Gefiltert wird beim
**Aufbau der Antwort** (`deal.embed_data`), nicht in der Oberfläche — wer den Filter dort
formulierte, hätte ihn beim zweiten Aufrufer nicht. Was er **tun** darf, sagt dieselbe
Tabelle wie bei allen anderen (`can` ∩ `PARTY_ACTIONS` = `quote`·`decline`), und `_target`
liest die Zeile aus dem **angemeldeten Benutzer**, nie aus der Nutzlast.

**Ein Mitarbeiter behält die volle Sicht — auch wenn er selbst die Gegenpartei ist.** Die
Frage lautet «darf dieser Betrachter ins ERP?» (`STAFF_ROLES`), nicht «kommt seine Nummer
im Vorgang vor»: er sieht dort ohnehin den ganzen Auftrag, und eine zweite, engere Ansicht
desselben Datensatzes wäre eine zweite Wahrheit. Hinge die Verengung an der **Beteiligung**,
verlöre ein Einkäufer, den man einmal selbst anfragt, an genau diesem Auftrag die Zahlen,
die er zum Arbeiten braucht.

##### Wer nicht den Zuschlag hat, sieht ihn auch nicht

Die erste Fassung schloss die Gegenpartei aus dem **Auftrag** aus und liess ihr **im Modul**
alles. Gemessen an einem unterlegenen Lieferanten nach dem Zuschlag an einen anderen: er las
dessen **Namen**, dessen **Preis**, die Zahlungsfrist, das Zusagedatum – und dazu die
**Freigabe-Liste**, also die Konkurrenzliste selbst.

Die Regel ist darum dieselbe wie beim Beschaffungs-Beleg (`won`): Name, Betrag, Frist,
Referenz und Datum der Zusage fallen für jede Gegenpartei weg, die nicht selbst den Zuschlag
hat; die Freigabe-Liste fällt für **jede** Nicht-Personal-Sicht ganz weg. *Zwei Formen einer
Regel sind in Ordnung; zwei Regeln nicht* – auch wenn die beiden Module bewusst keine Zeile
Code teilen.

Und **das Wort der Gegenhandlung hängt an `can`**, nicht an der Stufe: sonst steht bei einer
Gegenpartei «Auftrag stornieren» an einem Knopf, den es für sie nie gibt.

##### Eine Frage, zwei Leser: Feed und Detail

Beteiligt ist, wer an einem **der beiden** Module mit Aussenwirkung vorkommt
(`orders._involved` = `deal.mine`; es war einmal eine Vereinigung mit dem
Beschaffungs-Beleg). Der Feed fragte einmal nur den
Beschaffungs-Beleg: die Gegenpartei eines Geldvorgangs hatte ERP-Zugang, sah ihren Auftrag
aber in **keiner Liste** – erreichbar nur über die direkte Adresse. Zwei Ableitungen
derselben Frage laufen genau so auseinander.

**Und sie bestätigt kein Modul.** `confirm_step` ist Personal-only; der Bestätigungsweg
hängt darum an derselben Naht wie das Modul-Protokoll (`internal` – die Aussage der
Aufrufstelle über sich selbst), nicht an einer Rollenabfrage. Ein Knopf, der nie etwas tun
kann, ist kein Angebot.

#### Wie man bei IHM bestellt — die Bestellangabe

Seine Artikelnummer, sein Shop-Link (`config.parties[].ref`). Sie ist eine Eigenschaft der
**Paarung** Modul × Gegenpartei und nicht der Gegenpartei allein: derselbe Lieferant führt je
Teil eine andere Nummer. Sie gehört darum dorthin, wo man festlegt, **wer in Frage kommt** –
am Beleg wäre sie eine Angabe, die man bei jedem Vorgang neu abschreibt.

**Nur wo wir bestellen** (`Direction.party_ref`): beim Verkauf liefern wir, dort gibt es das
Feld nicht, und ein trotzdem gesendeter Wert wird **verworfen** – ein Feld, das keine
Oberfläche zeigt, der Dienst aber annimmt, wäre die Hintertür zu einer Angabe, die niemand
liest (dieselbe Regel wie #787). Zur Laufzeit steht sie an **seiner** Angebotszeile; sieht
sie aus wie eine Adresse, ist sie ein Link.

#### Die beiden Fristen — Pflicht, und die Null hat einen Namen

►►► **Ein Angebot nennt beide Fristen** (Testnotizen #854–#856). ◄◄◄ Sie sind kein
Beiwerk: aus der **Lieferfrist** kommt der Termin, aus der **Zahlungsfrist** die
Fälligkeit jeder Rechnung — und, wenn sie null ist, die Vorauszahlung. Fehlt eine, hat
niemand über den Zeitpunkt gesprochen, und das System müsste einen erfinden. Durchgesetzt
wird das im **Dienst** (`deal._assert_terms`, geprüft wird bei `quote` das **Ergebnis**,
nicht die Nutzlast), nicht am Feld: die Tür ist nicht der einzige Aufrufer.

**Die üblichen Werte tragen Namen** (`domain/deal.PAYMENT_TERMS` / `LEAD_TERMS`):
*Vorauszahlung* (0) · *30 Tage* — und *Sofort* (0) für die Lieferfrist. *«Bei einer
Software ist die Lieferfrist 0 — soll ich dann einfach 0 eintragen?»* Ja, und genau darum
steht dort ein **Wort**: eine Null in einem Feld «Tage» ist von einer vergessenen Eingabe
nicht zu unterscheiden, ein Name ist eine Angabe.

**Kein Schieberegler.** Eine Frist ist keine stufenlose Grösse — zwischen «Vorauszahlung»
und «30 Tage» liegt nichts, was man durch Ziehen findet, und ein Regler über 0–365 träfe
die 30 nur mit Glück. Es ist eine **Aufzählung mit einem freien Rest**, und die freie
Eingabe beginnt bei `FREE_MIN = 1`: sonst gäbe es zwei Wege zur Null und zwei Bedeutungen,
von denen eine niemand kennt.

#### Lieferverzug — eine ABLEITUNG, kein Zustand

Der Liefertermin ist *Zusagedatum + Lieferfrist der gewählten Zeile*, und «verspätet»
heisst *Termin vorbei und noch nicht erledigt* — **exakt dieselbe Form wie `overdue`** bei
einer Forderung (`deal._delivery` / `_is_late`). Zwei Ableitungen, **null Spalten**: ein
gespeicherter Verzug wäre ein Wert, den jemand nachziehen müsste, und er lügt beim ersten
vergessenen Mal. **Ohne vereinbarte Frist gibt es keinen Termin** — ein erfundener wäre
schlimmer als keiner, und genau daran erkennt man, dass niemand über die Zeit gesprochen
hat.

Was man dann tun kann, **gibt es alles schon**: warten · stornieren (die Stücke stehen
still, ein ganz gewöhnlicher Abweichungsauftrag entscheidet über sie) · und das Geld läuft
unabhängig weiter — genau darum sind `charge` und `pay` auch nach dem Storno erlaubt, damit
eine Anzahlung erstattet werden kann. Ein «Verzug»-Status hätte keine dieser Handlungen
hinzugefügt; er hätte nur eine vierte Sache zu pflegen gegeben.

#### Kein Scan — und das ist eine Eigenschaft des Moduls

Ein Geldvorgang bewegt keine Stücke: es gibt **nichts zu verifizieren**, und ein Scan davor
wäre ein erfundenes Hindernis. Die Frage steht am Modul (`Module.requires_verification`)
und reist als `ModuleFacts.verifies` mit dem Schritt — die Ausführungsstelle nennt damit
keinen Modultyp, und jedes künftige Modul ohne physisches Gegenstück erbt die Regel ohne
eine Zeile.

**Die Richtung ist eine Einstellung, kein zweiter Modul-Schlüssel.** Es ist EIN Modul, eine
Kachel in der Palette; die `config` friert mit der Freigabe ein und reist mit dem Schritt,
ist also genauso haltbar wie ein Schlüssel. Am **Vorgang** wird sie zusätzlich eingefroren
(`deals.direction`): läse er sie bei jeder Anzeige neu, änderte ein späterer Umbau
**rückwirkend**, was ein alter Vorgang bedeutet.

#### ZWEI Stufen — und die dritte Zeile ist keine

Unumkehrbar sind **zwei** Dinge: nichts zugesagt (`Angebot` ↔ `Anfrage`) · zugesagt
(`Auftrag`). `Erledigt` und `Storniert` sind **Ausgänge**: man kommt dort an, statt
hindurchzugehen. Wie die Stufen in einer Richtung *heissen*, sagt `domain/deal.DIRECTIONS`
— als **Daten**, nicht als Verzweigung: die erste Verzweigung ist eine Beschriftung, die
zweite eine Regel, und ab der dritten gibt es zwei Vorgänge, die nur so tun, als wären sie
einer.

*«Abgeschlossen» stand einmal als dritte Stufe da und war genau das Missverständnis — ein
**Zustand** in einer Reihe von **Schritten**. Man tut nichts, um ihn zu erreichen; er tritt
ein, wenn nichts mehr davorsteht (`deal.finish`).*

**Die dritte Zeile der Karte ist das GELD**, und es ist bewusst keine Stufe: eine Zahlung
macht aus einem Angebot keine Zusage, sie ist reversibel, und sie darf **vor** der Erfüllung
stehen (Vorauszahlung) wie danach (Zahlungsziel). Wer sie als dritte Stufe führte, hätte für
die Vorauszahlung ein `if`. Sie steht dort, wo man sie erwartet — dritte Position —, und ist
ab der Zusage bedienbar; die Kette darüber sagt weiterhin nur, was **zugesagt** ist.

**Das Verb der Schwelle heisst in beiden Richtungen «Auftrag bestätigen»**: was passiert,
ist dasselbe — zwei Parteien sind ab hier gebunden. Ein eigenes Wort je Richtung wäre eine
Unterscheidung, die es in der Sache nicht gibt.

#### Zwei Achsen, und darum kein einziger Modus

`deals` trägt die **Zusage**, `deal_entries` die **Forderungen** und die **Zahlungen**
(`kind`: `charge` ↔ `payment`, Betrag **darf negativ sein**). Alles Weitere ist abgeleitet:
*berechnet*, *bezahlt*, *offen* = berechnet − bezahlt, *noch nicht berechnet* = zugesagt −
berechnet. **Null Spalten** — eine gespeicherte «offen»-Spalte wäre die zweite Wahrheit,
und die eine vergessene Nachzieh-Stelle fällt erst auf, wenn jemand mahnt.

| Szenario | Folge | neuer Mechanismus |
|---|---|---|
| Zahlungsziel | zusagen → abschliessen → fordern → zahlen | keiner |
| **Vorauszahlung** | zusagen → fordern → zahlen → abschliessen | keiner |
| Anzahlung + Schluss | zusagen → fordern → zahlen → … → fordern | keiner |
| Gutschrift / Kulanz | **negative** Forderung, ohne Ware | keiner |
| Erstattung | **negative** Zahlung, auch nach dem Storno | keiner |

**`prepaid` fragt nach der ZUSAGE, nicht nach dem offenen Betrag.** Direkt nach der Zusage
ist *offen* null — weil noch **nichts gefordert** wurde. Dieselbe Zahl, eine ganz andere
Aussage; wer sie liest, hielte den Vorgang für bezahlt (`Balance.settled`).

**Eine naheliegende Handlung, und der Server sagt welche** (`next_charge` ↔ `next_payment`,
`Balance`): erst fordern, dann kassieren. Beide Achsen bleiben frei — alles Übrige liegt
unter «Weitere» —, aber sie standen als drei gleichwertige Knöpfe da, und drei gleich laute
Angebote sind kein Vorschlag. **Und keine Vorgabe ist je negativ** (#795): dass mehr
berechnet als zugesagt wurde, ist eine gültige Aussage — als Vorschlag in einem
Eingabefeld ist sie es nicht; dort stand «−250.00», und niemand stellt eine Rechnung über
minus 250. Negative Beträge bleiben **eingebbar**: das ist die Gutschrift bzw. die
Erstattung.

#### `can` ist Auskunft UND Tor

Was an welcher Stufe erlaubt ist, steht in **einer** Tabelle (`services/deal.ACTIONS`):
die Oberfläche rendert einen Knopf genau dann, wenn sein Verb in `can` steht, und `apply`
weist ab, was nicht darin steht. Wäre `can` nur ein Anzeige-Hinweis, liefen Knopf und Tür
beim nächsten Verb auseinander.

**Geld darf ab der Zusage in jeder Stufe fliessen — auch nach dem Storno**: eine Anzahlung
muss erstattet werden können, und eine Rechnung darf vor der Lieferung stehen und danach.
Ein **Storno behält seinen Weg**: er macht die Zusage nicht ungeschehen, er sagt nur, dass
nichts mehr kommt.

#### Die Nummer

`<Auftragsnummer>-<laufend>`, wo **wir** nummerieren (`direction = in`) — dieselbe Regel
wie beim Suffix der Einzelinstanz, und **immer mit Suffix, auch die erste** (Testnotiz
#827). Früher fiel das «-1» nach aussen weg; das war eine Sonderregel für genau einen
Fall, und dieselbe Serie hiess danach «100000801», dann «100000801-2» — zwei Formen für
eine Nummer, und wer sie sortiert oder sucht, muss beide kennen.

Bei einer **Ausgabe** steht dort die Nummer der Gegenpartei; eine erfundene wäre eine
Behauptung über ein fremdes Dokument. *Gezählt wird nur, was wir selbst nummerieren: in
einem Auftrag, der zuerst eine Lieferantenrechnung erfasst, hiess die erste eigene sonst
«…-2» — eine Nummernserie mit Lücken ist buchhalterisch keine (gemessen beim Durchspielen
der Szene, nicht gelesen).*

#### Storniert wird durch eine GEGENBUCHUNG, nie durch Löschen

*«Soll man wirklich aktiv erfasste Rechnungen so löschen können? Ich denke eher in
Richtung stornieren.»* (Testnotizen #823/#824) — Das ist zwingend: eine Rechnungsnummer
ist vergeben, ein Beleg ist draussen. Wer die Zeile verschwinden lässt, behauptet, sie sei
nie passiert; das ist keine Buchhaltung. Vorher machte `void` einen Soft-Delete — der
Saldo stimmte, die Zeile war weg.

**Und es braucht keine neue Mechanik.** Eine Gutschrift ist längst eine *negative
Rechnung*, eine Erstattung eine *negative Zahlung* (§9.11) — eine Stornierung ist genau
das, über den vollen Betrag. Also entsteht eine **zweite** Zeile: dieselbe Art, der
negative Betrag, `reverses_id` auf die stornierte (Migration `126`). Beide bleiben stehen,
`balance` rechnet sie ohne einen einzigen Sonderfall, und der Nachweis ist lückenlos.

Zwei Sperren, und beide fallen aus derselben Frage: eine **Gegenbuchung** storniert man
nicht, und eine bereits **stornierte** Zeile ebenso wenig — sonst entstünde eine Kette aus
Vorzeichen, in der niemand mehr sagen kann, was gilt. Sie stehen in `can` (also fehlt der
Knopf) **und** in `_reverse` (also weist die Tür ab). **Einen Löschweg gibt es nicht** —
auch nicht für einen Tippfehler; eine Frist («innerhalb fünf Minuten») wäre eine erfundene
Regel mit einer Uhr darin.

#### Man storniert einen BELEG, kein Ereignis

*«wenn ich eine zahlung erfasst habe, dann habe ich sie ja erfasst, dann kann ich sie doch
nicht mehr stornieren… dann muss ich sie durch eine weitere zahlung korrigieren oder???»*
(Testnotiz #842) — Ja, und diese Antwort ist die richtige. Der Storno lag eine Runde lang
auf **beiden** Achsen; das war ein Schritt zu weit.

======================  ===============================  ==============================
Zeile                   was sie ist                      wie man sie korrigiert
======================  ===============================  ==============================
**Forderung**           ein Beleg, den **wir** ausstellen **Storno** – eine
                                                         Stornorechnung, eigener Beleg,
                                                         eigene Nummer
**Zahlung**             ein **Ereignis** der Aussenwelt   eine **zweite Zahlung**
                        (Geld ist geflossen)             (negativ)
======================  ===============================  ==============================

`reverse` gilt darum **nur für eine Forderung** — durchgesetzt in `_reverse`, nicht nur am
Knopf, und `can` führt das Verb gar nicht erst, wenn nur Zahlungen dastehen. An einer
Zahlung steht stattdessen **«Korrigieren»**, und das ist **kein neues Verb**: es öffnet die
gewöhnliche Zahlungs-Erfassung mit dem **negativen Betrag vorbelegt**. Ob es ein
Erfassungsfehler war oder ob das Geld zurückkam, weiss nur ein Mensch — beides ist dieselbe
Zeile, und die gibt es längst. *Das System bietet an, der Mensch entscheidet* — dieselbe
Regel wie §4.5 bei «nicht bestanden».

*Bewusst nicht gebaut und benannt: die **Zuordnung Zahlung → Rechnung** (Ausziffern offener
Posten). Bei einem Vorgang mit meist einer Rechnung ist der Topf richtig; die Zuordnung wäre
ein zweites Modell für dieselbe Zahl.*

#### Jede Nummer wird genau EINMAL vergeben

Die Storno-Zeile kopierte die Nummer der stornierten (Testnotiz #841): zwei Belege hiessen
gleich, und in der Serie fehlte die nächste Zahl. Eine Stornorechnung ist aber ein **eigener
Beleg** — MWST-pflichtig mit eigener Nummer und einem **Verweis** auf die stornierte. Sie
zieht darum die nächste Nummer; der Bezug wohnt in `reverses_id` und im Vermerk, nie in der
Nummer.

Und daraus folgt die andere Hälfte (#840): **eine Nummer, die wir vergeben, tippt niemand
ab.** Das Feld gibt es genau dort, wo die Nummer **von aussen** kommt — an einer
Lieferantenrechnung (sie steht auf seinem Papier) und an jeder Zahlung (QR-Referenz,
Zahlungszweck, die Id des Zahlungsdienstes). Wie es heisst, sagt `Direction.charge_reference`
bzw. `PAYMENT_REFERENCE`; `None` heisst «gibt es hier nicht». Ein trotzdem gesendeter Wert
wird **verworfen** — ein ausgegrautes Feld wäre eine Bitte.

#### Wer den Preis nennt, ist eine Eigenschaft der Richtung

*«Wenn ich einkaufe, sage ich was und von wem ich es offeriert haben möchte, die Gegenpartei
trägt Preis ein und ich akzeptiere. Beim Verkaufen sage ich zuerst was ich zu welchem Preis
an wen offeriere, Kunde bestätigt.»* (Testnotiz #837) — Exakt richtig, und vorher nicht
abgebildet: `ask` schickte in **beiden** Richtungen eine leere Zeile hinaus, beim Verkauf
sähe der Kunde also ein Angebot ohne Preis.

Ein Angebot hat einen **Urheber** (`Direction.quoted_by`), und daraus folgt alles:

* **Wir nennen** (Einnahme): der Betrag ist **Pflicht, bevor es hinausgeht**; die Zeile
  entsteht sofort als *offeriert*. Die Gegenpartei ändert unseren Preis nicht — sie **nimmt
  an oder lehnt ab**.
* **Er nennt** (Ausgabe): leere Anfrage, er offeriert, wir wählen.

`PARTY_ACTIONS` ist damit keine Konstante mehr, sondern `Direction.party_actions` — eine
**Ableitung** aus `quoted_by`, keine zweite Angabe. Das ist die eine erlaubte Unterscheidung
zwischen den Richtungen, und sie steht als **Daten** im Flow, nicht als `if direction ==`.

#### «Einnahme» und «Ausgabe», nicht «Verkauf» und «Einkauf»

Testnotiz #831, und sie nimmt meine Wahl aus #804 zurück. Dieses Modul entstand aus der
Einsicht, dass der kleinste gemeinsame Nenner **nicht die Ware** ist: Miete, Lohn, Gebühr,
Spesen und ein Transport sind keine Käufe. Ein Wert, der «Verkauf» heisst, ist damit **enger
als das Modul**, und beim ersten Mietvertrag ist er schlicht falsch.

Und darum trägt es auch **nicht die Symbole des Handels** (`FLOW`: Einkaufswagen ↔
Handschlag) — ein Handschlag über einer Mietzahlung behauptet ein Geschäft, das es nicht
gibt. Zwei diagonal entgegengesetzte Pfeile sagen, wohin das Geld fliesst, und mehr
behauptet dieses Modul nicht.

#### Ohne Rechnung keine Zahlung

Man kassiert nicht, was niemand gefordert hat (Testnotiz #822). Der Satz stand seit §9.11
im Haus; jetzt steht er auch in `can`, also in **beiden** Formen — der Knopf fehlt, und
`apply` weist ab. Die **Vorauszahlung** verliert dadurch nichts: sie ist «erst fordern,
dann zahlen», die Rechnung kommt dort vor der Lieferung, nicht nach der Zahlung.

#### Was ein Modul BERICHTET, und wann es noch etwas zu TUN gibt

Zwei Ableitungen am Schritt, beide aus Angaben, die ohnehin dastehen — und keine fragt
nach dem Modultyp:

* **`open_actions`** (Testnotiz #821): steht an diesem Modul noch etwas an? Gelesen aus
  `deal.can`, also aus derselben Tabelle, die auch das Tor ist. Die
  Zeichnung dämpft ein Modul nur, wenn es **nicht dran ist und nichts mehr zu tun hat** —
  vorher lag ein abgeschlossener Auftrag bei 55 % Deckkraft da, während seine Geld-Knöpfe
  funktionierten. Eine erfundene Sperre, nur in Farbe.
* **`records`** (Testnotiz #825): hat dieses Modul mehr zu berichten als die blosse
  Passage? Es gibt genau drei Dinge, die ein Eintrag über «wer, wann» hinaus tragen kann —
  **erfasste Werte** (Erfassungspunkte in `config`), **ein Zustandswechsel**
  (`status_before ≠ status_after`) und **eine Verifikation** (der Scan). Trifft keines zu,
  ist das Protokoll leer im Wortsinn und wird nicht angeboten. Entfernt wird es nirgends —
  es ist der Nachweis.

#### Die Wörter, die keine Wahl mehr sind

`Direction` trägt nur noch, was wirklich verschieden ist: `label`, `hint`, `stage_labels`
und `ask_verb` — wer zuerst fragt, ist nicht derselbe. Alles Übrige lautet in beiden
Richtungen gleich und steht als **Konstante**: das Verb der Schwelle (**«Angebot
annehmen»**, #826 — man nimmt das *Angebot* an, der Auftrag ist das Ergebnis), das des
Abschlusses, die Gegenhandlung und die beiden Geld-Wörter (**«Rechnung erfassen»** ·
**«Zahlung erfassen»**, #828 — erfasst wird beides, egal wohin das Geld fliesst; das
System bucht eine Zeile, es überweist nichts). Als Feld wären es fünf Werte, die jemand
einzeln falsch setzen kann; als Konstante sind sie eine Aussage.

Dieselbe Regel im Editor: **was ein Bedienelement selbst sagt, sagt man nicht daneben**
(#816/#817/#819). Die Labels «Geschäft», «Was ist zu tun?» und «Weiter, wenn» sind
entfallen — und die Werte des letzten Schalters heissen dafür **«Nach Zusage» ↔ «Nach
Zahlung»** (#818): «zugesagt» klang nach einem *Zustand* statt nach einer *Bedingung* und
war einzeln gelesen eine schlechte Beschreibung.

#### Wo der Abschluss steht, und was das Feld hält

Der Modul-Abschluss steht **am Ende der Karte** (#829), hinter der Geld-Zeile. Er stand in
der Stufe «Auftrag», also mitten in der Kette, und darunter kam noch etwas: ein Knopf, der
ein Modul abschliesst, sagt damit «hier ist Schluss», während sichtbar noch etwas folgt.
Rechnung und Zahlung gehören zum Modul, auch wenn sie nachgelagert kommen. Die Sperre
(`prepaid`) ersetzt an genau dieser Stelle den Knopf — der Grund steht dort, wo man
weiterklicken würde.

Und das Partner-Feld an der Ausführungsstelle hält die frische Wahl nur, **bis sie als
Zeile dasteht** (#794 → #820): gehalten wird sie, weil sie im Moment des Klicks noch nicht
gespeichert ist; sobald der Server sie als Angebotszeile zurückgibt, ist sie es, und dann
stünde derselbe Partner zweimal da. Eine **Ableitung**, kein zweiter Zustand — ein
Zurücksetzen an der Antwort wäre die Stelle, die der nächste Pfad vergisst. *Der Editor
war es nicht: dort räumt `SearchSelect.pick` seine Suche selbst auf (gemessen in Chromium,
zwei Adds hintereinander, beide Male leer).*



### 9.13 Online bezahlen — die Karte gehört UNS

> **Status: gebaut.** Der Zahllink ist weg; bezahlt wird im ERP. Der Zahlungsdienst
> liefert nur die Eingabefelder — und genau das ist sein Sinn.

#### Die Umdeutung, aus der alles folgt

Bisher erzeugte `…/payment-link` eine **gehostete Kasse** beim Dienst: der Zahlende
verliess das ERP und stand auf einer fremden Seite mit fremdem Namen, fremder Schrift und
fremder Adresszeile. *Er hatte ausserdem seit dem Ende des Handels-Belegs **kein einziges
Bedienelement** — ein Endpunkt, den niemand rief.*

Jetzt entsteht dort nur eine **Zahlungsabsicht** (`stripe_pay.prepare`), und ihr Geheimnis
geht an eine eigene Karte im ERP. Fläche, Wörter, Betrag, Knopf und Rückmeldung gehören
uns; vom Dienst kommen die **Eingabefelder** in einem iframe.

> **Das ist kein Kompromiss, sondern der Grund.** So berührt **keine Kartennummer je
> unseren Server** — der Unterschied zwischen «wir nehmen Karten an» und «wir sind
> PCI-pflichtig». Und die 3-D-Secure-Abfrage gehört der Bank; sie liesse sich gar nicht
> nachbauen.

Damit man die Naht nicht sieht, kommt das **Aussehen aus unseren Tokens**
(`getComputedStyle` liest die CSS-Variablen des Hauses) — nicht aus einer geratenen
Farbliste, die beim nächsten Design-Wechsel stehen bleibt.

#### Was wir wissen, fragen wir nicht

Name, E-Mail und Rechnungsadresse der **Gegenpartei dieses Vorgangs** (nicht des
Betrachters — die Rechnung gehört dem Kunden, auch wenn ein Mitarbeiter die Zahlung
auslöst) reisen mit der Vorbereitung mit und werden dem Element als **feste Angabe**
übergeben.

**Die beiden Hälften gehören zusammen**: `fields: 'never'` heisst «wird mitgeliefert» —
wer nur die eine schreibt, bekommt eine Ablehnung, und zwar erst beim Bezahlen, also in
der unangenehmsten Form. Und **nur, was wirklich dasteht**: fehlt die Adresse, fragt das
Element sie; eine halbe Vorbelegung wäre schlechter als die Frage.

#### Eine Zahlung gehört zu genau EINER Rechnung

►►► *«Wenn ich eine Rechnung ausstelle, dann wird eine Zahlung auf genau diese Rechnung
referenziert. Ich soll nicht eine Zahlung für zwei verschiedene Rechnungen erfassen können
— dann lieber die zwei Rechnungen stornieren und eine daraus machen.»* (Testnotiz #858)
◄◄◄

Richtig, und die einfachere Regel ist zugleich die buchhalterisch saubere: der Weg für
«eine Überweisung über zwei Rechnungen» ist eine **Stornorechnung und eine gemeinsame
neue** — beides gibt es längst, und am Ende steht ein Beleg, den man vorzeigen kann. Die
Alternative wäre eine Aufteilungstabelle (das *Ausziffern* offener Posten) für eine Zahl,
die daneben ohnehin als Summe steht.

**Ein Feld je Frage** (`deal_entries.charge_id`, Migration `129`): die Zuordnung
beantwortet **worauf**, `balance` weiterhin **wie viel** — es rechnet unverändert über die
Summen aller Zeilen, und darum ändert sich an keiner bestehenden Zahl etwas. `NULL` ist
regulär und heisst «nicht zugeordnet»; nachträglich zugeordnet wird **nichts** — eine
geratene Zuordnung wäre eine Behauptung über einen Beleg.

**Drei Fälle, und keiner ist eine Einstellung** (`deal._charge_for_payment`): genau **eine**
offene Rechnung → sie ist gemeint (danach zu fragen wäre eine Frage mit genau einer
richtigen Antwort) · **mehrere** → die Zahlung muss sagen, welche, und der Satz **nennt
sie** · **keine** → offen (eine Erstattung gehört zu einer längst beglichenen).

**Und die Bezahlkarte kassiert genau diese eine** (`stripe_pay.prepare` → `open_charges`,
die älteste offene): ihr Rest ist der Betrag, ihre Nummer steht **menschenlesbar** in der
Beschreibung und **maschinenlesbar** in den Metadaten. Vorher war es der offene Betrag des
**ganzen Vorgangs** — also eine Zahlung, die auf zwei Belege zeigt.

*Nicht hier: der «statement descriptor» — der Text, den die Bank dem Karteninhaber zeigt.
Er gehört dem **Konto**, nicht der Zahlung (`docs/stripe-setup.md` §2).*

#### `pay_online` — die dritte Handlung am Geld

`pay` schreibt auf, was geschehen ist (eine Überweisung liegt auf dem Konto);
`pay_online` **lässt es geschehen** und bucht selbst nichts. Zwei Handlungen, zwei Verben.

**Drei Bedingungen, alle in `can`** — dieselbe Liste ist Auskunft **und** Tor:

| Bedingung | warum |
|---|---|
| `Direction.collects` | Ein Zahlungsdienst **zieht ein**; er überweist nicht in unserem Namen. Bei einer Ausgabe gibt es den Knopf nie. |
| `payment_service_ready()` | Ohne Schlüssel endete er in einem leeren Dialog — «ein Knopf, der nie etwas tun kann, ist kein Angebot». |
| `open > 0` | Über null lässt sich nichts einziehen. |

*Eine vierte stand hier — «es muss eine Rechnung geben», die Regel von `pay` (§9.12). Beim
Gegenprüfen war ihre Bug-Form **nicht herstellbar**: `open` ist `Forderungen − Zahlungen`,
ohne Forderung also nie positiv. Sie sagte nichts, was `open > 0` nicht schon sagt, und
ist entfallen. Bei `pay` bleibt sie richtig — dort nennt ein Mensch den Betrag; hier **ist**
der offene Betrag die Sache.*

**Es hat keinen Eintrag in `HANDLERS`** und einen eigenen Endpunkt (`…/deal/payment`): der
`…/deal`-Weg gibt den Auftrag zurück, hier kommt ein Geheimnis für genau diese eine
Zahlung. Damit `apply` an einem Verb ohne Handler nicht mit `KeyError` zerbricht — an der
Tür ein **500** —, antwortet es mit einem **Satz**.

#### Die Gegenpartei bezahlt selbst — und sieht dafür die Zahlen

`Direction.party_actions` trägt `pay_online` in **beiden** Richtungen; *ob* es an diesem
Vorgang etwas zu bezahlen gibt, beantwortet eine Ebene höher `collects`. Zwei Stellen für
dieselbe Bedingung wären zwei Massstäbe.

**Und damit sieht sie die Geld-Zahlen** (`won` statt `internal`): wer bezahlen soll, muss
sehen, was er schuldet — eine Aufforderung ohne Betrag ist keine. **Ein Leck ist es
nicht**: `won` heisst «dieser Betrachter *ist* die Gegenpartei dieses Vorgangs», die
Rechnungen sind seine; ein angefragter, unterlegener Dritter sieht weiterhin nichts.
**Buchen darf sie trotzdem nicht** — eine Buchung ist unsere Aussage über unser Konto.

#### Gebucht wird nur vom Webhook

`payment_intent.succeeded` (nicht mehr `checkout.session.completed` — die gehostete Kasse
gibt es nicht mehr) schreibt **eine Zeile Geld**, idempotent über die `pi_…`-Referenz.
Gebucht wird `amount_received`, nicht `amount`: bei einer Teilautorisierung sind das zwei
Zahlen, und nur die zweite ist eine Zahlung.

Die Karte sagt darum «**ausgeführt**», nie «gebucht»: dazwischen liegt eine Sekunde, die
niemandem gehört. Der Browser ist keine Quelle — wer ihn nach der Zahlung schliesst, darf
keine Buchung verschlucken.

►►► **Angezeigt wird sie trotzdem sofort** (Testnotiz #857). ◄◄◄ *«Nachdem ich als Partner
bezahlt habe, wurde es erst nach einem Refresh angezeigt — gewollt, oder gibt es einen
eleganten, einfachen Weg?»* Gewollt ist die **Quelle**, nicht das Warten: zwischen dem
«bezahlt» der Karte und der Meldung des Dienstes liegen ein bis drei Sekunden, und in denen
lädt ein einzelnes Nachladen zu früh.

**Der einfache Weg ist fragen** — kein WebSocket und kein SSE für **ein** Ereignis, das
einmal je Zahlung eintrifft: nachgefragt wird alle 1.5 Sekunden, bis sich die Summe der
Zahlungen ändert, höchstens zehnmal. **Und es endet an der Zeile, nicht an einer Uhr**:
bleibt die Meldung aus, steht die Karte still da, statt sie zu behaupten — der Nachweis ist
die Zeile, und die entsteht dort, wo das Geld gemeldet wird.

#### Der Anbieter steht nicht im Geldvorgang

«Ist ein Zahlungsdienst eingerichtet?» wohnt in `core/config.payment_service_ready()`. Der
Geldvorgang fragt eine **Eigenschaft**, keine Marke — ein Quelltext-Wächter hält es so.
Sie fragt nach **beiden** Schlüsseln (geheim: Absicht anlegen · öffentlich: Formular
rendern); einer allein ist eine halbe Strasse.

**Welche Zahlungsarten es gibt, entscheidet das Konto beim Dienst**
(`automatic_payment_methods`) — Karte, TWINT, was dort freigeschaltet ist. Eine Liste bei
uns wäre die zweite Stelle, an der beim nächsten Freischalten jemand nichts sieht.

### 9.14 Eine Rechnung je Modul — und die drei Wege zum Geld

►►► **«Je Zahlungsmodul gibt es maximal eine Rechnung.»** ◄◄◄ (Testnotiz #866)

*«Nur eine Rechnung pro Zahlungsmodul. Habe ich Teilrechnungen, dann erstelle ich einfach
2 Zahlungsmodule.»* — Und das ist die richtige Modellierung, weil der Grund die **Zeit**
ist: *Vorauszahlung → Leistung → Restzahlung* sind drei Zeitpunkte, und ein Modul steht an
einem. Zwei Rechnungen an derselben Stelle wären zwei Aussagen über einen Moment, den es
nur einmal gibt.

**Die eine Lesestelle ist `deal.live_charge`**, und was sie zählt, ist genau das, was eine
*Forderung nach aussen* ist:

| nicht gezählt | warum |
|---|---|
| eine **Gegenbuchung** (`reverses_id`) | sie ist die Rücknahme einer Rechnung, nicht eine |
| eine **stornierte** Zeile | genau das ist der Ausweg: was falsch ist, wird storniert und neu gestellt |
| eine **Gutschrift** (negativ) | eine Minderung, keine zweite Rechnung — Skonto, Teilretoure und Kulanz bleiben möglich |

**Damit ist die Regel keine Sackgasse**, und das ist der Punkt: sie verbietet die zweite
*offene* Forderung, nicht den zweiten Vorgang. Steht die Rechnung, gibt es hier nichts
mehr zu buchen — der Knopf **fehlt** (`credit_only`), und `next_charge` fällt mit ihm weg:
eine Vorgabe für eine Buchung, die der Dienst abweist, wäre ein Angebot, das garantiert
scheitert.

**Und das System wurde dabei kleiner.** `_charge_for_payment` hatte drei Fälle, darunter
«mehrere offene → die Zahlung muss sagen, welche», mit einem Satz, der sie aufzählte. Der
Ast ist **unerreichbar geworden** und ist entfallen — ein Ast, den niemand erreicht, ist
von einem kaputten nicht zu unterscheiden. Mit ihm ging `DealEmbed.open_invoices`.

#### Zwei Module tragen ihre eigenen Preise — einen «Anteil» gibt es nicht

Hier stand eine Runde lang `deals.share` (Prozent, Vorgabe 100): welchen Teil der
Positionen **dieser** Vorgang abrechnet, gedacht als Gegenstück zur Zwei-Modul-Form. Er ist
**ersatzlos entfallen** (Testnotiz #867 — *«ich checke diese Funktion nicht»*), und die
Aufteilung braucht ihn nicht: **wer den Preis nennt, nennt ihn je Position**, also trägt
die Anzahlung ihre eigenen Positionspreise und die Restzahlung ihre. Das ist zugleich die
genauere Antwort — ein Prozentsatz auf eine Summe verteilt sich über alle Steuersätze, ein
Preis je Position sagt, was er meint.

*Ein zweites Feld «gesperrt?» gibt es ohnehin nicht: `currency_locked` hatte **keinen**
Leser (die Oberfläche fragte längst `can`), und ein `share_locked` daneben gab einer
**Gegenpartei** ein Eingabefeld für eine Zahl, die der Dienst ihr nie abnimmt (gemessen).
`can` ist Auskunft **und** Tor; ein zweiter Wert daneben ist die Stelle, an der beide
auseinanderlaufen.*

#### Zwei Knöpfe mit demselben Wort sind einer zu viel

*«Gibt es hier Buttons/Funktionen, die doppelt sind bzw. in der Abfolge und der Logik
keinen Sinn machen?»* (#874) — Es gab zwei, und beide sind gefallen:

* **«Gutschrift erfassen»** stand am Vorgang, sobald die eine Rechnung stand — und an
  ihrer Zeile stand bereits «Gutschrift» (`reverse_word`). Dasselbe Wort, zwei Wirkungen:
  der eine nimmt **diese Rechnung** zurück (mit Bezug, und er gibt den Platz für eine neue
  frei), der andere buchte eine **freistehende** negative Forderung, die zu keinem Beleg
  gehörte und in der Liste als zweite Rechnung erschien. Was für eine Korrektur vorgesehen
  ist, steht im Fehlersatz von `_charge` selbst: **stornieren und neu stellen**; eine
  Minderung ohne Rücknahme (Kulanz) ist die Gutschrift **an** der Rechnung.
* **«Zahlung erfassen»** stand am Vorgang für den Fall «es gibt keine Rechnung» — den es
  nicht gibt: `can` führt `pay` erst, wenn eine Forderung gebucht ist (§9.12/#822), und
  ohne Forderung ist die Liste leer.

**Und die Gegenhandlung des Vorgangs ist keine Buchung**: «Auftrag stornieren» (`revoke`)
stand zwischen «Rechnung erfassen» und «Zahlung erfassen» und las sich als dritte Buchung.
Sie steht jetzt am **Ende der Karte**, neben dem Modul-Abschluss — die eine bringt den
Vorgang ans Ziel, die andere nimmt ihn zurück.

#### Drei Wege, das Geld zu bekommen — und sie stehen an der Rechnung

*«Im Grunde gibt es 3 Arten von Bezahlsystemen: Barzahlung, Zahlung per Karte und Zahlung
via Banküberweisung.»* (#865) — Sie sind **eine Angabe an der Zahlung**
(`deal_entries.method`), kein zweites Modell: gebucht wird in jedem Fall dieselbe Zeile.

| Weg | was das System tut | wer löst aus |
|---|---|---|
| **bar** | `pay` — aufschreiben, was geschehen ist | ein Mensch |
| **Karte** | `pay_online` — es geschehen lassen; gebucht wird vom Webhook | der Zahlende |
| **Überweisung** | **nichts** — es ist eine **Auskunft** (§9.14a) | der Zahlende, im E-Banking |

**Die Karte tippt niemand ab**: sie entsteht beim Zahlungsdienst und kommt über den
Webhook — von Hand erfasst wäre sie eine Behauptung ohne Beleg. `dm.MANUAL_METHODS` neben
`METHODS` (zwei Formen einer Regel), durchgesetzt an der **Menschentür** (`_pay`), nicht
nur im Formular.

►►► **Und alle drei stehen AN der Rechnung, die sie begleichen** (#859). ◄◄◄ *«Wie kann
ich bestimmen, welche Rechnung ich bezahle?»* — Gar nicht: die Knöpfe standen **unter**
der Liste, galten also dem Vorgang, und `stripe_pay.prepare` nahm `open_charges[0]`. Ein
Knopf **an** der Zeile beantwortet die Frage, indem er sie nicht stellt.

#### 9.14a Die QR-Rechnung — damit eine Überweisung nicht abgetippt wird

**Die ehrliche Antwort auf «international gültig»: einen weltweiten Standard gibt es
nicht.** Es gibt zwei, und einer deckt unseren Fall vollständig ab — die **Swiss
QR-Rechnung** (Pflicht seit 10/2022, jede Schweizer Banking-App liest sie; CH/LI-IBAN,
CHF oder EUR). Der **EPC-QR / GiroCode** für EUR an ausländische Konten ist dieselbe
Mechanik mit anderer Nutzlast: später eine Datei mehr, kein Umbau.

**Wo sie nicht gilt, gibt es sie nicht** — dann steht die Bankverbindung im Klartext da,
mit dem **Grund** daneben (`qrbill.problem`). Ein QR, der in der App des Kunden einen
Fehler wirft, wäre schlimmer als keiner.

**Die Referenz ist die Creditor Reference** (`RF…`, ISO 11649) aus unserer
Rechnungsnummer — strukturiert, international gültig und **ohne QR-IBAN**: die muss man
bei der Bank bestellen, und ohne sie ist die schweizerische QR-Referenz gar nicht erlaubt.
*Und sie sagt, woher sie kommt* (Testnotiz #871 — *«leitet sich diese von der
Rechnungsnummer ab?»*): der Trennstrich fällt weg, weil ISO 11649 nur Buchstaben und
Ziffern kennt (`100000886-1` → `RF…1000008861`) — ohne den Satz daneben sieht das nach
einer erfundenen Zahl aus, und genau daraus entstand die Rückfrage.

**Erzeugt wird sie im Backend**: die Nutzlast ist eine Liste von **einunddreissig Zeilen
in fester Reihenfolge**, und eine zweite Fassung im Browser wäre die Stelle, an der beim
nächsten Feld eine Zeile verrutscht — das sieht man einem QR nicht an.

**Wie GROSS er ist, entscheidet die Stelle, an der er steht** (#872). Er trug eine feste
Kantenlänge (240 px) und stand in einem 168 px breiten Kasten: 72 px zu breit, also ragte
er heraus und sass sichtbar ausser der Mitte (gemessen: Δ rechts −72 px). Das Bild nennt
jetzt nur noch sein **Seitenverhältnis** und füllt seinen Kasten — eine zweite Zahl im
Backend, die zur Breite im Browser passen muss, geht beim ersten Umbau auseinander. **Die
Ruhezone gehört dabei zum Code**, nicht zum Layout drumherum: vier Module ringsum
(ISO/IEC 18004), in der `viewBox`, damit sie mitskaliert; als Polsterung im Browser wäre
sie die zweite Stelle, an der jemand sie wegoptimiert.

#### Storno oder Gutschrift — dieselbe Buchung, zwei Wörter

*«Wenn bezahlt wurde, dann kann ich ja quasi nicht mehr stornieren.»* (#860) — Richtig:
eine Rechnung, auf die Geld geflossen ist, nimmt man nicht zurück, man **schreibt sie
gut**. Es ist dieselbe Gegenbuchung (§9.12, #823/#824); nur das **Wort** hängt an der
Zahl, und der Server sagt es (`DealEntryOut.reverse_word` aus `paid_on`) — eine zweite
Formel im Browser wiche ab und sähe trotzdem richtig aus.

**Erstattet wird auf dem Weg, auf dem gezahlt wurde**: bar und per Überweisung ist die
Erstattung eine gewöhnliche **negative Zahlung** (die es längst gibt); eine **Karte** gibt
nur der Dienst zurück, der sie belastet hat (`refund_online` → `stripe_pay.refund`).
Gebucht wird auch dort nicht dort: der Dienst meldet `charge.refunded`, und der Webhook
schreibt die Zeile.

**Und eine Zahlung auf eine inzwischen stornierte Rechnung wird trotzdem gebucht** — ohne
Zuordnung. Sie ist passiert; ein Ereignis der Aussenwelt macht man nicht ungeschehen
(§9.12, #842). Was daraus folgt, braucht keine eigene Regel: der offene Betrag wird
negativ — *wir schulden* —, und die Erstattung steht als Handlung da.


### 9.14b Der Betrag der Zusage ist die Summe seiner Positionen

►►► **Wo die POSITIONEN den Preis tragen, gibt es keine zweite Zahl.** ◄◄◄

Bei einer **Einnahme** nennen wir den Preis je Position (§9.12, MWSTG Art. 26), und der
Betrag des Vorgangs *ist* ihre Brutto-Summe (`gross_of`) — dieselbe Summe, aus der auch
Netto, Steuer je Satz und die anteilige Aufteilung einer Teilrechnung kommen
(`vat_split` / `split_for`). Der Zuschlag liess ihn trotzdem frei übersteuern, und damit
konnte derselbe Beleg zwei Dinge sagen: «Total 900» über einer Aufstellung, die auf 1000
aufgeht.

Eine abweichende Zahl wird darum **abgewiesen** — mit der richtigen im Satz —, nicht still
verworfen: eine stillschweigend ignorierte Angabe ist die unangenehmere Form, weil man ihr
nicht ansieht, dass sie nichts getan hat. Wer nachverhandelt, ändert den Preis **an der
Position**.

Bei einer **Ausgabe** nennt die Gegenpartei eine Summe (ihre Steuer steht auf *ihrer*
Rechnung); dort ist der Betrag die einzige Angabe, und ein Wert in der Nutzlast **ist** die
Nachverhandlung.

►►► **Und die Null ist eine Angabe — auch beim Zuschlag.** ◄◄◄ Die vereinbarte
Zahlungsfrist wurde als `_days(payload) or _days(line)` gelesen. Eine **null** aus der
Nutzlast ist aber genau die Vorauszahlung (§9.12, `PREPAID_DAYS`), und `0 or X` ist `X`:
wer «zahlbar sofort» vereinbarte, bekam still die Frist der Offerte — und damit ein Modul,
das ohne Zahlung abschliesst, obwohl Vorkasse verabredet war. Dieselbe Falle, gegen die
`_assert_terms` ausdrücklich auf `is None` prüft.

*Bewusst **nicht** getan: die vier Werte der Zusage (`party_id`, `amount`, `due_days`,
`agreed_lines`) durch einen blossen **Zeiger** auf die gewählte Angebotszeile zu ersetzen.
Sie sind keine Kopien **einer** Tatsache: `party_id` ist der Zeiger, und Betrag wie Frist
dürfen bei der Zusage abweichen — verhandelt wird auch am Telefon. Ein Zeiger sagte damit
weniger, nicht dasselbe: er überschriebe die Offerte mit der Zusage, und danach liesse sich
nicht mehr sagen, was der Partner ursprünglich angeboten hat.*

### 9.14c Die Karte IST der Beleg — und sie wächst

►►► **Ein Vorgang, ein Dokument.** ◄◄◄ (Testnotiz #899)

Die Ausführungsstelle des Geldvorgangs war eine **Kette von Abschnitten**: Positionen ·
Angebot · Auftrag · Geld. Mit der Zusage kam ein Block dazu, der Partner, Summe und
Fristen **noch einmal** zeigte — ein zweiter Beleg neben dem ersten, in anderer
Reihenfolge als der erste.

Gemeint war nie ein zweiter Beleg, sondern **derselbe, einen Schritt weiter**. Also steht
er in der Ordnung, die ein Beleg hat:

| Abschnitt | Was darin steht |
|---|---|
| **Belegkopf** | Belegart (Angebot ↔ Auftrag ↔ storniert) · Richtung als Symbol · *An <Partner>* · Zusagedatum · die Sperre «Erst zahlen» |
| **Positionen** | je Artikel eine Zeile mit Menge, Nummer, Satz, Preis — und darunter Netto, Steuer je Satz, Total |
| **Bedingungen** | Währung, Zahlungsfrist, Lieferfrist bzw. der Termin, der daraus folgt |
| **Rückläufe** | der Angebotsspiegel: wer was zu welcher Frist angeboten hat |
| **Rechnung & Zahlungen** | die Geld-Zeilen (§9.14) |
| **Handlungen** | unter einer Haarlinie, wie die Unterschrift |

**Er wächst, statt umzuschalten.** Die Belegart im Kopf **ist** der Fortschritt; die
Preisspalte trägt nach der Zusage die gebuchten Zahlen statt des Entwurfs, die Bedingungen
stehen als Auskunft statt als Feld, die Rückläufe klappen auf **eine** Zeile zusammen, und
darunter kommt das Geld dazu. Dieselben Zeilen, ein Zustand weiter — **ein späterer
PDF-Export ist damit dieselbe Ableitung ohne Knöpfe**, nicht ein zweiter Beleg, der beim
nächsten Feld ausläuft.

**Die Regel, die es zusammenhält, ist zählbar**: jede Beleg-Angabe steht an **genau einem**
Ort. Empfänger und Zusagedatum im Kopf, Zahlungsfrist und Liefertermin bei den Bedingungen,
Steueraufteilung und Nettosumme bei den Positionen. Und die **Summe** gibt es einmal: die
Vorschau aus getippten Preisen und die gebuchten Zahlen des Servers sind dieselbe
Aufstellung — zwei Bauteile wären zwei Schreibweisen für Netto, Steuer und Total.

**Zusammengeklappt wird erst NACH dem Zuschlag.** Solange verhandelt wird, versteckt der
Beleg nichts. Danach sind die unterlegenen Zeilen der **Nachweis**, warum so entschieden
wurde — er verschwindet nicht, er steht auf Klick.

**Die Zahlungsfrist steht über der Lieferfrist** (#897) — im Beleg wie an der
Angebotszeile, und auch in deren Anzeige. Sie ist die folgenreichere Angabe: aus ihr kommt
die Fälligkeit, und null heisst Vorauszahlung. Zwei Formulare für dieselben zwei Fragen
dürfen nicht anders herum fragen.


