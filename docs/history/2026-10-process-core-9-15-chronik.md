# PROCESS_CORE §9.8–§9.15 – Chronik (Wortlaut bis Oktober 2026)

> **Archiv.** Diese Abschnitte standen bis zum 28.10.2026 in `PROCESS_CORE.md`, Wort für
> Wort: der entfallene Einkaufs-Beleg am Bewegen-Modul (§9.8), die entfernten Module
> «Ausliefern», «Beschaffen», «Verkauf» und «Zahlung (alt)» (§9.9 · §9.9a · §9.12–§9.14)
> und der Beleg mit seinen Unterabschnitten §9.15a–§9.15s. §9.15s («Umbau Oktober 2026»)
> ging §9.15a–r vor; was heute gilt, steht in `PROCESS_CORE.md` §9.15. Verweise im Code
> auf «§9.15a» … «§9.15r» meinen den Wortlaut hier.
>
> Einige Aussagen sind seither überholt (u. a. «es bewegt keine Stücke», `unbill`,
> «Verkauft hat keinen Schreiber», die Tabellen `deals`/`purchases`, die mit Migration
> `152` gefallen sind). Die vollständige frühere Fassung von `PROCESS_CORE.md` (mit den
> Testnotiz-Erzählungen und den Abschnitten zum Prozessbild vor `docs/prozessbild.md`)
> liegt im Commit `57aec14`.

---

#### Selbst gebracht oder eingekauft — der Beleg ist ENTFALLEN

Ein Transport, den eine Spedition fährt, ist eine **Leistung, die man einkauft**. Das
Bewegen-Modul trug dafür einmal denselben Einkaufs-Beleg wie das Beschaffen-Modul
(`Module.buys = BUY_IF_CHOSEN`), samt Schalter «Selbst ↔ Beschaffen» an der
Ausführungsstelle. Die Einsicht dahinter war richtig — *eine Sendung aufzugeben IST ein
Einkauf*: der Spediteur ist ein Lieferant, der Tarifvergleich ist der Angebotsspiegel.

**Mit den Handels-Modulen ist der Beleg gegangen** (§9.9a), und der Schalter mit ihm. Was
bleibt, ist die richtigere Form derselben Aussage: wer eine Spedition beauftragt, legt
einen **Geldvorgang** daneben (§9.12) — dieselbe Maschine, ohne die Bindung an Ware, und
mit demselben Angebotsspiegel. Das Bewegen-Modul selbst weiss davon nichts mehr; es
bewegt.

**Die frühere Liste `manuell · paket · fracht` bleibt ebenso entfallen** — *Paket* und
*Fracht* sind keine zwei Arten, sondern zwei **Angebote** desselben Einkaufs; das
entscheidet der Tarif, nicht der Modellierer. Ein Roboter, der es fährt, ist «selbst»:
unser Gerät, keine Rechnung.


### 9.9 Das Modul «Ausliefern» ist ENTFERNT

> **Status: gelöscht.** Es war das, was vom Verkaufs-Modul übrig blieb, nachdem der Beleg
> herausgenommen war — ein Scan und ein Statuswechsel auf `Verkauft`, sonst nichts. Eine
> Runde später ist auch das weg.

**Der Grund ist derselbe wie beim Beleg: es sagte nichts, was nicht schon dasteht.** Was
*physisch* geschieht, sagen die Module, die es tun — **«Bewegen»** bringt das Stück zum
Kunden, **«Zahlung»** (§9.12) regelt das Geld. «Das Stück gehört jetzt jemand anderem»
ist die **Folge** aus beidem, kein eigener Vorgang. Ein Modul, dessen ganze Aussage eine
Folge ist, beschreibt nichts; es verlangt nur einen zusätzlichen Scan dafür, dass jemand
sie aufschreibt.

#### Der Status `Verkauft` bleibt — und das ist kein Widerspruch

Er hat heute **keinen Schreiber** mehr. Er steht trotzdem im `CATALOG`, und das ist die
eine Stelle, an der «was nicht gebraucht wird, ist weg» nicht gilt:

> **Der Statuskatalog ist nicht nur die Liste dessen, was ENTSTEHEN kann — er ist das
> Vokabular, in dem der append-only Ereignis-Log geschrieben ist.**

Jedes Stück, das je ausgeliefert wurde, trägt das Wort in seiner Zeile und in seiner
Geschichte. `flow._left_with` liest es von dort (§8.1a), die Bestandsleiste gruppiert
danach (§10.3). Ihn zu streichen machte Vergangenes nicht ungeschehen, sondern
**unlesbar** — und eine Ansicht meldete einen Zustand, den sie nicht kennt. Dieselbe
Regel wie bei den Tabellen der entfernten Bereiche.

**Und die Retoure bleibt, was sie war**: ein ganz gewöhnlicher Auftrag, der das Stück
greift — **das Greifen IST die Rücknahme**. Sie hing nie an diesem Modul.


### 9.9a Die Module «Beschaffen» und «Verkauf» sind ENTFERNT

Sie sind nicht abgeschaltet, sondern gelöscht — mit ihrem Beleg, ihren Tabellen und ihren
Diensten (`domain/procurement`, `domain/money`, `services/purchase`, `services/invoices`,
`services/payments`, `models/purchase`, `models/invoice`, `models/payment`,
`components/erp/purchase-work.tsx`).

**Der Grund ist keine Geschmacksfrage, sondern eine Doppelung.** Der Beleg dieser Module
war Angebot → Zusage → Erfüllung mit Angebotsspiegel, Rechnungen, Zahlungen und Storno.
Genau das ist der **Geldvorgang** (§9.12) — nur ohne die Bindung an Ware, und damit auch
für Miete, Lohn, Gebühr, Spesen und eine eingekaufte Spedition brauchbar. Zwei Maschinen
für dasselbe Geschäft laufen beim ersten neuen Verb auseinander.

**Was an ihre Stelle tritt:**

| war | ist jetzt |
|---|---|
| «Beschaffen»: anfragen, bestellen, Wareneingang | ein **Geldvorgang** (Ausgabe) plus die Module, die das Material physisch bewegen |
| «Verkauf»: anbieten, zusagen, liefern | ein **Geldvorgang** (Einnahme) plus die Module, die das Material physisch bewegen |
| Einkauf **in** einem Bewegen-Modul (Spedition) | ein Geldvorgang neben dem Bewegen-Modul |
| Rechnungen und Zahlungen am Beleg | die Geld-Zeilen des Vorgangs (§9.12) |

**Stripe ist geblieben** (`services/stripe_pay`, `docs/stripe-setup.md`): der Webhook
schreibt eine Geld-Zeile am **Vorgang** statt am Beleg. Das Bedienelement, das mit der
Beleg-Karte verschwunden war, ist inzwischen wieder da — und zwar als **eigene Bezahlkarte
im ERP** statt als Zahllink (§9.13).

Die Tabellen `purchases`, `invoices` und `payments` bleiben stehen (Zwei-Deploy-Regel,
`docs/backlog.md`): eine Spalte, die niemand liest, kostet nichts; ein Tabellen-Drop
kostet die Vergangenheit.


### 9.12–9.14 Der Vorgänger «Zahlung (alt)» ist ENTFERNT — was davon weiter gilt

