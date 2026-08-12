# TEST_REPORT — Testkampagne Prozessmodell

> **Soll steht vor dem Lauf.** Jeder Fall in `backend/tests/matrix.py` trägt seine
> Erwartung als Datensatz; gefahren wird über die **echten** Dienstpfade
> (`process.release` / `process.confirm_step`) gegen echtes PostgreSQL 16 — nie über
> nachgestellte Zustände. Die interessanten Fehler entstehen zwischen den Schritten.
>
> **Nichts ist beschönigt.** Ein Fall, der nicht lief, steht als «nicht geprüft» da.
> **Ein** Fall weicht ab, und er steht als Befund in `FINDINGS.md` (🟡-1).
>
> **Stand: Runde 2.** Die Matrix ist von 67 auf **71 Fälle** gewachsen — Block 9 prüft den
> **Abbruch über die Abweichung** (S57 · S58 · S59) und den Restbestand eines inaktiven
> Artikels (S98b). Beide 🟠-Befunde der ersten Runde sind damit erledigt.

## Wie das hier reproduzierbar ist

```bash
cd backend
export DATABASE_URL=postgresql+psycopg2://…            # echtes PostgreSQL, kein SQLite
python -m pytest -q tests/test_scenarios.py            # die Matrix als Wächter
python -m pytest -q tests/test_invariants.py           # die Invarianten als Wächter
python -m scripts.scenario_report                      # diese Tabelle
python -m scripts.invariant_report --populate          # die Invarianten-Tabelle
```

Beide Wächter laufen ab jetzt bei jeder Änderung mit. Ohne Datenbank **überspringen** sie
mit Grund — sie behaupten nie, bestanden zu haben.

## Die Achsen

| Achse | Werte | abgedeckt |
|---|---|---|
| **A · Herkunft** | Neu · Lager · gemischt | ✅ alle drei |
| **B · Serialisierung** | Einzel · Charge | ✅ beide |
| **C · Menge** | 1 · 2 · viele (600) | ✅ alle drei |
| **D · Modultyp** | Datenerfassung · Verschrotten · Sperren | ✅ alle drei |
| **E · Schachtelung** | keine · 1 · 2 · 3 Ebenen | ✅ alle vier |
| **F · Rückführung** | normal · gekappt · auto-gekappt · gemischt | ✅ alle vier |

**Unmögliche Kombination, dokumentiert statt weggelassen:** «Neu» **gemischt mit** «Lager»
in einem Auftrag gibt es nicht (Fall S11). Ein Erzeugungsauftrag fährt die Vorlage genau
seines Artikels und trägt deren Versionsstempel; für eine zweite Zeile wäre der Stempel
eine Behauptung. Geprüft ist, dass die Ablehnung wirklich kommt — nicht, dass der Fall
fehlt.

## Die Zeichen in der Tabelle

| | |
|---|---|
| ✅ | Soll == Ist |
| 🟠 | **bekannter, offener Befund** (`FINDINGS.md`). Das Soll bleibt stehen – es ist die Regel, nicht der Ist-Zustand. Der Wächter lässt die CI dafür nicht rot werden, **meldet aber**, sobald die Abweichung aufhört: dann ist der Befund behoben und die Markierung muss weg. Ein Befund, der still verschwindet, hinterlässt sonst eine Ausnahme, die niemand mehr hinterfragt. |
| ❌ | unerwartete Abweichung |
| 💥 | der Fall ist gar nicht gelaufen |
| ⊘ | unmögliche Kombination, mit Begründung |

## 1 · Die Szenariomatrix

