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

