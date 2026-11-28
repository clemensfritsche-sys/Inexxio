# Übersetzungen der Website

Deutsch ist die Quelle. Jede weitere Sprache steht in `src/i18n/<sprache>/` (Liste und Status:
`src/config/languages.mjs`, Entscheid 136 in `website/WEBSITE_PLAN.md`).

## Wie es funktioniert

- Jeder Text im Code geht durch `t('<datei>', …)` (`src/i18n/t.mjs`). Der deutsche Text ist der
  Schlüssel: `src/i18n/fr/krantechnik.json` ist ein Wörterbuch `"Deutsch": "Français"`.
- Derselbe deutsche Text wird einmal übersetzt und gilt überall.
- Adressen: `src/i18n/<sprache>/pfade.json` (deutscher Pfad → Pfad der Sprache, immer unter `/<sprache>`).
- Ratgeber: `src/content/ratgeber/<sprache>/<gleicher-name>.md`, mit `quelle: "<Fingerabdruck>"` in
  den Kopfangaben – den Fingerabdruck nennt `npm run sprachen`.

## Wenn sich ein deutscher Text ändert

Der Build bricht ab und nennt jeden Befund (`npm run sprachen` zeigt dieselbe Liste):

| Befund | Bedeutung | Was tun |
|---|---|---|
| fehlt | neuer oder geänderter deutscher Text | übersetzen (`node scripts/languages.mjs --prepare` trägt ihn leer ein) |
| verwaist | den deutschen Text gibt es nicht mehr | löschen (`--prepare` tut es) – war er nur geändert, steht der neue unter «fehlt» |
| leer | eingetragen, aber nicht übersetzt | übersetzen |
| Werte | `{{…}}`, Links `[…](…)`, `**`, `==` stimmen nicht mit dem Deutsch überein | angleichen |
| Pfad | eine Seite ohne Adresse in der Sprache | in `pfade.json` eintragen |
| Ratgeber | Artikel fehlt oder das Deutsch hat sich geändert | nachziehen, `quelle` erneuern |

Dazu prüft `scripts/check-site.mjs` jede gebaute Seite einer anderen Sprache auf deutsche Wörter –
ein Text, der an `t()` vorbei im Code steht, fällt so auf.

## Regeln für jede Übersetzung

- Ton wie im Deutschen: einfach, direkt, sachlich, Sie-Form (fr: «vous»). Keine Werbefloskeln.
- **Unverändert lassen:** `{{werte}}`, Link-Ziele `(…)`, `**` und `==` (sie umschliessen die
  entsprechende Stelle der Übersetzung), Marken- und Firmennamen (INEXXIO, INEXXIO 365, HS Steiner,
  Putzmeister, Liebherr …), Personennamen, Strassen.
- Keine Ausrufezeichen, keine Emojis, kein «ß».
- Seitentitel (`title`) höchstens 50 Zeichen (mit « | INEXXIO» höchstens 60); Beschreibungen
  (`description`) möglichst 140–155 Zeichen.