| # | Fall | A · B · C · D · E · F | Soll | Ist | |
|---|---|---|---|---|---|
| S01 | Erzeugen · einzeln · 1 · Datenerfassung | neu · einzel · 1 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 1}<br>`instanzen` = 1<br>`scans` = 1<br>`probleme` = [] | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 1}<br>`instanzen` = 1<br>`scans` = 1<br>`probleme` = [] | ✅ |
| S02 | Erzeugen · Charge · 1 · Datenerfassung | neu · batch · 1 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 1}<br>`instanzen` = 1<br>`scans` = 1 | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 1}<br>`instanzen` = 1<br>`scans` = 1 | ✅ |
| S03 | Erzeugen · einzeln · 2 → zwei Instanzen, zwei Scans | neu · einzel · 2 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 2}<br>`instanzen` = 2<br>`scans` = 2 | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 2}<br>`instanzen` = 2<br>`scans` = 2 | ✅ |
| S04 | Erzeugen · Charge · 2 → EINE Instanz, EIN Scan, ZWEI Erfassungen | neu · batch · 2 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 2}<br>`instanzen` = 1<br>`scans` = 1<br>`erfassungen` = 2 | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 2}<br>`instanzen` = 1<br>`scans` = 1<br>`erfassungen` = 2 | ✅ |
| S05 | Erzeugen · Charge · 600 – die Menge ist kein Sonderfall | neu · batch · viele · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`stück` = 600<br>`instanzen` = 1<br>`scans` = 1<br>`erfassungen` = 600 | `status` = 'abgeschlossen'<br>`stück` = 600<br>`instanzen` = 1<br>`scans` = 1<br>`erfassungen` = 600 | ✅ |
| S06 | Verschrotten · einzeln · 1 → Endzustand, Auftrag abgeschlossen | neu · einzel · 1 · verschrotten · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 1}<br>`probleme` = [] | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 1}<br>`probleme` = [] | ✅ |
| S07 | Verschrotten · Charge · 2 → beide Stücke terminal | neu · batch · 2 · verschrotten · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 2} | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 2} | ✅ |
| S08 | Sperren · einzeln · 1 → gesperrt, aber nicht terminal | neu · einzel · 1 · sperren · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'gesperrt': 1}<br>`wählbar` = True | `status` = 'abgeschlossen'<br>`states` = {'gesperrt': 1}<br>`wählbar` = True | ✅ |
| S09 | Lager · einzeln · 1 – bestehendes Stück, kein neues | lager · einzel · 1 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 1}<br>`neue_stück` = 0<br>`abweichung` = False | `status` = 'abgeschlossen'<br>`states` = {'freigegeben': 1}<br>`neue_stück` = 0<br>`abweichung` = False | ✅ |
| S10 | Lager · Teilmenge einer Charge – 1 von 3 | lager · batch · 1 · datenerfassung · 0 · – | `stück_im_auftrag` = 1<br>`status` = 'abgeschlossen'<br>`rest_frei` = 2 | `stück_im_auftrag` = 1<br>`status` = 'abgeschlossen'<br>`rest_frei` = 2 | ✅ |
| S11 | Gemischt «Neu» + «Lager» in EINEM Auftrag | gemischt · einzel · 2 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S12 | Gemischt: zwei Lager-Zeilen, zwei Artikel | gemischt · einzel · 2 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`stück` = 2<br>`instanzen` = 2 | `status` = 'abgeschlossen'<br>`stück` = 2<br>`instanzen` = 2 | ✅ |
| S13 | Zwei Module hintereinander | neu · einzel · 2 · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`module` = 2<br>`states` = {'freigegeben': 2} | `status` = 'abgeschlossen'<br>`module` = 2<br>`states` = {'freigegeben': 2} | ✅ |
| S14 | Erfassung → Verschrotten: der Ausgang steht am Schluss | neu · einzel · 1 · verschrotten · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 1}<br>`probleme` = [] | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 1}<br>`probleme` = [] | ✅ |
| S15 | Modul HINTER einem Ausgang – nicht anlegbar | neu · einzel · 1 · verschrotten · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S20 | Stichprobe 50 % von 4 → 2 gezogen | neu · batch · viele · datenerfassung · 0 · – | `gezogen` = 2<br>`rest` = 2<br>`erfassungen` = 2 | `gezogen` = 2<br>`rest` = 2<br>`erfassungen` = 2 | ✅ |
| S21 | Stichprobe 25 % von 3 → aufgerundet 1 | neu · batch · viele · datenerfassung · 0 · – | `gezogen` = 1<br>`rest` = 2 | `gezogen` = 1<br>`rest` = 2 | ✅ |
| S22 | Stichprobe 1 % von 2 → nie leer | neu · batch · 2 · datenerfassung · 0 · – | `gezogen` = 1 | `gezogen` = 1 | ✅ |
| S23 | Anteil an der GESAMTMENGE, nicht je Instanz | lager · batch · viele · datenerfassung · 0 · – | `gezogen_gesamt` = 2<br>`instanzen` = 2 | `gezogen_gesamt` = 2<br>`instanzen` = 2 | ✅ |
| S24 | Der ungezogene Rest läuft ohne Erfassung durch – sichtbar | neu · batch · viele · datenerfassung · 0 · – | `status` = 'abgeschlossen'<br>`erfassungen` = 2<br>`stück` = 4 | `status` = 'abgeschlossen'<br>`erfassungen` = 2<br>`stück` = 4 | ✅ |
| S25 | Die Ziehung ist eingefroren – zweimal gefragt, dieselbe Antwort | neu · batch · viele · datenerfassung · 0 · – | `gleich` = True | `gleich` = True | ✅ |
| S30 | Ein schlechtes Stück hält die GANZE Instanz an | neu · batch · 2 · datenerfassung · 0 · – | `bewegt` = 0<br>`angehalten` = 2<br>`urteil` = 'failed'<br>`states` = {'im_prozess': 2} | `bewegt` = 0<br>`angehalten` = 2<br>`urteil` = 'failed'<br>`states` = {'im_prozess': 2} | ✅ |
| S31 | Der Halt hat einen Ausgang: erneut erfassen | neu · batch · 2 · datenerfassung · 0 · – | `nach_schlecht_held` = True<br>`nach_gut_held` = False<br>`status` = 'abgeschlossen' | `nach_schlecht_held` = True<br>`nach_gut_held` = False<br>`status` = 'abgeschlossen' | ✅ |
| S32 | Ein «nicht bestanden» legt NICHTS an | neu · batch · 2 · datenerfassung · 0 · – | `neue_aufträge` = 0 | `neue_aufträge` = 0 | ✅ |
| S40 | Eine Abweichung, normale Rückführung – zurück an denselben Punkt | lager · batch · 2 · datenerfassung · 1 · normal | `abweichung` = True<br>`eltern_wartet_vorher` = True<br>`eltern_wartet_nachher` = False<br>`punkt_gleich` = True<br>`eltern_status` = 'im_prozess'<br>`probleme` = [] | `abweichung` = True<br>`eltern_wartet_vorher` = True<br>`eltern_wartet_nachher` = False<br>`punkt_gleich` = True<br>`eltern_status` = 'im_prozess'<br>`probleme` = [] | ✅ |
| S41 | Zwei Abweichungen parallel – der Eltern wartet auf BEIDE | lager · batch · 2 · datenerfassung · 1 · normal | `verliehen` = 2<br>`wartet_am_anfang` = True<br>`wartet_nach_einer` = True<br>`wartet_nach_beiden` = False<br>`gesperrte_module` = 1 | `verliehen` = 2<br>`wartet_am_anfang` = True<br>`wartet_nach_einer` = True<br>`wartet_nach_beiden` = False<br>`gesperrte_module` = 1 | ✅ |
| S42 | Zwei Abweichungen nacheinander | lager · batch · 2 · datenerfassung · 1 · normal | `wartet_zwischendurch` = True<br>`wartet_am_ende` = False<br>`eltern_status` = 'im_prozess'<br>`probleme` = [] | `wartet_zwischendurch` = True<br>`wartet_am_ende` = False<br>`eltern_status` = 'im_prozess'<br>`probleme` = [] | ✅ |
| S43 | Drei Ebenen tief, alle rückführend – die Kette trägt | lager · batch · 1 · datenerfassung · 3 · normal | `a_wartet` = True<br>`b_wartet` = True<br>`a_status` = 'im_prozess'<br>`nach_c_a_wartet` = True<br>`nach_b_a_wartet` = False<br>`a_am_schluss` = 'abgeschlossen'<br>`stück` = 'freigegeben' | `a_wartet` = True<br>`b_wartet` = True<br>`a_status` = 'im_prozess'<br>`nach_c_a_wartet` = True<br>`nach_b_a_wartet` = False<br>`a_am_schluss` = 'abgeschlossen'<br>`stück` = 'freigegeben' | ✅ |
| S44 | Rückführung bei der Definition GEKAPPT – der Eltern wartet nicht | lager · batch · 2 · datenerfassung · 1 · gekappt | `eltern_wartet` = False<br>`verliehen` = 0<br>`eltern_läuft_weiter` = 'abgeschlossen'<br>`eltern_stück` = 1 | `eltern_wartet` = False<br>`verliehen` = 0<br>`eltern_läuft_weiter` = 'abgeschlossen'<br>`eltern_stück` = 1 | ✅ |
| S45 | AUTO-Kappung durch Verschrotten in der Abweichung | lager · batch · 2 · verschrotten · 1 · auto-gekappt | `wartet_vorher` = True<br>`wartet_nachher` = False<br>`kind_status` = 'abgeschlossen'<br>`eltern_status` = 'abgeschlossen'<br>`stück` = 'verschrottet'<br>`eltern_rest` = 1 | `wartet_vorher` = True<br>`wartet_nachher` = False<br>`kind_status` = 'abgeschlossen'<br>`eltern_status` = 'abgeschlossen'<br>`stück` = 'verschrottet'<br>`eltern_rest` = 1 | ✅ |
| S46 | Gemischt: eine Abweichung rückführend, eine gekappt | lager · batch · viele · datenerfassung · 1 · gemischt | `verliehen` = 1<br>`wartet` = True<br>`nach_rückkehr_wartet` = False<br>`eltern_status` = 'im_prozess' | `verliehen` = 1<br>`wartet` = True<br>`nach_rückkehr_wartet` = False<br>`eltern_status` = 'im_prozess' | ✅ |
| S47 | Aussondern auf EBENE 3, während 1 und 2 warten | lager · batch · 1 · verschrotten · 3 · auto-gekappt | `a_wartet_vorher` = True<br>`b_wartet_vorher` = True<br>`a_wartet_nachher` = False<br>`b_wartet_nachher` = False<br>`a_status` = 'abgebrochen'<br>`b_status` = 'abgebrochen'<br>`c_status` = 'abgeschlossen'<br>`stück` = 'verschrottet' | `a_wartet_vorher` = True<br>`b_wartet_vorher` = True<br>`a_wartet_nachher` = False<br>`b_wartet_nachher` = False<br>`a_status` = 'abgebrochen'<br>`b_status` = 'abgebrochen'<br>`c_status` = 'abgeschlossen'<br>`stück` = 'verschrottet' | ✅ |
| S48 | Eltern abschliessen, während ein GEKAPPTER Unterauftrag noch läuft | lager · batch · 2 · datenerfassung · 1 · gekappt | `eltern_status` = 'abgeschlossen'<br>`kind_status` = 'im_prozess' | `eltern_status` = 'abgeschlossen'<br>`kind_status` = 'im_prozess' | ✅ |
| S49a | ALLE Stücke in Abweichungen, rückführend → Eltern Im Prozess | lager · batch · 2 · datenerfassung · 1 · normal | `eltern_status` = 'im_prozess'<br>`unterwegs` = 0<br>`verliehen` = 2 | `eltern_status` = 'im_prozess'<br>`unterwegs` = 0<br>`verliehen` = 2 | ✅ |
| S49b | ALLE Stücke gekappt übernommen → Eltern Abgebrochen | lager · batch · 2 · datenerfassung · 1 · gekappt | `eltern_status` = 'abgebrochen'<br>`verliehen` = 0 | `eltern_status` = 'abgebrochen'<br>`verliehen` = 0 | ✅ |
| S50 | Abweichung auf ein Stück, das schon in einer Abweichung ist | lager · batch · 1 · datenerfassung · 2 · normal | `erlaubt` = True<br>`c_ist_abweichung` = True<br>`offene_zeilen` = 1 | `erlaubt` = True<br>`c_ist_abweichung` = True<br>`offene_zeilen` = 1 | ✅ |
| S51 | Gesperrtes Stück greifen = Sonderfreigabe (auch eine Abweichung) | lager · einzel · 1 · sperren · 0 · – | `vorher` = 'gesperrt'<br>`abweichung` = True<br>`nachher` = 'freigegeben' | `vorher` = 'gesperrt'<br>`abweichung` = True<br>`nachher` = 'freigegeben' | ✅ |
| S52 | Ein gesperrtes Modul lässt sich nicht bestätigen | lager · batch · 2 · datenerfassung · 1 · normal | `code` = 409<br>`spricht` = True | `code` = 409<br>`spricht` = True | ✅ |
| S60 | Dasselbe Stück zweimal in EINEM Auftrag | lager · batch · 2 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S61 | Auswahl behauptet «aus Auftrag N», Stück ist frei | lager · einzel · 1 · datenerfassung · 0 · – | `code` = 409<br>`spricht` = True | `code` = 409<br>`spricht` = True | ✅ |
| S62 | Auswahl behauptet «frei», Stück läuft in einem Auftrag | lager · batch · 1 · datenerfassung · 0 · – | `code` = 409<br>`spricht` = True | `code` = 409<br>`spricht` = True | ✅ |
| S64 | Sequenzielle Übernahme: nie zwei offene Zugehörigkeiten | lager · batch · 1 · datenerfassung · 1 · normal | `offene_zeilen` = 1<br>`gesamt_zeilen` = 2 | `offene_zeilen` = 1<br>`gesamt_zeilen` = 2 | ✅ |
| S70 | Verschrottetes Stück in einen NEUEN Auftrag | lager · einzel · 1 · datenerfassung · 0 · – | `code` = 409<br>`spricht` = True | `code` = 409<br>`spricht` = True | ✅ |
| S71 | Verschrottetes Stück per rohem UPDATE | – · einzel · 1 · verschrotten · 0 · – | `abgewiesen` = True | `abgewiesen` = True | ✅ |
| S72 | Auftrag mit verschrottetem Stück abschliessen | neu · einzel · 1 · verschrotten · 0 · – | `status` = 'abgeschlossen' | `status` = 'abgeschlossen' | ✅ |
| S73 | Verschrottetes Stück in eine Abweichung ziehen | lager · einzel · 1 · datenerfassung · 1 · normal | `code` = 409<br>`spricht` = True | `code` = 409<br>`spricht` = True | ✅ |
| S74 | Der ENTWURF meldet es – nicht erst der Klick | lager · einzel · 1 · datenerfassung · 0 · – | `freigebbar` = False<br>`grund_genannt` = True | `freigebbar` = False<br>`grund_genannt` = True | ✅ |
| S80 | Menge N heisst: danach laufen exakt N Einzelinstanzen | neu · batch · viele · datenerfassung · 0 · – | `soll` = 7<br>`ist` = 7 | `soll` = 7<br>`ist` = 7 | ✅ |
| S81 | Nach der Aussonderung bleibt die Zeile – nur der Zustand wechselt | neu · batch · 2 · verschrotten · 0 · – | `zeilen_vorher` = 2<br>`zeilen_nachher` = 2<br>`states` = {'verschrottet': 2} | `zeilen_vorher` = 2<br>`zeilen_nachher` = 2<br>`states` = {'verschrottet': 2} | ✅ |
| S82 | Nach der Rückführung stimmt die Menge des Eltern wieder | lager · batch · 2 · datenerfassung · 1 · normal | `eltern_stück` = 2<br>`am_ende_frei` = 2 | `eltern_stück` = 2<br>`am_ende_frei` = 2 | ✅ |
| S83 | Lager-Zeile mit zu wenigen Stücken | lager · batch · 2 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S84 | Menge 0 | neu · einzel · 0 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S90 | «Neu» ohne Erzeugungsprozess am Artikel | neu · einzel · 1 · – · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S91 | Unbekannter Modultyp | neu · einzel · 1 · – · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S92 | Unbekannter Erfassungstyp | neu · einzel · 1 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S93 | Aussondern ohne Grund | neu · einzel · 1 · verschrotten · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S94 | Pflichtpunkt nicht erfasst | neu · batch · 1 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>**`spricht` = False** | 🟠 |
| S95 | Wertesatz für ein NICHT gezogenes Stück | neu · batch · viele · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S96 | Fehlender Wertesatz für ein gezogenes Stück | neu · batch · 2 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S97 | Ohne Verifikation der Instanz | neu · batch · 1 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S98 | Auftrag auf einen INAKTIVEN Artikel | neu · einzel · 1 · datenerfassung · 0 · – | `code` = 400<br>`spricht` = True | `code` = 400<br>`spricht` = True | ✅ |
| S26 | Ein Stück, das in einer Abweichung war, entgeht der Prüfung nicht | lager · einzel · 2 · datenerfassung · 1 · normal | `modul1_gesperrt` = True<br>`am_modul2_erfasst` = 2 | `modul1_gesperrt` = True<br>`am_modul2_erfasst` = 2 | ✅ |
| S53 | Gesperrt ist nur DAS Modul mit der offenen Rückführung | lager · einzel · 2 · datenerfassung · 1 · normal | `gesperrte_module` = 1<br>`module_gesamt` = 2 | `gesperrte_module` = 1<br>`module_gesamt` = 2 | ✅ |
| S63 | NEBENLÄUFIGKEIT – zwei Freigaben mit demselben freien Stück | lager · einzel · 1 · datenerfassung · 0 · – | `erfolge` = 1<br>`offene_zeilen` = 1 | `erfolge` = 1<br>`offene_zeilen` = 1 | ✅ |
| S85 | Eine gescheiterte Freigabe verbraucht KEINE Objektnummer | lager · einzel · 1 · datenerfassung · 0 · – | `nummer_verbraucht` = 0 | `nummer_verbraucht` = 0 | ✅ |
| S86 | Der Log ist die Wahrheit: Zustand == letzter Eintrag | lager · batch · 2 · datenerfassung · 1 · normal | `abweichungen` = [] | `abweichungen` = [] | ✅ |
| S99 | Unbekannter Status wird gemeldet, nicht einsortiert | – · – · – · – · 0 · – | `bestand` = 'unknown'<br>`terminal` = False<br>`wählbar` = False<br>`beschriftung` = 'phantasie' | `bestand` = 'unknown'<br>`terminal` = False<br>`wählbar` = False<br>`beschriftung` = 'phantasie' | ✅ |
| S57 | ABBRUCH: alle Stücke entzogen und gekappt → Auftrag abgebrochen | lager · batch · 2 · verschrotten · 1 · gekappt | `eltern_status` = 'abgebrochen'<br>`eltern_wartet` = False<br>`module_gesperrt` = 0<br>`abbrecher_status` = 'abgeschlossen'<br>`stück` = {'verschrottet': 2}<br>`probleme` = [] | `eltern_status` = 'abgebrochen'<br>`eltern_wartet` = False<br>`module_gesperrt` = 0<br>`abbrecher_status` = 'abgeschlossen'<br>`stück` = {'verschrottet': 2}<br>`probleme` = [] | ✅ |
| S58 | ABBRUCH beim OBERSTEN Auftrag – ohne Elternteil | neu · einzel · 2 · verschrotten · 1 · gekappt | `eltern_status` = 'abgebrochen'<br>`hat_eltern` = False | `eltern_status` = 'abgebrochen'<br>`hat_eltern` = False | ✅ |
| S59 | Ein liegengelassener Abzweig klemmt den Eltern NICHT dauerhaft | lager · batch · 1 · verschrotten · 2 · gekappt | `a_wartet_vorher` = True<br>`a_wartet_nachher` = False<br>`a_status` = 'abgebrochen'<br>`b_status` = 'abgebrochen' | `a_wartet_vorher` = True<br>`a_wartet_nachher` = False<br>`a_status` = 'abgebrochen'<br>`b_status` = 'abgebrochen' | ✅ |
| S98b | Ein INAKTIVER Artikel bleibt über «Lager» abwickelbar | lager · einzel · 1 · verschrotten · 0 · – | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 1} | `status` = 'abgeschlossen'<br>`states` = {'verschrottet': 1} | ✅ |

