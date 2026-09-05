# Zahlungsdienst (Stripe) — Setup

Der Zahlungsdienst ist **optional**. Ohne Schlüssel läuft alles unverändert: bezahlt wird
per **Überweisung**, und die trägt ein Mensch ein. Das ist kein Fallback, sondern der
B2B-Normalfall — der Knopf «Jetzt bezahlen» erscheint dann gar nicht erst.

> **Das ERP nennt Betrag und Währung. Stripe kassiert.**
>
> Im Vorgängersystem stand es umgekehrt (dort hiess es wörtlich «Stripe ist Quelle der
> Wahrheit»), und daraus kam fast die ganze Komplexität: `stripe_*`-Snapshot-Spalten an
> vier Tabellen, ein Webhook, der **Aufträge erzeugte**, ein `CheckoutIntent` mit
> Reservierungen und ein Aufräumer für verlassene Warenkörbe. Heute schreibt der Webhook
> **eine Zeile Geld** (`services/deal.record_payment`) und sonst nichts.

> ►►► **Bezahlt wird BEI UNS, nicht dort.** ◄◄◄
>
> Es gibt keinen Zahllink mehr. Der Zahlende — Kunde **oder** Personal — bleibt im ERP:
> die Karte, die Wörter, der Betrag und der Knopf sind unsere. Vom Dienst kommen nur die
> **Eingabefelder** (ein *Payment Element* in einem iframe), und das ist ihr Sinn: so
> berührt **keine Kartennummer je unseren Server**. Die 3-D-Secure-Abfrage gehört der
> Bank; sie liesse sich gar nicht nachbauen.
>
> **Was das ERP weiss, wird nicht gefragt**: Name, E-Mail und Rechnungsadresse der
> Gegenpartei reisen mit und werden dem Element als feste Angabe übergeben. Fehlt die
> Adresse, fragt es sie — eine halbe Vorbelegung wäre schlechter als die Frage.

## 1. Sandbox-Schlüssel

Im Stripe-Dashboard oben das **Sandbox/Test**-Konto wählen. Unter
**Developers → API keys** beide kopieren:

| Schlüssel | wofür |
|---|---|
| **Secret key** (`sk_test_…`) | Der Server legt die Zahlungsabsicht an und prüft den Webhook. |
| **Publishable key** (`pk_test_…`) | Der Browser rendert damit das Formular. |

**Beide sind Pflicht**, und das ist eine Ableitung, keine Einstellung: einer allein wäre
eine halbe Strasse — der Knopf erschiene, und der Dialog bliebe leer
(`config.payment_service_ready()`).

> **Zwei Schlüssel, zwei Wege — und das ist kein Widerspruch.** Der *Secret Key* ist ein
> Geheimnis und gehört in den Secret Manager (§4). Der *Publishable Key* ist **keines**:
> er steht in jeder Bezahlseite der Welt im Quelltext, und er steht auch bei uns im
> Browser jedes Zahlenden. Ihn wie ein Geheimnis zu behandeln kostet zwei `gcloud`-Befehle
> und eine IAM-Bindung und schützt **nichts**. Er steht darum als **einfache Variable** im
> Deploy (§5) — genau dort, wo `NEXT_PUBLIC_FIREBASE_API_KEY` seit jeher steht, und aus
> demselben Grund: gleiche Sache, gleicher Weg.

## 2. Dashboard: Zahlungsarten und Adaptive Pricing

**Welche Arten angeboten werden, entscheidet das Konto**, nicht unser Code:
**Settings → Payments → Payment methods**. Für die Schweiz sinnvoll: **Karte** und
**TWINT** (≈ 1.3 % + 0.30 statt 1.5–2.9 % + 0.30 — die günstigere Sofortzahlung). Unser
Code fragt `automatic_payment_methods` und führt **keine eigene Liste**: die wäre die
zweite Stelle, an der beim nächsten Freischalten jemand nichts sieht.

