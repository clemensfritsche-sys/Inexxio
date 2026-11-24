# 24.11.2026 – Spam aus dem Formular, Betreff «Anfrage», Logo der Mail

**Anlass:** die erste Anfrage auf Produktion war Spam («Hi, kam dashur të di çmimin tuaj», Name
«Robertattaw», Firma «google») – durch Honigtopf, Mindestzeit und 5/h gerutscht. Sie legte eine
Person an, stand offen in «zu tun» und bekam eine Bestätigung an eine vermutlich fremde Adresse.

**Entschieden (Inhaber):**
- **Spam: die KI liest jede Anfrage zuerst** (`services/spam`, Haiku, Bruchteile eines Rappens).
  Spam wird aussortiert – nichts entsteht, die Anfrage steht im Log (`inquiry.held`) und an der
  Gesellschaft im Reiter «Verlauf» unter «Aussortiert», getrennt vom Verlauf, und in «zu tun», bis
  jemand «Kein Spam» oder «Spam» wählt. Ohne KI geht jede Anfrage durch.
- **Betreff immer «Anfrage»** – nicht mehr der erste Satz (Spam schrieb ihn mit). Offen bleibt eine
  Anfrage je Person (`_ANSWERED` fragt Betreff UND Person – geprüft, Test
  `test_an_answer_closes_only_the_inquiry_of_its_person`). Die Bestätigung bleibt «Angekommen –
  Danke für Ihre Anfrage».
- **Logo der Mail-Vorlage 176 statt 240 px** – dezenter; die Unterzeile bleibt lesbar.
- Zeiterfassung (Pause nachtragen, Uhrzeit «12.03»): bleibt, wie es ist.

**Verworfen:**
- Anfragen über Gmail laufen lassen, damit sein Spamfilter greift: eine Mail an uns selbst prüft
  Gmail nicht, und es wäre ein zweiter Weg für dieselbe Sache.
- Captcha (Google, Cloudflare Turnstile): Dritte, Datenschutz, lästig für echte Kunden. Die nächste
  Stufe, falls Bots das Formular einmal in Massen treffen.
- Spam ganz verwerfen: eine verwechselte echte Anfrage wäre verloren.

**Nicht geändert:** die Datenschutzerklärung – Abschnitt 10 sagt schon, dass die KI eingehende
Nachrichten liest und ein Mensch entscheidet.