**71 Fälle · 70 bestanden · 1 bekannter Befund (🟠, siehe FINDINGS.md) · 0 unerwartet abweichend**

### S94 — Pflichtpunkt nicht erfasst
_Der Fehler kommt – er nennt aber nur den Punkt, nicht das Stück._
- ❌ spricht: Soll True · Ist False
- ℹ️ `meldung` = 'Noch nicht erfasst: OK.'

## 2 · Die Invarianten über den gesamten Bestand

> Ein Szenariotest prüft, woran jemand gedacht hat. Eine Invariante prüft, was **wahr sein
> muss** — auch in den Fällen, an die niemand gedacht hat. Sie sind rein lesend und
> bleiben dauerhaft im System (`app/services/invariants.py`).

_Bestand aus der Matrix: 70 von 71 Fällen eingespielt._

_Geprüfter Bestand: 102 Aufträge · 71 Instanzen · 720 Einzelinstanzen · 764 Zugehörigkeiten · 3605 Log-Einträge._

| # | Invariante | Regel | Verstösse | |
|---|---|---|---|---|
| I01 | Jede Einzelinstanz ist in höchstens EINEM Auftrag aktiv | G2 – aktiv heisst offene Zugehörigkeit; zwei davon darf es nie geben. | – | ✅ |
| I02 | Eine offene Zugehörigkeit steht IMMER vor einem Modul | §4.1 – wer das Ende passiert, wird frei; die Zeile wird dabei geschlossen. | – | ✅ |
| I03 | Der Zustandspunkt gehört zum eigenen Auftrag | G1 – «wo steht dieses Stück» ist eine Aussage über DIESE Zugehörigkeit. | – | ✅ |
| I04 | Kein Statuswechsel führt aus einem terminalen Status heraus | G4 – geprüft am LOG, nicht an der Absicht: ein Eintrag, dessen Vorher-Zustand terminal ist, wäre der Beweis. | – | ✅ |
| I05 | Log und Zeile widersprechen sich nicht | G5 – der Log sagt Endzustand, die Zeile sagt etwas anderes: dann hat jemand AUSSERHALB der Prozesslogik geschrieben (Migration 110). | – | ✅ |
| I06 | Jeder gespeicherte Zustand steht im Katalog | §1.1 – die Liste ist geschlossen; ein Wert daneben ist im System nicht gültig. | – | ✅ |
| I07 | Der Auftragsstatus passt zum Zustand seiner Stücke | §2.1 – abgeleitet heisst: er darf der Zeilenlage nie widersprechen. | – | ✅ |
| I08 | Die Menge stimmt: Definitionszeilen == Einzelinstanzen | G3 – Menge N heisst, danach laufen exakt N Stück. Die Zeilen bleiben stehen, auch wenn sich ihr Zustand ändert. | – | ✅ |
| I09 | Jede wartende Rückführung hat einen Gegenpart | §12.4 – die Rückkehrposition ist die geschlossene Zeile des Quell-Auftrags mit gesetztem Zustandspunkt. Zeigt sie ins Leere, kommt das Stück nirgends an. | – | ✅ |
| I10 | Eine Rückführung zeigt auf einen Auftrag, den es gibt | G3 – ein Verweis ins Leere ist ein Loch in Bestand und Historie. | – | ✅ |
| I11 | Jede Objektnummer existiert genau einmal | §0 – ein universeller Nummernkreis über alle Objekttypen. | – | ✅ |
| I12 | Jede Einzelinstanz gehört zu einer Instanz, die es gibt | G1 – ihre Nummer ist von der Instanz abgeleitet; ohne sie hat sie keine. | – | ✅ |
| I13 | Jedes Stück im Prozess hat einen Auftrag, der es hält | G2 – «Im Prozess» heisst: in genau einem Auftrag. Ohne Zeile wäre der Zustand eine Behauptung. | – | ✅ |
| I14 | Jeder Auftrag hat genau ein Start-Ereignis je Stück | §6.3 – das Start-Objekt wird einmal passiert; zweimal hiesse, das Stück wäre zweimal eingetreten. | – | ✅ |
| I15 | Das Prozessbild ist für jeden Auftrag widerspruchsfrei | §8.1a – jede Einzelinstanz steht auf genau einer Kante, und eine Kante mit Stücken gilt als gegangen. Die Prüfung steckt im Graph selbst. | – | ✅ |