- Anführungszeichen wie im Deutschen: «…» ohne Leerzeichen innen (Schweizer Satz).
- Zahlen in Schweizer Schreibweise: 1'200, CHF.
- Nie «Werkstatt» und «Fixpreis» – auch nicht übersetzt (fr: kein «atelier», kein «prix fixe»;
  stattdessen «chez nous», «dans notre entreprise», «prix convenu d'avance» …).

## Glossar Französisch (fr-CH)

| Deutsch | Français |
|---|---|
| Fahrmischer | camion malaxeur |
| (Misch-)Trommel | tambour (malaxeur) |
| Trommeltausch | remplacement du tambour |
| Fahrgestell | châssis |
| Verschleissteile | pièces d'usure |
| Auslaufrinne / Rinne | goulotte (de déchargement) |
| Verlängerungsrinne | rallonge de goulotte |
| Einfülltrichter | trémie de chargement |
| Auslaufschurre / Schurre | trémie de déchargement |
| Mischspiralen | spirales de malaxage |
| Spiralschutz | protection des spirales |
| Fahrzeugtechnik | Technique des véhicules |
| Krantechnik | Technique de levage |
| Krane nach Mass | Grues sur mesure |
| Kranservice | Service grues |
| Heukrananlage | installation de grue à foin |
| Heukran | grue à foin |
| Brückenkran | pont roulant |
| Zweiträger-Brückenkran | pont roulant bipoutre |
| Hängekran | pont suspendu |
| Schwenkkran / Säulenschwenkkran | potence / potence sur colonne |
| Laufkatze, Katze | chariot |
| Kranbahn | chemin de roulement |
| Hubwerk | treuil de levage |
| Kettenzug | palan à chaîne |
| Greifer | grappin |
| Funkfernsteuerung, per Funk | radiocommande, par radiocommande |
| Kranbuch | carnet de la grue |
| Kranprüfung | contrôle de grue |
| Bootskran, Mastkran, Bootslift | grue à bateaux, grue à mâts, élévateur à bateaux |
| Speziallösungen | Solutions spéciales |
| Spezialmaschinen | machines spéciales |
| Anbaugeräte | équipements portés |
| Baumaschinen | engins de chantier |
| Minibagger | mini-pelle |
| Rüttelplatte | plaque vibrante |
| Verbindliche Offerte | offre ferme |
| Offerte | offre |
| Anfrage / Anfrage stellen | demande / Faire une demande |
| Funktionsgarantie | garantie de bon fonctionnement |
| Inspektion · Prüfung · Wartung · Reparatur | inspection · contrôle · entretien · réparation |
| Probelauf | essai de fonctionnement |
| Inbetriebnahme | mise en service |
| Einweisung | instruction |
| Stillstand | arrêt |
| Ratgeber | Conseils |
| Über uns | À propos |
| Karriere | Carrière |
| ehemals HS Steiner | anciennement HS Steiner |
| Tuttwil-Wängi TG | Tuttwil-Wängi TG (unverändert) |
| Zürich · St. Gallen · Bodensee · Schweiz | Zurich · Saint-Gall · lac de Constance · Suisse |

## Glossar Englisch (`en`, britisches Englisch)

| Deutsch | English |
|---|---|
| Fahrmischer | truck mixer |
| (Misch-)Trommel · Trommeltausch | (mixer) drum · drum replacement |
| Fahrgestell | chassis |
| Verschleissteile | wear parts |
| Auslaufrinne · Verlängerungsrinne | discharge chute · extension chute |
| Einfülltrichter · Auslaufschurre | charging hopper · discharge hopper |
| Mischspiralen · Spiralschutz | mixing spirals · spiral protection |
| Fahrzeugtechnik · Krantechnik · Speziallösungen | Vehicle technology · Crane technology · Special solutions |
| Krane nach Mass · Kranservice | Custom cranes · Crane service |
| Heukrananlage · Heukran | hay crane system · hay crane |
| Brückenkran · Hängekran · Schwenkkran | overhead travelling crane · underhung crane · jib crane |
| Laufkatze · Kranbahn · Hubwerk · Kettenzug · Greifer | trolley · crane runway · hoist · chain hoist · grab |
| Funkfernsteuerung | radio remote control |
| Kranbuch · Kranprüfung | crane logbook · crane inspection |
| Anbaugeräte · Baumaschinen · Minibagger · Rüttelplatte | attachments · construction machinery · mini excavator · plate compactor |
| Verbindliche Offerte · Offerte | binding quote · quote |
| Anfrage stellen | Send an enquiry |
| Funktionsgarantie | performance guarantee |
| Probelauf · Inbetriebnahme · Einweisung · Stillstand | test run · commissioning · instruction · breakdown |
| Ratgeber · Über uns · Karriere | Guides · About us · Careers |
| ehemals HS Steiner | formerly HS Steiner |
| Zürich · St. Gallen · Bodensee · Schweiz | Zurich · St. Gallen · Lake Constance · Switzerland |

## Glossar Italienisch (`it`, Italienisch der Schweiz)

| Deutsch | Italiano |
|---|---|
| Fahrmischer | autobetoniera |
| (Misch-)Trommel · Trommeltausch | tamburo (betoniera) · sostituzione del tamburo |
| Fahrgestell | telaio |
| Verschleissteile | parti di usura |
| Auslaufrinne · Verlängerungsrinne | canala di scarico · prolunga della canala |
| Einfülltrichter · Auslaufschurre | tramoggia di carico · tramoggia di scarico |
| Mischspiralen · Spiralschutz | spirali di miscelazione · protezione delle spirali |
| Fahrzeugtechnik · Krantechnik · Speziallösungen | Tecnica veicoli · Tecnica di sollevamento · Soluzioni speciali |
| Krane nach Mass · Kranservice | Gru su misura · Servizio gru |
| Heukrananlage · Heukran | impianto gru per fieno · gru per fieno |
| Brückenkran · Hängekran · Schwenkkran | carroponte · gru sospesa · gru a bandiera |
| Laufkatze · Kranbahn · Hubwerk · Kettenzug · Greifer | carrello · vie di corsa · argano di sollevamento · paranco a catena · benna |
| Funkfernsteuerung | radiocomando |
| Kranbuch · Kranprüfung | libretto della gru · controllo della gru |
| Anbaugeräte · Baumaschinen · Minibagger · Rüttelplatte | attrezzature · macchine edili · miniescavatore · piastra vibrante |
| Verbindliche Offerte · Offerte | offerta vincolante · offerta |
| Anfrage stellen | Invia una richiesta |
| Funktionsgarantie | garanzia di buon funzionamento |
| Probelauf · Inbetriebnahme · Einweisung · Stillstand | prova di funzionamento · messa in servizio · istruzione · fermo macchina |
| Ratgeber · Über uns · Karriere | Guide · Chi siamo · Lavora con noi |
| ehemals HS Steiner | già HS Steiner |
| Zürich · St. Gallen · Bodensee · Schweiz | Zurigo · San Gallo · Lago di Costanza · Svizzera |