> **Stand im Sandbox-Konto** (gemessen am 05.09.2026, `payment_method_configurations`):
> **Karte an**, **TWINT aus** (`available: false` — Stripe schaltet es erst frei, wenn das
> Konto aktiviert ist). Bezahlen geht damit heute per Karte; TWINT ist **ein Schalter im
> Dashboard**, keine Code-Änderung. An gibt es daneben eine ganze Reihe, die für ein
> Schweizer B2B-ERP kaum passt (Klarna, Link, Amazon Pay, Bancontact, EPS, BLIK, MB Way,
> Pix, Satispay) — sie stehen sonst alle im Formular. Was davon bleibt, ist eine
> **Konto**-Entscheidung; der Code fragt sie nicht.

**Adaptive Pricing → Disabled** (das ist der Standard — **nicht** aktivieren). Wir geben
Betrag **und** Währung vor (`stripe_pay.prepare`); wäre es an, rechnete Stripe unsere Zahl
mit **seinem** Kurs erneut um: angezeigt € 11.80, belastet € 11.82.

**Stripe Tax bleibt aus.** Es berechnete eine Steuer, die wir nicht kennen — die
Umkehrung des Grundsatzes oben. Die Steuer steht am Beleg (`deal_entries.vat`).

## 3. Webhook-Endpoint

**Die Adresse für `inexxio-dev` lautet:**

```
https://inexxio-dev.web.app/api/v1/payments/webhook
```

Das ist die Adresse der **Website**, und sie ist trotzdem richtig: Firebase Hosting leitet
`/api/**` an den Cloud-Run-Dienst weiter (`firebase.json`, Rewrite auf
`inexxio-backend-dev` in `europe-west6`). Die direkte Cloud-Run-URL des Dienstes ginge
ebenso — sie ist nur nirgends aufgeschrieben, während diese hier stabil und bekannt ist.

> **Woran man merkt, ob der Umweg trägt:** die Signatur gilt für die **rohen Bytes**.
> Käme der Rumpf verändert an, wäre die Antwort `400 {"detail":"Ungültige Signatur."}` —
> im Stripe-Dashboard sofort sichtbar, ohne dass jemand raten muss. Die erste Testzahlung
> (§6) beantwortet das also mit. Bleibt es dabei, **direkt auf die Cloud-Run-URL** zeigen
> (`gcloud run services describe inexxio-backend-dev --region europe-west6
> --format='value(status.url)'`) — das ist derselbe Dienst, nur ein Hop weniger.

**Im Dashboard:**

1. **Developers → Webhooks → Add endpoint**
2. **Endpoint URL**: die Adresse oben
3. **Events** — genau diese zwei, mehr liest der Code nicht:
   - `payment_intent.succeeded`
   - `charge.refunded`
4. Speichern → **Signing secret** (`whsec_…`) kopieren.

> ⚠ **Wer den Endpoint aus der Zeit des Zahllinks hat, muss ihn umstellen**: dort steht
> `checkout.session.completed`, und die Meldung gibt es nicht mehr — die gehostete Kasse
> ist weg. Der Beleg bliebe auf «offen» stehen, obwohl das Geld da ist.
>
> **Für `inexxio-dev` ist das erledigt** (05.09.2026): der bestehende Endpoint
> `we_1TnvmEQr3aoUqi8iTHk0Ukj0` hört auf die beiden Ereignisse oben. **Umgestellt, nicht
> neu angelegt** — und das ist der Punkt: das *Signing Secret* eines Endpoints ändert sich
> beim Umstellen **nicht**, `STRIPE_WEBHOOK_SECRET` bleibt also gültig. Ein neuer Endpoint
> hätte ein neues Secret gebraucht, und bis es im Secret Manager steht, liefe jede Meldung
> in «Ungültige Signatur».

**Oder in einem Aufruf** (dasselbe, nur ohne Klicks — die Antwort enthält das `secret`,
und zwar **nur bei der Anlage**):

```bash
curl -sS https://api.stripe.com/v1/webhook_endpoints \
  -u "sk_test_DEIN_KEY:" \
  -d url="https://inexxio-dev.web.app/api/v1/payments/webhook" \
  -d "enabled_events[]=payment_intent.succeeded" \
  -d "enabled_events[]=charge.refunded" \
  -d description="Inexxio dev" | python3 -m json.tool
```