**15 Invarianten · 15 erfüllt · 0 verletzt**

### Gegenprobe: schlagen die Wächter überhaupt an?

Ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu unterscheiden. Der Test
`test_every_invariant_would_actually_notice_something` stellt drei Fehlerformen her und
verlangt, dass sie gemeldet werden:

| Fehlerform | erwartet | Ergebnis |
|---|---|---|
| zweite offene Zugehörigkeit für dasselbe Stück (Bruch G2) | `I01` meldet | ✅ gemeldet |
| Log-Eintrag **aus** einem Endzustand heraus (Bruch G4) | `I04` meldet | ✅ gemeldet |
| Einzelinstanz mit Zustand ausserhalb des Katalogs | `I06` meldet | ✅ gemeldet |

Bemerkenswert am ersten: die Fehlerform liess sich **nicht** auf normalem Weg herstellen —
der partielle Unique-Index hat den ersten Anlauf abgewiesen. Erst nachdem der Index im
Test kurz weicht, entsteht die Lage. Das ist der beste verfügbare Beweis, dass er trägt.

## 3 · Was NICHT geprüft wurde — und warum

| Nicht geprüft | Grund |
|---|---|
| **Oberfläche im Browser** | Playwright ist in dieser Umgebung nicht installiert, und der Agent-Proxy blockiert die Deploy-URLs. Alle Aussagen über das Frontend stammen aus **Quelltext-Prüfung**, nicht aus einem Klick. Wo eine Regel nur im Frontend steht, ist sie hier ausdrücklich **ungeprüft**. |
| ~~**Abbruch eines Auftrags**~~ | **Jetzt geprüft** (Runde 2): es gibt keine Abbruch-*Funktion*, aber sehr wohl einen Weg — die Abweichung, die alle Stücke nimmt und die Rückführung kappt (S57 · S58 · S59, `SYSTEM_LOGIC.md` §4.4). |
| **Sehr grosse Mengen (5000+)** | Gefahren wurde bis 600 Stück in einer Charge (S05). Die Grössenordnung darüber ist eine **Laufzeit**-Frage, keine Logikfrage — sie gehört in eine Lastmessung, nicht in diese Kampagne. |
| **Mehrbenutzer über HTTP** | Die Nebenläufigkeit ist auf **Dienstebene** mit zwei echten Sitzungen und einer Barriere geprüft (S63). Zwei gleichzeitige HTTP-Anfragen durch den vollen Router-Stapel sind nicht gefahren. |
| **Modultypen mit Aussenwirkung** | Es gibt keine (Einkauf/Verkauf sind nicht gebaut). `Module.units_may_leave` ist damit ungetestet — der Schalter steht, sein Fall existiert noch nicht. **Seit Runde 2 ist das ein benanntes Risiko** (R7): derselbe Schalter entscheidet auch, ob sich ein Auftrag noch abbrechen lässt. |
| **Migrationen von echtem Altbestand** | Das Schema wird aus den Migrationen aufgebaut (CI), aber es gibt keinen Produktions-Dump zum Nachfahren. |

