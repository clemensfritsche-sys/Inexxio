# 2026-10-24 – Service, Karriere und Ratgeber im Layout v4

**Was** (WEBSITE_PLAN Entscheid 129): die letzten Seiten im alten Stil neu, nach Vorschlag im Artefakt
«Service, Karriere, Ratgeber – Vorschlag» und Freigabe des Auftraggebers.
- `/service`: Kopf (Titelbild Transporter) → Notfall als dunkle Karte (`CallPanel`, Nummer gross, was man
  bereithält, «Bis wir da sind») → Saison-Aktion → «Wobei dürfen wir helfen?» (drei `FieldCards`) →
  Garantien → Fragen (4) → Anfrage.
- `/karriere`: Kopf (drei Menschen am Kran) → Warum hier arbeiten (`FactGrid`, 4) → Wer zu uns passt (drei
  Karten, je eine Bewerbungs-Mail mit Betreff; keine ausgeschriebenen Stellen) → So bewerben Sie sich
  (`SolutionPath`, 3) → Bewerbung (`CallPanel`). Kein Anfrage-Formular.
- `/ratgeber`: Kopf (Kranbuch) → Artikel als `FieldCards` mit Zeichnung → Anfrage. Artikel: Titel und Autor
  neben der Zeichnung, «Kurz gesagt» als graue Karte, Lesespalte, Quellen, «Weiterlesen» als Karten (die
  Zeichnung eines Ziels kommt aus der Navigation bzw. aus `illo` des Artikels), Anfrage. Texte unverändert.
- Neu: `components/CallPanel.astro`, Kopfangabe `illo` in jedem Artikel (`lib/ratgeber.ts` verlangt sie).
- Entfernt, weil niemand sie mehr nutzt: `Hero`, `EntryTiles`, `ArticleCard`, `RelatedLinks`.