Jedes andere Ereignis wird mit `200 {"status":"ignored"}` quittiert. Ein Fehlercode darauf
brächte Stripe nur dazu, es endlos erneut zuzustellen.

> **Bis der Endpoint steht, ist die Zahlung eine Einbahnstrasse**: die Karte kassiert, aber
> die Buchung entsteht erst mit der Rückmeldung — der Vorgang bliebe auf «offen» stehen.
> Der Rückweg läuft bewusst über den Webhook und nicht über den Browser: wer ihn nach der
> Zahlung schliesst, darf keine Buchung verschlucken.

> **Das neue Signing Secret muss danach nach Secret Manager** (§4) — und der Dienst
> **neu starten**, sonst prüft er gegen das alte. Ein Secret aus einer früheren
> Einrichtung passt **nicht**: es gehört zu *jenem* Endpoint, und jede Meldung liefe in
> «Ungültige Signatur» (400). Das ist die richtige Antwort und sieht trotzdem aus wie ein
> kaputter Webhook — darum hier genannt.
>
> Bei der Gelegenheit: **alte Endpoints im Dashboard löschen**. Einer, der auf eine
> Adresse des Vorgängersystems zeigt, stellt weiter zu und sammelt Fehlversuche.

## 4. Die zwei Geheimnisse im Google Secret Manager (`inexxio-dev`)

Nur diese beiden — der *Publishable Key* ist keines und geht den kürzeren Weg (§5).

```bash
printf '%s' 'sk_test_DEIN_KEY' | gcloud secrets create STRIPE_SECRET_KEY \
  --project=inexxio-dev --replication-policy=automatic --data-file=-

printf '%s' 'whsec_DEIN_SECRET' | gcloud secrets create STRIPE_WEBHOOK_SECRET \
  --project=inexxio-dev --replication-policy=automatic --data-file=-
```

Existieren sie schon, eine neue Version anhängen:

```bash
printf '%s' 'sk_test_…' | gcloud secrets versions add STRIPE_SECRET_KEY --project=inexxio-dev --data-file=-
printf '%s' 'whsec_…'   | gcloud secrets versions add STRIPE_WEBHOOK_SECRET --project=inexxio-dev --data-file=-
```

**Zugriff** (einmalig) für den Cloud-Run-Service-Account:

```bash
for S in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET; do
  gcloud secrets add-iam-policy-binding "$S" --project=inexxio-dev \
    --member="serviceAccount:cloudrun-backend@inexxio-dev.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

> **Reihenfolge:** erst die Secrets anlegen, dann deployen — `--set-secrets` referenziert
> sonst etwas, das es nicht gibt, und der **ganze** Deploy schlägt fehl (nicht nur die
> Zahlung). Beide stehen für `inexxio-dev` bereits dort; die Deploy-Zeile nennt sie, und
> der Deploy läuft.

## 5. Der öffentliche Schlüssel: eine Zeile im Deploy

In `.github/workflows/deploy-dev.yml` beim Cloud-Run-Deploy die Zeile `--set-env-vars`
um **`STRIPE_PUBLISHABLE_KEY=pk_test_…`** ergänzen:

```
--set-env-vars "APP_ENV=development,FRONTEND_BASE_URL=https://inexxio-dev.web.app,STRIPE_PUBLISHABLE_KEY=pk_test_…" \
```

Kein Secret Manager, kein `gcloud`, keine IAM-Bindung — der Wert steht ohnehin im Browser
jedes Zahlenden, genau wie `NEXT_PUBLIC_FIREBASE_API_KEY` ein paar Zeilen tiefer.

**Ohne diese Zeile ist der Dienst schlicht nicht eingerichtet** — kein Fehler, kein Stub,
kein 503: `payment_service_ready()` ist `False`, und der Knopf «Jetzt bezahlen» erscheint
nicht (`DealEmbed.can` führt `pay_online` dann gar nicht).

## 6. Testen (Sandbox)

1. Artikel mit einem **Zahlung**-Modul anlegen (Richtung **Einnahme**, ein Partner),
   Auftrag freigeben.
2. Am Vorgang: anbieten → Angebot annehmen → **Rechnung erfassen**.
3. Unter den Stufen erscheint die Zahlungszeile: **offen · fällig** — und daneben
   **«Jetzt bezahlen»**.
4. Klicken → das Formular öffnet sich **in der Karte**: Testkarte
   `4242 4242 4242 4242`, beliebiges künftiges Datum, beliebige CVC/PLZ. Name, E-Mail und
   Adresse stehen schon da, wenn sie am Benutzer gepflegt sind.
5. Nach der Zahlung meldet der **Webhook** – nicht der Browser: die Zeile erscheint mit
   der `pi_…`-Referenz in der Buchungsliste. (Die Karte sagt darum «ausgeführt» und nicht
   «gebucht»: dazwischen liegt eine Sekunde, die niemandem gehört.)
6. **Als Gegenpartei prüfen**: mit dem Benutzer anmelden, der als Partner eingetragen ist
   — er sieht den Auftrag, sein Modul, den offenen Betrag und denselben Knopf. Er sieht
   **keine** Freigabe-Liste, keine fremden Preise und hat **keine** Buchungs-Knöpfe.
7. Erstattung **im Stripe-Dashboard** auslösen → `charge.refunded` bucht eine **negative**
   Zahlung (eigene Referenz `pi_…:refund`). Einen eigenen Erstattungs-Knopf gibt es
   bewusst nicht: der Dienst bietet ihn an, und «erstattet wird auf dem Weg, auf dem
   gezahlt wurde» ist dort ohnehin die einzige Möglichkeit.

## Was es bewusst NICHT gibt

| | warum |
|---|---|
| Ein Zahllink / gehostete Kasse | Der Kunde stand auf einer fremden Seite mit fremdem Namen. Die Bezahlkarte ist unsere; nur die Eingabefelder gehören dem Dienst — und genau deshalb berührt keine Kartennummer unseren Server. |
| Ein Kunden-Datensatz beim Dienst (`Customer`) | Zwei Stammdaten für dieselbe Person, und die zweite ausserhalb des ERP. Die Angaben reisen je Zahlung mit. |
| Eine Quittungs-Mail des Dienstes | Fremdes Briefpapier für einen Vorgang, der bei uns steht. Der Nachweis ist die Zeile im Geldvorgang. |
| Eine eigene Liste von Zahlungsarten | Was angeboten wird, entscheidet das Konto (`automatic_payment_methods`). Eine zweite Liste sähe beim nächsten Freischalten nichts. |
| Ein `manual`-Provider | Er simulierte einen Zahlungsdienstleister samt eigener Bezahlseite. Eine Überweisung braucht keine Simulation — sie braucht ein Feld. |
| Ein Provider-Rahmen mit zwei Implementierungen | Eine Abstraktion über einer Zeile. |
| Stripe Tax | Es berechnete eine Zahl, die wir nicht kennen. |
| Customer Portal / Subscriptions | Wiederkehrende Aufträge werden eine **Schlaufe im Prozess** (PROCESS_CORE §13.7), kein Abo-Objekt beim Zahlungsdienst. |
| `stripe_customer_id` & Co. | Die Id steht in `deal_entries.reference` — in derselben Spalte, in der bei einer Überweisung der Zahlungszweck steht. Ein Feld, zwei Wege. |
| Ein eigener Erstattungs-Knopf | Der Dienst bietet ihn an. Ein zweiter Auslöser wäre ein zweiter Weg zu derselben Buchung — der Webhook fängt sie ohnehin. |

## Go-Live

Für die Produktion dieselben Schritte im Live-Modus und mit `inexxio-prod`; die
Endpoint-URL zeigt dann auf das Prod-Backend. **Zuerst in der Sandbox durchspielen** —
ein falsch gesetzter Webhook fällt sonst erst auf, wenn Geld fliesst.