## 4 · Zwischenergebnisse, ehrlich

Der erste Lauf meldete **drei** Abweichungen. Zwei davon waren **Testfehler**, keine
Befunde — und das ist selbst ein Ergebnis:

| Fall | erster Befund | tatsächlich |
|---|---|---|
| **S43** (drei Ebenen tief) | «A wartet nach C nicht mehr» | **Mein Soll war falsch.** Nach C ist das Stück bei **B**, nicht bei A — A wartet zu Recht weiter. Korrigiert und um die fehlende Stufe erweitert (nach B wartet A nicht mehr). |
| **S94** (Pflichtpunkt fehlt) | «kein Fehler» | **Mein Helfer war falsch.** Er füllte einen leeren Wertesatz automatisch auf (`values or {...}`), sodass der Fall gar nicht gestellt wurde. Direkt am Dienst gestellt kommt der Fehler — aber er nennt das Stück nicht (siehe `FINDINGS.md`, 🟡-3). |
| **S98** (inaktiver Artikel) | «kein Fehler» | **Echter Befund** (🟠-1). |

Dazu ein Befund, den erst die **Invarianten** zutage förderten und der ebenfalls kein
Produktfehler war: `I12` meldete 20 verwaiste Einzelinstanzen. Ursache war der
Aufräumer der bestehenden Wächter-Suite (`test_terminal_status._cleanup`), der über
**ein Stück** löschte und die Instanz dazu — ein zweites Stück derselben Instanz blieb
verwaist zurück. Behoben; danach hinterlässt die Suite nichts mehr (0 Waisen nachgemessen).