> **Status: gelöscht** (Testnotiz #960). Die Abschnitte §9.12–§9.14c beschrieben das
> `deal`-Modul (`domain/deal`, `services/deal`, `deal-work.tsx`); ihr Wortlaut liegt
> unverändert in `docs/history/2026-09-zahlungsmodul-vorgaenger.md` (Anhang). Gebaut ist
> heute allein der **Beleg** (§9.15, Schlüssel `beleg`, Beschriftung «Zahlung»).

Diese Entscheidungen entstanden dort und gelten im Beleg unverändert:

- **Geld mit einer zweiten Partei, in beide Richtungen EIN Modul** (Einnahme ↔ Ausgabe als
  Einstellung, nicht als zweiter Modul-Schlüssel) – und **es bewegt keine Stücke**: ein
  Durchläufer (`Im Prozess` → `Im Prozess`), darum muss keine andere Regel von ihm wissen.
- **`can` ist Auskunft UND Tor**: dieselbe Tabelle zeigt die Knöpfe und weist ab.
- **Ableitung statt Spalte**: *offen*, *fällig*, *überfällig* rechnen sich aus Beträgen und
  Daten; eine gespeicherte «offen»-Spalte wäre die zweite Wahrheit.
- **Bezahlt wird BEI UNS** (vormals §9.13): eigene Bezahlkarte im ERP (Payment Element),
  gebucht wird nur vom Webhook; der Anbieter steht nicht im Geldvorgang
  (`core/config.payment_service_ready`). Einrichtung: `docs/stripe-setup.md`.
- **Eine Rechnung je Modul** (vormals §9.14) – seit §9.15q keine Regel mehr, sondern die
  Struktur: der Beleg IST die Rechnung. Eine Anzahlung ist ein zweites Modul mit eigenen
  Positionspreisen.
- **Drei Wege zum Geld** (bar · Überweisung · Karte); die Überweisung ist eine Auskunft
  (Bankverbindung, RF-Referenz, Swiss QR-Rechnung), keine Buchung (§9.15i).
- **Die Karte IST der Beleg und wächst** (vormals §9.14c): dieselben Zeilen, ein Zustand
  weiter – keine zweite Darstellung nach der Zusage.


### 9.15 Der Beleg — das Zahlungsmodul, neu aufgebaut

> `docs/history/2026-09-neuaufbau-zahlungsmodul.md` · `domain/voucher` · `services/voucher` ·
> Tabellen `vouchers` · `voucher_quotes` · `voucher_lines` · `voucher_entries` ·
> Migration `134`

**Fachlich dasselbe wie §9.12–§9.14**: Geld mit einer zweiten Partei, in beide Richtungen
dieselbe Maschine, drei Achsen ohne Reihenfolge, `can` als Auskunft **und** Tor, und die
eine Regel, aus der die Robustheit folgt – **es bewegt keine Stücke.**

**Neu ist die FORM**, an drei Stellen, an denen der Vorgänger die Hälfte seiner Zeilen
verbraucht hat:

| | Vorgänger (`zahlung`) | Neu (`beleg`) |
|---|---|---|
| Angebotsspiegel | JSONB an der Kopfzeile, bei jeder Änderung neu gebaut | eine **Tabelle** |
| Position | **drei** Formen (abgeleitet · je Angebot kopiert · eingefroren), 21 Fundstellen | **eine** Tabelle; eingefroren durch die **Stufe** |
| Ein Verb | **vier** Deklarationen (`ACTIONS` · `REQUIRED_FOR`/`_UP_TO` · `HANDLERS` · `party_actions`) | **eine** Zeile in `VERBS` |

**Drei Spalten sind Ableitungen geworden**: *mit wem* · *was vereinbart ist* · *welche
Zahlungsfrist* stehen an der **gewählten Angebotszeile** (`state = gewaehlt`). Am
Vorgänger standen sie daneben und wurden beim Zuschlag hineinkopiert – damit konnte
derselbe Beleg zwei Dinge sagen, und eine eigene Regel musste den Widerspruch verhindern.
Als Ableitung kann er **nicht entstehen**.

**Ein neues Verb: `price`.** Die Positionen zu bepreisen ist eine eigene Handlung, nicht
ein Nebeneffekt des Anfragens. Damit gilt die Hausregel «gespeichert, nicht abgeschickt»
auch für das Herzstück des Belegs: man tippt, es wird gespeichert, und `ask` schickt es
hinaus.

**Die Positionen gehören dem BELEG, nicht der Angebotszeile.** Ein Beleg hat *einen* Satz
Positionen mit *einem* Satz Preise – zwei Kunden zwei verschiedene Preise anzubieten sind
zwei Angebote, also zwei Belege. Beim Vergleich mehrerer Lieferanten (der eigentliche
Zweck des Spiegels) nennt ohnehin jeder eine **Summe**, und die steht an seiner Zeile.

**Der Vorgang bleibt am SCHRITT**, nicht am Auftrag: ein Auftrag kann eine Einnahme *und*
eine Ausgabe tragen (wir kaufen Material, wir verkaufen das Produkt) – «ein Vorgang je
Auftrag» bräuchte sofort die Regel «je Richtung». Und dass eine Anzahlung ein **zweites
Modul** ist, bleibt richtig: drei Zeitpunkte sind drei Punkte im Prozess (§9.14).

►►► **Und der Vorgänger ist gelöscht** (Testnotiz #960). ◄◄◄ *«Dieses Prozessschrittmodul
kann vollständig und gänzlich aus dem Code eliminiert werden wie bereits geplant.»* – Es
war ein **Löschen**, kein Umbau, und genau dafür wurde dieses Modul **neben** ihn gebaut
statt in ihn hinein: gefallen sind `domain/deal` · `services/deal` · `schemas/deal` ·
`models/deal` · `deal-work.tsx`, der Modul-Eintrag, fünf Endpunkte, fünf API-Methoden und
54 Wächter, die seine Form prüften. **Hier keine Zeile.** Die befristete Doppelung des
Steuerkatalogs ist damit aufgelöst, und es gibt wieder genau eine Fassung.

*Die Tabellen `deals`/`deal_entries` bleiben stehen* – dieselbe Regel wie bei jeder
Alt-Tabelle: eine Spalte, die niemand liest, kostet nichts; ein Tabellen-Drop kostet die
Vergangenheit und verlangt vorher eine Sicherung der produktiven Datenbank
(`docs/backlog.md`).

#### 9.15a Was auf dem Beleg steht, ist Pflicht

> Testnotiz #964 · `voucher._assert_complete` · `.ix-editable.is-missing`

*«Alle Eingabefelder hier in diesem Modul – also alles, was so leicht blau hinterlegt ist –
sollen Muss-Felder sein.»* «Leicht blau hinterlegt» **ist** die Auszeichnung änderbarer
Werte (§9.15, `.ix-editable`), also gilt die Regel jedem Wert, den der Beleg trägt: Preis
und Steuersatz je Position, die beiden **Zoll**-Angaben, die beiden **Fristen** und die
**Lieferbedingung** samt ihrem Ort.

**Geprüft wird an der EINEN Stelle, an der er nach aussen geht** (`ask`) – nicht bei jedem
Tippen: der Beleg *entsteht* unvollständig, und eine Meldung dabei sagte nur, dass man noch
nicht fertig ist. Die rote Tönung im Browser ist die **freundliche Hälfte** derselben
Regel, nie ein zweiter Massstab (dieselbe Bauart wie `pick_problem`/`unpickable`).

**Gelesen wird der Wert, der auf dem Beleg STEHT** – die Zeile, wo sie etwas trägt, sonst
der Artikel. Die rohe Spalte zu prüfen hiesse, eine Angabe zu verlangen, die sichtbar längst
dasteht. Und **der Satz nennt die Position**: «Ohne Zolltarifnummer …» über einem Beleg mit
zwölf Zeilen ist eine Sackgasse mit Ausrufezeichen.

*Die eine benannte Folge: die Zoll-Angaben sind Pflicht **auch im Inland**. Man könnte sie
am Ziel festmachen (Empfängerland ≠ Ausstellerland), aber ein Pflichtfeld, das je nach
Empfänger eines ist oder nicht, ist keins – sondern eine Regel, die man erst beim Scheitern
kennenlernt. Sie stehen ohnehin am **Artikel** und reisen von dort auf jeden Beleg: wer sie
einmal pflegt, tippt sie nie wieder.*

#### 9.15b Der Belegkopf nennt gar keine Belegart

> Testnotizen #974 · #977

Im Kopf stand an einem **erledigten** Vorgang «Erledigt» – ein Zustand, kein Beleg. Der
erste Anlauf machte daraus die **Belegart** («Offerte» · «Auftragsbestätigung»), und das
war die Auslegung einer Ablehnung: #974 hiess *«ich möchte, dass diese Anzeige
verschwindet»*, und #977 hat es wiederholt.

**Sie sagt oben auch nichts, was die Karte nicht schon sagt**: wie weit der Beleg ist,
steht als Punkt an **jedem** Abschnitt (`ModuleSection state`), und was als Nächstes zu tun
ist, steht auf dem Knopf, der es tut. Damit hatte `Direction.document_label` keinen Leser
mehr – und eine Auflösung ohne Leser ist die zweite Wahrheit, die beim nächsten Umbau
abweicht; sie ist mitsamt `VoucherEmbed.stage_label` entfallen.

**Der Storno bleibt.** Er ist keine Belegart, sondern eine **Tatsache** über dieses Papier
(`cancelled_on`), und er steht sonst nirgends: *der Beleg behält seinen Weg.* `label_of`
bleibt unverändert daneben – eine Fehlermeldung über die Stufe muss die Stufe nennen
dürfen. **Zwei Fragen, zwei Antworten.**

#### 9.15c Eine Chronik gibt es nicht — die Daten stehen an ihrem Ort

> Testnotizen #968 · #969 · #970

*«Die Chronik kann vollständig und gänzlich entfallen. Ich möchte die Information dort
darstellen, wo sie eigentlich angezeigt werden.»* Sie zählte **zwei Daten** auf, und beide
haben einen eigenen Ort: *wann offeriert wurde* am Kopf der Angebote, *wann zugesagt wurde*
an der Zeile, bei der zugesagt wurde, *wann storniert wurde* im Belegkopf. Ein Abschnitt,
der dieselben Daten ein zweites Mal nennt, ist nicht der Nachweis, sondern seine ärmere
Kopie: nacktes Datum statt Aussage.

**Die Aussage steht da, die Tatsache im Hover** («vor 3 Tagen offeriert» ↔ Datum und
Uhrzeit) – dieselbe Regel wie bei der Fälligkeit einer Geld-Zeile (§9.14).

**Und der Moment brauchte keine Spalte**: `created_at` einer Angebotszeile *ist* der
Moment, in dem sie hinausging (`_ask` legt sie genau dort an und nirgends sonst), und
`updated_at` der **gewählten** Zeile ist der Moment des Zuschlags (`_agree` setzt `CHOSEN`
in einem Zug mit der Stufe, und danach fasst kein Verb sie mehr an). `sent_on` bleibt
daneben: das ist das **Datum auf dem Papier** – ein Beleg trägt einen Tag, keine Uhrzeit.

#### 9.15d Die Gegenpartei: eine Liste, eine Form

> Testnotiz #962 · `voucher._possible_parties`

Dieselbe Sache stand in **zwei** Formensprachen da: eine angefragte Partei als Chip mit
Zustandspunkt und ✕, eine zugelassene, noch nicht angefragte als `+ Name`-Knopf – und der
trug ausgerechnet `.ix-editable`, die Auszeichnung **änderbarer Werte**. Damit sah *jede*
Partei dauerhaft «aktiv» aus, und ob eine angefragt war, war an der Form nicht abzulesen.

**Ein Chip je möglicher Gegenpartei**, und eine Anatomie: Punkt (gefüllt = angefragt ↔
hohler Ring), Name, Handlung (`+` fragt an, `✕` zieht zurück). Der **Name zeigt die
Anschrift** – immer, auch bei einer noch nicht angefragten: im Offertenschritt ist niemand
angefragt, und die Anschrift will man sehen, **bevor** man anbietet. `recipients` trägt
darum die **Vereinigung** zugelassen ∪ angefragt; eine zweite Abfrage braucht es nicht.

**Und die Liste hängt nicht mehr an `ask`.** Sie stand nur da, solange man anfragen
*durfte* – fehlte eine Stammdatenangabe, verschwand mit dem Anfragen auch das Abwählen und
die Anschrift. Was man **tun** darf, entscheidet weiterhin `can`, je Chip; was man **sehen**
darf, ist eine andere Frage.

#### 9.15e Ein Feld stellte zwei Fragen — darum sind es zwei

> `domain/voucher.TASK` · `ORDER_REF` · `Direction.party_ref` · `Beleg.INSTRUCTION`

*«Bei Einkaufsteilen ist es oft ‹gemäss Spezifikation›, aber wenn ein intern gefertigtes
Teil auswärts nachbearbeitet werden muss, soll dieses Feld dafür genutzt werden … bei der
Verkaufsabwicklung habe ich keine Ahnung, was ich dort reinschreiben soll. Es ist ein
Mussfeld – die Logik geht bei Verkaufsteilen nicht auf.»*

Die Pflichtangabe **je Partner** meinte zwei verschiedene Dinge, und darum war sie in der
einen Richtung sinnvoll und in der anderen unbeantwortbar:

| | gehört zu | Pflicht? | wo? |
|---|---|---|---|
| **Was ist zu tun?** («Härten auf 58 HRC») | dem **Modul** – der Satz lautet für jeden Partner gleich | **nein**, leer heisst «gemäss Spezifikation» | `config.instruction` |
| **Wie bestellen?** (seine Artikelnummer, sein Shop-Link) | der **Paarung** Modul × Partner – derselbe Lieferant führt je Teil eine andere Nummer | **ja** – aber nur, wo wir bestellen | `config.parties[].ref` |

**Der Ort bleibt die Definition**, und das ist die Antwort auf die Frage dahinter: in einem
Fertigungsprozess wird **vorher** definiert, was zu tun ist; am Band wird er abgearbeitet
(§4). Was ein Mensch erst zur Laufzeit weiss, gehört nicht hierher – aber «Härten auf
58 HRC» weiss er beim Modellieren.

**Leer ist eine vollständige Aussage, keine fehlende Angabe.** *Was* gehandelt wird, sagt
der Beleg über seine Positionen und deren Spezifikation; der Satz ergänzt nur, was daraus
nicht hervorgeht. Ein Pflichtfeld, das bei der Hälfte der Vorgänge nichts aufzunehmen hat,
lädt zu einer Eingabe ein, die niemand liest – und beim Verkauf gab es darauf gar keine
richtige Antwort.

**Die zweite Frage hängt an der RICHTUNG** (`Direction.party_ref`), nicht an einem `if` im
Dienst: beim Verkauf liefern **wir**, also gibt es sie dort nicht, und ein trotzdem
gesendeter Wert wird **verworfen**. Jede künftige Richtung erbt die Regel, und die
Oberfläche fragt eine Angabe statt einen Schlüssel zu vergleichen.

#### 9.15f Beide Anschriften, auf beiden Seiten, immer

> Testnotizen #952 · #975 · `voucher._addresses`

*«Standardmässig immer bei Informationen ausweisen, global etablieren, auch wenn sie
zweimal das Gleiche anzeigt. Eine Logik für alles, Komplexität und If/Else verringern.»*

Ein Beleg stellt zwei Fragen – *wohin die Rechnung, wohin die Ware* – und stellt sie auf
**jeder** Seite gleich. Bis hierher standen die Beschriftungen nur auf der Gegenseite und
nur dort, wo die beiden sich unterscheiden: **zwei** Bedingungen für eine Frage, die immer
gleich lautet – und die eine verbliebene Zeile beantwortete danach keine der beiden
erkennbar.

**Eine Regel für beide Seiten**: gibt es nur eine Anschrift, steht sie unter beiden
Beschriftungen. Das ist die Auskunft «an dieselbe», nicht eine Doppelung. **Wo gar keine
dasteht, gibt es auch keine Beschriftung** – dort sagt die Seite, dass sie fehlt; eine
Beschriftung über einer Lücke wäre eine leere Behauptung.

Erfunden wird weiterhin nichts: die zweite Zeile entsteht nur aus Angaben, die am Benutzer
stehen (Rechnungsadresse ≠ Hauptadresse).

#### 9.15g Die dominante Handlung — und daneben die leise

> Testnotiz #976 · `beleg-work.StageRow`

*«Kann man diesen Bereich ähnlich darstellen wie ‹Vorgang abschliessen› und daneben das
unscheinbarere Abbrechen?»* – Gemeldet an der **Angebotszeile** (annehmen ↔ absagen), und
damit ist es keine Eigenschaft einer Zeile, sondern die **Anatomie einer Entscheidung** auf
diesem Beleg: eine Handlung bringt ihn weiter und nimmt den Platz, alles andere steht als
Quadrat daneben und klappt beim Zeigen seinen Namen aus.

Sie steht darum **einmal** – die Fusszeile der Karte (Abschluss ↔ Storno, §9.14) und der
Zuschlag an einer Angebotszeile sind dieselbe Zeile. **Welche die dominante ist, sagen die
Daten**: annehmen, sobald ein Preis dasteht; sonst ihn erfassen. Eine Offerte zu
*korrigieren*, während man sie annehmen könnte, ist der Nebenweg.

#### 9.15h Eine Blase steht über dem, was sie erklärt

> Testnotiz #978 · `beleg-work.Note`

*«Kann das nicht irgendwo neben dem Betrag oder so stehen – und den Hovertext direkt
darüber und nicht wie jetzt irgendwo.»* – **Zwei Meldungen, eine Ursache.** Die Blase des
Hauses sitzt über der **Mitte ihres Elements** (`[data-tip]::after`, `left: 50%`); nur war
das Element nicht die Auskunft, sondern die ganze Zeile: ein Kind einer Flex-**Spalte** wird
blockifiziert und auf die volle Breite gezogen. Bei 460 px stand die Blase einen halben
Beleg neben den drei Wörtern, die sie erklärt.

`width: fit-content` ist die Antwort und **nicht** `align-self` – dieselbe Lehre wie bei
`Editable` (§9.15, #961/#963): eine **definite** Quergrösse wirkt in der Spalte *und* in der
Zeile. Gemessen: Box == Text, Δ 0,00 px; die Bug-Form meldet 1146 px.

#### 9.15i Rechnung & Zahlung — zwei Fächer, eine Handlung, eine Wahl

> `docs/konzept-beleg-shop-besitz.md` · `beleg-work.Money` · `voucher._ways`

*«Irgendwie scheint mir dieser Bereich zu komplex, zu unstrukturiert, zu wirr, zu viele
Optionen, die sich gegeneinander stören, kannibalisieren.»*

**Gezählt, nicht vermutet.** An einer Rechnung standen bis zu **sechs** gleich aussehende
Knöpfe mit **drei** Bedeutungen — eine Buchung («Rechnung erfassen»), eine Korrektur
(«Stornieren») und eine blosse **Auskunft** («Überweisen» zeigt IBAN und QR und bucht gar
nichts). Dazu standen **zwei Rollen** in einer Zeile: «Rechnung erfassen» ist unsere
Handlung, «Jetzt bezahlen» die des Zahlenden. Und einen **Fortschritt** gab es nicht,
obwohl es drei klare Zustände gibt: *nichts gefordert → gefordert → bezahlt.*

**(1) Zwei Fächer statt einer Knopfreihe.** Es sind zwei Fragen, und jede gehört genau
einer Seite:

| Fach | Frage | Wem es gehört |
|---|---|---|
| **Fordern** | Was schuldet uns jemand? | uns — stellen, stornieren, gutschreiben |
| **Begleichen** | Wie kommt das Geld hierher? | dem Zahlenden — bar · Überweisung · Karte |

Beide sind ein gewöhnlicher `ModuleSection` und tragen damit denselben Fortschritts-Punkt
wie jeder andere Abschnitt des Belegs. Dazwischen die Zeile **«Offen»** — das Ergebnis von
*gefordert minus beglichen*. Der frühere gemeinsame Titel «Rechnung & Zahlung» ist
**entfallen**: er fasste zwei Fragen zu einer Überschrift zusammen, und genau daraus kam
die Unordnung.

**(2) Genau eine Handlung bringt weiter** — unten, breit, als `StageAction` (dasselbe
Bauteil wie der Zuschlag und der Modul-Abschluss, §9.15): *Rechnung stellen* → *Zahlung
erfassen* → nichts mehr. Alles andere ist eine **Korrektur** und steht klein bei der Zeile,
die sie korrigiert — nie im selben Rang. Welche gerade dran ist, folgt aus `can` und
`credit_only`; ein Rang, den die Oberfläche selbst vergäbe, wäre die zweite Regel daneben.

**(3) Der Weg zum Geld ist eine WAHL, kein Verb.** Bar · Überweisung · Karte sind drei
Antworten auf **eine** Frage; was dahinter passiert, ist verschieden (buchen ↔ Angaben
zeigen ↔ Zahlformular öffnen), die Frage ist dieselbe. Als drei Knöpfe standen sie im
selben Rang wie eine Buchung und wie eine Korrektur.

Welche Antworten es gibt, sagt der Server (`ways`, abgeleitet aus `can`), und **jeder Weg
sagt selbst, was er auslöst** (`action`/`verb`) und **ob er eine Auskunft mitbringt**
(`info`). Beides leer heisst *reine Auskunft* — so sieht die Gegenpartei die Überweisung,
und dort steht kein Knopf, der nach Buchung aussieht. Ein Vergleich auf den Schlüssel
«transfer» in der Oberfläche wäre der Spiegel über die API-Grenze, der beim nächsten Weg
still falsch wird.

**Und welche Rechnung gemeint ist, sagt der Dienst** (`settle_charge`): je Modul lebt
höchstens **eine** offene Forderung (§9.14), die Frage hat also genau eine Antwort. Sie in
den Zeilen zu suchen wäre die zweite Regel neben `open_charges` — genau daraus kam #859.

**«Rechnung STELLEN» ↔ «Rechnung ERFASSEN»** (`Direction.charge_verb`): bei einer
**Einnahme** entsteht der Beleg hier, bekommt unsere Nummer und geht hinaus; bei einer
**Ausgabe** schreiben wir ab, was der Lieferant geschickt hat. Die **Zahlung** wird in
beiden Richtungen *erfasst* — das System bucht eine Zeile, es überweist nichts.

*Bewusst nicht gebaut und benannt: die **Automatisierung** (Bank-Datei camt.053,
Mahnliste) und die **Zustellung** (PDF, E-Mail). Beides steht im Konzept.*

#### 9.15j Die zweite Anschrift heisst je Rolle anders

> Testnotiz #979 · `voucher._addresses`

*«Beim Leistungserbringer wäre es evtl. besser/richtiger zu sagen Absendeadresse oder so?
Etabliere hier korrektes.»*

«Lieferadresse» heisst *wohin geliefert wird* — an der eigenen Anschrift des
**Leistungserbringers** stand damit, man möge **ihm** dorthin liefern, während er
derjenige ist, der liefert. Von seiner Seite aus geht die Ware **ab**: das ist die
**Versandadresse** (im Handel, in der Logistik und im Zoll ist der *Versender* die
Gegenrolle des Empfängers).

**Nur diese eine Beschriftung ist rollenabhängig**, und das ist Absicht: die
«Rechnungsadresse» beantwortet auf beiden Seiten dieselbe Frage — *welche Anschrift gilt
in Rechnungssachen* —, und so steht sie auch auf jedem gedruckten Beleg. Ein zweites Wort
dafür wäre eine Unterscheidung ohne Unterschied.

Die Rolle wird **nicht übergeben, sondern gelesen**: `document_head` kennt sie als
`flow.collects`, `their_side` leitet sie selbst ab (`not collects`). Ein Parameter wäre
eine Angabe, die jeder der beiden Aufrufer einzeln falsch setzen kann.

#### 9.15k Die Auswahl der Gegenpartei steht über ihrer Rolle

> Testnotiz #981 · `beleg-work.Party`

*«Gefühlt sollte die Auswahloptionen oberhalb vom Headline Leistungsempfänger stehen und
dann je nachdem was angewählt wurde unterhalb der Headline die Angaben geladen werden.»*

Die Chips standen **in** der Namenszeile, also unter der Rolle und an genau der Stelle, an
der sonst der Name steht: sie **ersetzten** die Angabe, die sie auswählen. Über der Rolle
ist es die Reihenfolge des Lesens — erst *wen meine ich*, dann *was gilt für ihn*.

Das Raster bekommt dafür eine achte Zeile (`PARTY_ROWS`), und auf unserer Seite bleibt sie
**leer**: die Symmetrie ist die Aussage, nicht die Dichte (§9.15, #913). Nach dem Zuschlag
gibt es nichts mehr zu wählen — dann ist die Zeile leer, und die unterlegenen Angebote
stehen als Nachweis in ihrem Abschnitt.

#### 9.15l Ein Eingabefeld nennt sich, während man tippt

> Testnotiz #982 · `beleg-work.Customs`

*«Im fertigen Beleg steht eigentlich immer ‹Zolltarif xy, Ursprung xy› — hier bei der
Eingabe steht einfach nur das Eingabefeld, aber der entsprechende Text nicht davor. Das
ist eine unerlaubte Abweichung von unserer Logik.»*

Der Name stand als **Platzhalter** im Feld — also an der Stelle, an der eine Oberfläche
sagt «hier ist nichts» — und verschwand beim ersten Zeichen. Die Regel dieses Belegs
lautet *der gedruckte Wert IST das Bedienelement* (§9.15, #922): was man ändert, muss
aussehen wie das, was gedruckt wird. Beschriftung und Wert stehen darum in **beiden**
Zuständen als eine Zeile, in derselben Grösse und Farbe; die Auszeichnung trägt allein der
Wert, denn nur er ist änderbar.


#### 9.15m Jede Angabe des Belegs hat ihr Verb

> Testnotiz #985 · `voucher._terms` · Migration `135`

*«Eingaben in ‹Zahlungsfrist› und ‹Lieferfrist› werden nicht persistiert — nach einem
Reload sind sie wieder weg. Der Fix muss für beide Felder und alle weiteren Feldtypen im
Modul gleichermassen greifen.»*

Und die Ursache war **keine Eigenheit dieser zwei Felder**: beide Fristen existierten
ausschliesslich an der **Angebotszeile**, und die entsteht erst mit dem Anfragen. Vorher
gab es im ganzen Datenmodell keinen Ort für sie — getippt lebten sie im Browser und
reisten allein in der Nutzlast von `ask` mit.

Damit waren sie die **einzige** Angabe des Belegs ohne eigenes Verb: Währung, Aussteller,
Lieferbedingung, Preis, Steuersatz und die beiden Zoll-Angaben werden längst sofort
geschrieben. Der Fix schliesst darum die Lücke, statt zwei Felder zu flicken — die Regel
lautet: **jeder änderbare Wert auf dem Beleg wird sofort persistiert, und keiner lebt nur
im Browser.**

- **Der Entwurf steht am Beleg** (`vouchers.lead_days`/`payment_days`), die **Vereinbarung**
  weiterhin an der gewählten Angebotszeile. Keine zwei Wahrheiten, sondern zwei
  **Zeitpunkte**: was wir anbieten wollen, und was zugesagt wurde. `due_days_of` /
  `lead_days_of` lesen die Zusage und fallen auf den Entwurf zurück — die Reihenfolge *ist*
  die Regel.
- **`ask` liest den Beleg**, nicht die Nutzlast: das Angebot ist die Kopie der Fristen,
  genauso wie der Betrag die Kopie der Positionen ist. Ein gesendeter Wert wird
  **verworfen**.
- **Geprüft wird beim Hinausgehen, nicht beim Tippen** (`_assert_terms` in `_ask`/`_quote`):
  ein Beleg entsteht unvollständig, und eine Meldung dabei sagte nur, dass man noch nicht
  fertig ist.

#### 9.15n Der Zustand einer Forderung — abgeleitet, mit Toleranz

> Testnotiz #991 · `domain/voucher.charge_state`

*Offen · Teilweise bezahlt · Beglichen · Überfällig · Überzahlt · Storniert* — aus **zwei
Zahlen** (Betrag der Rechnung und Rest), **null Spalten**. Ein gespeichertes Zustandsfeld
wäre die zweite Wahrheit, und die eine vergessene Nachzieh-Stelle fällt erst auf, wenn
jemand mahnt.

- **Rundungstoleranz `0.05`**: bei einer Auslandsüberweisung bleiben Rappen liegen, und
  eine Rechnung, die wegen drei Rappen für immer «offen» heisst, ist keine Auskunft,
  sondern eine Mahnliste voller Geister. Die Zahl steht im Fachmodell, nicht in der
  Oberfläche — sie ist eine fachliche Entscheidung, und wer mahnt, liest denselben Zustand.
- **Gerechnet wird mit dem Vorzeichen**, nicht mit «grösser null»: eine **Gutschrift** ist
  eine negative Rechnung (§9.11), und «offen < 0 heisst überzahlt» nennte jede unbeglichene
  Gutschrift «Überzahlt». Überzahlt ist, wo Rest und Betrag **verschiedene** Vorzeichen
  tragen.
- **Drei Töne, die des Hauses** (`done` · `pending` · `danger`). Eine vierte Farbe für Geld
  wäre eine zweite Farbsprache — und ein Zustand, den sonst niemand im ERP lesen kann.
  *Storniert* ist rot wie jeder «Stopp»-Zustand (dieselbe Lesart wie *inaktiv*).

►►► **Die Überzahlung ist ein GUTHABEN, und dafür braucht es nichts Neues.** ◄◄◄ Der
negative offene Betrag **ist** die Zahl — mit Vorzeichen, in derselben Spalte. Eine eigene
Guthaben-Tabelle wäre ein zweites Modell für etwas, das schon dasteht, und sie müsste bei
jeder Buchung nachgezogen werden. Zurückgezahlt wird über den Weg, auf dem gezahlt wurde:
eine gewöhnliche **negative Zahlung** (bar, Überweisung) bzw. `refund_online` (Karte).
**Verrechnet wird ein Guthaben nie automatisch** — welche Rechnung es mindern soll, weiss
nur ein Mensch.


#### 9.15o Wählen ist nicht anfragen

> Testnotiz #1000 · `services/voucher._add_party` · Migration `136`

*«Wurde beim Anlegen kein Partner vorgewählt, lässt er sich nachträglich nicht mehr
setzen. Die Auswahl wird korrekt angezeigt, aber nicht übernommen/persistiert.»*

**Nachgestellt über die echten Dienstpfade, und die Ursache ist strukturell.** Die Wahl im
freien Feld löste unmittelbar `ask` aus — und das ist die Handlung, mit der der Beleg
**nach aussen** geht: sie verlangt Preis, beide Fristen und die Lieferbedingung
(§9.15a/§9.15m). An einem frischen Modul fehlt davon naturgemäss alles, der Dienst wies
mit einem Satz ab, und die Wahl war weg.

Damit war *«wen meine ich»* die letzte Angabe des Belegs **ohne eigenes Verb**. Die Regel
gilt unverändert: **jeder änderbare Wert des Belegs wird sofort persistiert**, und was
nach aussen geht, ist eine eigene, ausdrückliche Handlung.

- **Drei Quellen, eine Liste** (`_possible_parties`): die **zugelassenen** aus der
  Definition (eine Vorlage für jeden künftigen Auftrag), die **gewählten** am Beleg
  (`vouchers.parties`) und die **angefragten** aus dem Spiegel. Ohne Dubletten.
- **Warum eine Liste und keine Tabelle.** `config.parties` steht eine Ebene höher in
  derselben Form: eine Liste von Objektnummern, ohne Eigenschaften und ohne Zustand. Was
  **hinausgegangen** ist, bleibt eine Zeile (`voucher_quotes`) mit Betrag, Fristen,
  Zustand und Datum — genau diese Trennung war der Grund des Neuaufbaus, und sie bleibt.
- **Geprüft wird die Wahl selbst**, nicht die Reife des Belegs (`_party`): dass es die
  Nummer gibt, dass sie zu einem Datensatz gehört, mit dem man handeln kann, und dass die
  Definition sie nicht ausschliesst. Eine Auswahl, die der Dienst später abwiese, wäre
  keine.
- **Auch die blosse Wahl adressiert** (`addressee_of`): sonst meldete der Belegkopf
  «Anschrift fehlt» über jemanden, den man eine Zeile höher ausgewählt hat.
- **Eine Gegenhandlung, ein Klick** (`unask`): was sie bewirkt, sagt der Beleg — steht eine
  Zeile da, wird sie zurückgezogen; steht keine, fällt die Wahl weg. Beides zusammen, wo
  beides da ist. Zwei Verben wären zwei Wörter für eine Sache.

#### 9.15p Die Zeilen-Grammatik — und der Saldo ist eine Farbe

> Testnotizen #995–#999 · #1001–#1003 · `module-ui.LedgerRow`

**Eine Zeile, vier Plätze, immer dieselben:**

```
[ Identifikator ] [ Meta ] ············ [ Aktion ] [ Betrag ]
```

Vier Notizen betrafen vier Plätze derselben Zeile — der Zustandspunkt **vor** der
Rechnungsnummer (#996), die Korrekturen **hinter** dem Betrag (#998/#1002) und eine
**zweite Zeile** mit einer Angabe, die die erste schon sagt (#999). Also ist es keine
Sammlung von Einzelfällen, sondern eine **Grammatik**, und sie steht als ein Bauteil da.

- **Der Identifikator** sagt, was die Zeile *ist*: die Rechnungsnummer, die Zahlungsart.
  Nichts steht davor.
- **Der Betrag steht immer zuletzt** und damit in jeder Zeile auf derselben Flucht —
  nicht, weil jemand eine Spaltenbreite pflegt, sondern weil er das letzte Element ist.
- **Die Aktion steht links davon und belegt ihren Platz immer** (`opacity`, kein
  `display`): erschiene sie erst beim Zeigen, rutschte der Betrag unter dem Zeiger zur
  Seite. Gemessen: Δ 0.00 px.
- **Strikt einreihig** — was nicht passt, wird gekappt (Meta zuerst).

►►► **Der Saldo sagt seinen Zustand als FARBE** (#997, `domain/voucher.balance_state`).
◄◄◄ «Offen 0.00» las sich wie «bezahlt», und das Wort war ohnehin nur an einem der vier
Zustände richtig. Also nennt die Karte allein die **Zahl** und färbt sie: orange, solange
etwas aussteht · rot, sobald ein Termin vorbei ist · grün, wenn es aufgeht. Das **Wort**
reist mit und steht im Hover — Farbe allein ist kein zugängliches Signal (WCAG 1.4.1).

**Ein Guthaben ist grün und nennt sich beim Namen.** An einer einzelnen Forderung ist
«Überzahlt» ein Problem — dort stimmt der Beleg nicht mit dem Geld überein; im **Saldo**
ist es eine Tatsache: niemand schuldet mehr etwas. Ein **Minus** wäre dort die schlechtere
Antwort — ein offener Posten ist eine Forderung und kein negativer Wert, und «−250.00»
neben dem Wort «Guthaben» wäre eine doppelte Verneinung.

**Und die Handlung steht in dem Fach, zu dem sie gehört** (#1001): *Rechnung stellen* zu
«Fordern», *Zahlung erfassen* zu «Begleichen» — dort zuunterst, direkt unter der
Zahlungsart, mit der sie eine Einheit bildet. Unter **beiden** Abschnitten stand sie
hinter allem, was in ihnen wächst: jede erfasste Zahlung schob sie weiter weg von der
Wahl, zu der sie gehört.

#### 9.15q Der Beleg IST die Rechnung — eine je Modul

> `docs/history/2026-09-konzept-eine-rechnung-je-modul.md` · Migration `138` ·
> `vouchers.billed_on`/`due_on`/`number`/`amount`/`vat`/`service_date`/`corrects_id`
>
> *Nachgezogen (Testnotiz #1047): das Verb `issue` («Rechnung ist versendet») ist
> gelöscht – samt Spalten-Mapping `vouchers.issued_on` (Drop im Folge-Deploy). Gestellt
> **ist** draussen.*

*«Nur eine Rechnung pro Zahlungsmodul — wirklich nur eine, auch keine
Stornierungsrechnung. Wenn es eine Korrektur gibt, dann durch ein zweites Zahlungsmodul.
Insbesondere bei Retouren wäre sonst der Warenverkehr getrennt von der monetären
Abwicklung: ich müsste im originalen Modul stornieren — aber dort, wo das Geschehen ist,
soll ich es auch abwickeln können.»*

**Der Befund war eine Doppelung, keine Geschmacksfrage.** Betrag, Steuer, Nummer, Datum
und Fälligkeit standen auf **beiden** Ebenen: die Forderungs-Zeile
(`voucher_entries.kind = 'charge'`) war eine Kopie des Belegs, der sie enthielt — genau
die Fehlerform, die der Neuaufbau bei den Positionen schon einmal beseitigt hat (dort gab
es sie dreimal). Daraus folgte fast alles, was sich «zu komplex» anfühlte: eine Funktion
musste **zählen**, was eine «Forderung nach aussen» ist (`live_charge`), eine zweite
beantwortete «welche Rechnung meint diese Zahlung» (`_charge_for_payment` · `_split` ·
`allocate` · `paid_map`), und **ein Verb machte zwei Dinge** — `reverse` hiess je nach
Bezahlstatus «Stornieren» oder «Gutschrift», auseinandergehalten von **einer Zahl**.

**Danach ist der Beleg die Rechnung.** Acht Angaben wandern eine Ebene hoch, und damit
kann es sie nicht zweimal geben: «eine Rechnung je Modul» ist keine Regel mehr, die
jemand durchsetzt, sondern die **Struktur**.

```
offer     Angebot        schreiben · anfragen · zusagen
agreed    Auftrag        → bill    (Nummer, Betrag, Steuer, Fälligkeit einfrieren)
billed    Rechnung       → pay · unbill (solange kein Geld geflossen ist)
done / cancelled         Ausgänge (unverändert)
```

- **Die dritte Stufe ist keine Wiederholung des Fehlers von damals.** «Abgeschlossen» war
  ein *Zustand* in einer Reihe von *Schritten* — man tat nichts, um ihn zu erreichen. Eine
  Rechnung zu stellen ist eine **Handlung mit unumkehrbarem Ergebnis**: eine Nummer ist
  vergeben, die Steuer steht fest, ein Papier existiert.
- **`unbill` ist die Gegenhandlung zu `bill`**, und sie endet, sobald **Geld geflossen**
  ist (eine Frage an die Daten, in `can`). Die **Nummer bleibt** — die
  zurückgenommene Rechnung ist nie hinausgegangen, es gibt sie nach aussen nicht, und die
  neu gestellte ist derselbe Beleg, korrigiert, bevor er das Haus verliess.
- **Kassiert wird auf eine GESTELLTE Rechnung** – gestellt ist draussen, in beide
  Richtungen gleich. Ein eigener Knopf «ist versendet» (`issue`) stand eine Runde lang
  dazwischen und ist ersatzlos gelöscht (#1047): er setzte ein Datum für das System und
  sperrte am Ende den Zahlungseingang eines Kunden, der die Rechnung längst vor sich hat.
- **Die Steuer wird EINGEFROREN, nicht gerechnet.** Die Positionen stehen ab der Zusage
  fest, die Summe wäre also stabil — die **Aufteilung** ist es nicht: eine künftige
  Änderung an `vat_split` oder am Katalog änderte rückwirkend die Steuer einer längst
  gestellten Rechnung. Ein Beleg behält, was auf ihm stand.

►►► **Die Korrektur ist ein eigener Beleg in einem eigenen Modul** (`corrects_id`). ◄◄◄

- **Die Positionen tragen positive Preise** — niemand tippt ein Minus. «3 × Getriebe à 200»
  ist die Aussage, und sie ist MWST-korrekt.
- **`bill` dreht das Vorzeichen**: wo `corrects_id` steht, wird `amount` negativ
  gespeichert und die Steueraufteilung **gespiegelt**. Danach rechnet jede Zahl
  vorzeichenrichtig, ohne eine einzige Fallunterscheidung beim Lesen.
- **Der Verweis steht auf dem Papier** («Korrektur zu …») — eine **Ableitung**, kein
  zweites Feld. MWSTG Art. 26 verlangt die eindeutige Bestimmbarkeit von Leistung und
  Entgelt; ohne Verweis wäre es eine zweite Rechnung mit negativem Vorzeichen.
- ►►► **Und `corrects_id` darf über Auftragsgrenzen zeigen.** ◄◄◄ Das ist der Kern: die
  Gutschrift gehört dorthin, wo die Ware **zurückkommt**.

**Und die Retoure macht das Modell KLEINER, nicht grösser.** Steht der Gutschriftsbeleg im
Retourenauftrag, entstehen seine Positionen **von selbst** aus den Stücken, die
zurückkommen (`sync_lines`) — der Auftrag greift drei Getriebe, der Beleg hat drei
Getriebe, und er kann keine fünf greifen, wenn nur drei existieren.

> **Die Warenlogik ist die Mengenkontrolle des Geldes.**

Damit entfällt ersatzlos, was `docs/history/2026-09-17-analyse-retoure.md` als Arbeit auflistete:
Teilkorrektur mit Positionsauswahl (§1 — die Teilmenge **ist** die zurückgenommene Ware),
Gutschrift ohne Positionsbezug (§2 — es gibt immer Positionen) und die Summenregel
«Σ Gegenbuchungen ≤ Betrag» (§6 — man kann nicht mehr zurücknehmen, als geliefert wurde).

**Die Entscheidung «Storno oder Gutschrift» trifft damit niemand mehr** — sie fällt aus
dem **Zeitpunkt** heraus: vor dem Versenden gibt es nur `unbill`, danach nur den
Korrekturbeleg.

**Was ersatzlos entfällt:** `live_charge` · `open_charges` · `charge_state` (aufgegangen in
`invoice_state`) · `balance_state` (dieselbe Funktion) · `_charge_for_payment` · `_split` ·
`allocate` · `paid_map` · `_reversal_of` · `reverse_word` · `settle_charge` ·
`credit_only` · `Balance.next_charge` · das Verb `reverse` · `VoucherAllocation` ·
`VoucherEntry.kind`/`charge_id`/`due_on`/`vat`/`service_date`/`reverses_id`.

⚠ **Eine Funktion wird dabei zurückgenommen, und das steht hier ausdrücklich:** die
**Sammelzahlung innerhalb eines Moduls** (#1010–#1017) wird gegenstandslos — sie teilte
eine Zahlung auf mehrere Rechnungen **desselben Belegs** auf, und davon gibt es künftig
eine. **Der Fall selbst bleibt real** (eine Überweisung über 1'500 begleicht 1'000 und
500), liegt aber zwingend über **Modulgrenzen**: das ist die **offene-Posten-Liste** je
Partner, und die ist Buchhaltung (`docs/backlog.md`). Bis dahin sind es zwei erfasste
Zeilen, wo im Kontoauszug eine steht — eine Zeile mehr auf dem Bildschirm, keine falsche
Zahl.

**Was offen bleibt, benannt statt versteckt:** die offene-Posten-Liste je Partner · der
reine Rechnungsfehler **nach** dem Versand (er braucht einen Auftrag über die betroffenen
Stücke — derselbe offene Punkt wie «ein Beleg ganz ohne Ware», weil `assert_releasable`
mindestens eine Einzelinstanz verlangt) · Mahnwesen, camt.053 und die PDF-Zustellung.

#### 9.15r Jede Zahl auf dem Beleg ist eine MENGE

> Testnotizen #1054/#1055/#1056/#1059 · Migration `141` ·
> `domain/voucher.inbound`/`charge_word`/`payment_word` · `services/voucher.minus`

*«Im Begleichen-Teil möchte ich keine Minus-Beträge eingeben, das ist verwirrend — denn am
Anfang sage ich ja, ob es eine Ein- oder Ausgabe ist.»*

**Der Betrag ist eine Menge. Wohin das Geld fliesst, sagt der Beleg — einmal.**

Das war die **Grundursache von drei Meldungen auf einmal**. Ein Korrekturbeleg trug einen
**negativen** Betrag (`bill` drehte das Vorzeichen, `_mirror` spiegelte die Steuer), und
drei Leser fragen «ist der Betrag grösser als null?» — bei einer Gutschrift ist er das nie:

| Leser | fragt | bei einer Gutschrift |
|---|---|---|
| `pay_online` | `open > 0` | fällt weg → «Stripe ist nicht mehr verfügbar» (#1054) |
| `next_payment` | `open > 0` | leer → man musste **−43.24** tippen (#1055) |
| `settled` | `paid >= agreed` | `−43.24 >= +43.24` ist **nie** wahr → bei Saldo 0 kein
  Abschluss (#1056) |

Gemessen über die echten Dienstpfade, nicht vermutet. Mit der Menge stimmen alle drei
**unverändert**: es ist nichts gebaut worden, **vier** Sonderfälle sind gefallen — die
drei oben plus der Vorzeichen-Vergleich in `invoice_state` («überzahlt ist, wo Rest und
Betrag verschiedene Vorzeichen tragen» → wieder schlicht `remaining < 0`).

**Das Minus verschwindet nicht, es bekommt einen Ort:** die Buchhaltung sieht eine
Gutschrift negativ, und sie leitet das aus `corrects_id` ab — an **einer** Stelle, wenn es
sie gibt. Eine Spalte mit Vorzeichen daneben wäre die zweite Wahrheit, und ein `signed()`
ohne Leser die zweite Wahrheit ohne Nutzen.

**Was ein Mensch tippt, ist nie negativ.** Die eine Ausnahme ist die Korrektur einer
erfassten Zahlung — und dort **setzt das System** den Betrag (die Oberfläche belegt ihn mit
dem Gegenwert vor); niemand schreibt ein Minus.

**Und eine Gutschrift wird dadurch SICHTBAR** (#1054 war auch eine Meldung über
Unsichtbarkeit: *«irgendwie hat sich die Funktion voll verändert»*). Der Belegkopf nennt
bewusst keine Belegart (§9.15b), also sagen es die **Wörter auf den Knöpfen** — dort, wo
man handelt: **«Gutschrift stellen»** statt «Rechnung stellen», **«Erstattung erfassen»**
statt «Zahlung erfassen». Zusammengesetzt aus **zwei Bits** (`charge_word`), nicht als
Tabelle mit vier fertigen Sätzen: mit der Gutschrift kam eine zweite Frage dazu, und vier
Sätze wären vier Stellen, an denen einer stehenbleibt. Die Fuge ist ein Leerzeichen vor
einem Infinitiv — in allen vier Fällen richtiges Deutsch, anders als eine gerechnete
Beugung («Kundeen», #787).

**`inbound` ist nicht `collects`** (`vo.inbound` = `collects != minus`): wer den Beleg
**ausstellt**, bleibt bei einer Gutschrift derselbe (wir schreiben unserem Kunden gut), nur
fliesst das Geld andersherum. Zwei Fragen, zwei Antworten — und nur die zweite entscheidet
über den **Zahlungsdienst** (er *zieht ein*) und den **Einzahlungsschein** (er trägt unsere
Bankverbindung). *Bis hierher fiel beides an einer Gutschrift ebenfalls weg, aber aus dem
falschen Grund: der Betrag war negativ. Ein Zufall, der stimmt, ist keine Regel.*

**#1059, validiert:** die Gutschrift bleibt in der **Einnahme**-Logik, und das ist richtig
— steuerlich ist sie eine *Umsatzminderung*, keine Ausgabe (eine Ausgabe wäre Vorsteuer).
Was sie unangenehm machte, war nicht der Ort, sondern das Minus.

Migration `141` hat bestehende Gutschriften und die Erstattungen darauf gedreht (seit der
Basis `161` Teil der Geschichte).


#### 9.15s Umbau Oktober 2026 — was jetzt gilt (geht §9.15a–r vor)

> Entscheide: Dokument «Zahlungsmodul – Ziel, Muster, Plan» und das Mockup
> (`docs/history/2026-10-25-zahlungsmodul-umbau.md`). Code: `domain/voucher`,
> `services/voucher` (`VERBS`, `can`, `situation`), `services/voucher_docs`,
> `services/document`, `services/legal`, `services/payment_list`, `routers/beleg.py`,
> Migration `155`. **Wo ein älterer Unterabschnitt etwas anderes sagt, gilt dieser.**

- **Die Stücke passieren das Modul von selbst** – mit der Zusage, bei Vorauszahlung mit
  der vollen Zahlung (`voucher.passable`, `process.advance_payments`). Einen
  «Bestätigen»-Knopf gibt es an einem Zahlungsmodul nicht (`PASSES_ITSELF`). Der Status
  bleibt `Im Prozess`. **Eigentum** «geht an die Partei · geht an uns» ist eine Pflichtwahl
  ohne Vorbelegung, eingefroren mit der Zusage. **Wem ein Stück gehört, wird abgeleitet**
  (`voucher.sold_units`): das jüngste nicht stornierte Zahlungsmodul, das es passiert hat.
  Am Ziel des Auftrags wird ein Stück, das der Partei gehört, **Verkauft** (Historie, behält
  seinen Ort), sonst Freigegeben. Storno → frei, Retoure «an uns» → frei, Reparatur ohne
  Zahlung → bleibt Verkauft; eine stornierte Retoure lässt den Verkauf wieder gelten.
- **Erledigt ist abgeleitet**: gestellt ∧ Saldo 0 (∧ Ausfuhrnachweis bei Export). Die Stufe
  `done` und «Vorgang abschliessen» gibt es nicht mehr.
- **Ein Wort für den Storno: «Stornieren»**, in jeder Stufe. Nach der Rechnung entsteht die
  Gutschrift über die ganze Rechnung von selbst (`credit_number`, eigene Nummer). «Rechnung
  zurücknehmen» (`unbill`) gibt es nicht mehr.
- **Passen die Stücke nicht mehr** (ein beim ersten Hinausgehen eingefrorenes Stück hat den
  Auftrag verlassen, ohne das Modul passiert zu haben – `units_problem`), bleibt nur
  «Stornieren». Die übrigen Stücke führt ein gewöhnlicher Abweichungsauftrag weiter.
- **Geld-Zeilen haben eine Art**: Zahlung (negativ = Erstattung) · Ausbuchung (mit Grund aus
  fester Liste, Entgeltsminderung) · Trinkgeld (Entgelt). «Falsch erfasst?» bucht genau eine
  Zeile gegen. Eine Referenz gehört zu genau einer aktiven Zeile (Unique-Index).
- **Gültigkeit** in Tagen ab «Anbieten» (Vorgabe 30); abgelaufen → «Erneut anbieten» (dieselbe
  Handlung). **Angenommen wird nur die aktuelle Fassung** (`offered_hash`): wer nach dem
  Anbieten ändert, bietet erneut an.
- **Die Anschrift entscheidet**: Ware → Steuersatz nach Lieferadresse (Ausland: 0 % Export,
  fest), Dienstleistung → nach Sitz (Ausland: Reverse Charge); Fremdwährung nur ins Ausland;
  Zoll (Tarif, Ursprung, Gewicht) nur bei Export; Ort der Lieferbedingung abgeleitet (E/F:
  Versandadresse des Erbringers, C/D: Lieferadresse). Die eigene Gesellschaft ist nie
  Gegenpartei.
- **Lieferantenrechnung**: Rechnungsnummer, -datum, MWST-Nr. (bei Steuer Pflicht), Foto
  Pflicht; weicht sie von der Zusage ab, wird erst nach «So annehmen …» (mit Grund) bezahlt.
- **Teilbetrag je Position** (netto); jedes Zahlungsmodul steht für sich.
- **Mahnung**: drei Stufen, je 10 Tage, von Hand; die Stufe ist die Zahl der Mahn-Dokumente.
  Überfälliges zählt an der Person (`todo`), eine eigene Mahnliste gibt es nicht.
- **Dokumente**: jede Stufe, die die Partei sehen soll, ist ein eingefrorenes A4-Dokument aus
  EINER Vorlage (AGB als letzte Seite, Datum der AGB-Fassung genannt) mit einem Link
  `/beleg?t=…` und einer Mail über das Postfach der Gesellschaft. Auf der Seite handelt die
  Partei mit denselben Verben (`can`).
- **Die Leiste** (`situation`) ist nie leer ausser bei Erledigt/Storniert; ein Wächter prüft,
  dass jeder Zustand einen nächsten Schritt hat.
- **Modul-Vorgaben** (Fristen, Gültigkeit, Lieferbedingung, Eigentum) stehen im Beleg fest.