## 5 · Runde 2 — die Folgerunde

Beide 🟠-Befunde der ersten Runde sind erledigt: **🟠-1 behoben** (`articles.may_create`),
**🟠-3 entschieden** (der Abbruch IST eine Abweichung). Dabei kam **ein weiterer Befund**
zutage, und zwar durch den Fix selbst:

| | |
|---|---|
| **Wie er auffiel** | Die neue Regel `may_create` ist der **erste Leser**, der die Frage «ist dieser Artikel freigegeben?» wirklich beantworten muss. Auf einer frisch aus den Migrationen gebauten Datenbank fiel sofort **die halbe Suite** aus. |
| **Was dahintersteckte** | Der Artikel-Status existierte in **zwei Sprachen**. Migration `107` hat Daten und *Server*-Default auf `freigegeben`/`inaktiv` gezogen — der *ORM*-Default im Modell blieb auf `"released"`. Und der ORM-Default gewinnt. |
| **Warum es niemand merkte** | Es gab keinen Leser. `services/articles` setzt den Status ausdrücklich; sonst fragte im aktiven Bereich niemand danach. Der Widerspruch war folgenlos — bis er es nicht mehr war. |
| **Behoben** | Standardwert aus dem Katalog, ORM- und Server-Default in derselben Zeile. Wächter `test_the_article_status_has_exactly_one_vocabulary`, gegen die Bug-Form gegengeprüft. |
| **Ausdrücklich offen** | In den **abgeschalteten** Bereichen (`ai`, `selling`) steht die alte Sprache noch. Sie sind nicht importierbar; wer sie wieder einschaltet, muss sie mitziehen (`FINDINGS.md`, Fund 4). |

**Und ein Messfehler auf meiner Seite, der hierher gehört:** der erste Suite-Lauf dieser
Runde hing nach 15 Minuten. Ursache war **nicht** der Code, sondern meine über viele Läufe
gewachsene Scratch-Datenbank — eine offene Sitzung auf `articles` gegen die
ACCESS-EXCLUSIVE-Sperre des Schema-Netzes. Gegen eine **frisch aus den Migrationen
gebaute** Datenbank (also so, wie die CI es tut) läuft die ganze Suite in **12 Sekunden**:
290 bestanden, 1 übersprungen (der bekannte Befund 🟡-1).
